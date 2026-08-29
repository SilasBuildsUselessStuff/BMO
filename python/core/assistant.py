"""Controller connecting BMO state, voice, AI, TTS, and serial communication."""

from threading import Event, RLock, Thread
from typing import Optional

import numpy as np
import json

from ai.client import AIClient, AIError
from communication.serial import BMOConnection
from core.state import BMOExpression, BMOState
from core.tools import ToolResult
from voice.listener import MicrophoneError, MicrophoneListener
from voice.tts import TTSError, TTSProvider
from voice.whisper import TranscriptionError, WhisperTranscriber


class BMOAssistant:
    """
    Coordinate BMO's state, voice components, AI, TTS, and ESP32 connection.

    Whisper, Ollama, and TTS all run in a background interaction thread.
    This keeps Tkinter responsive throughout the complete voice interaction.
    """

    def __init__(
        self,
        state: BMOState,
        connection: BMOConnection,
        listener: Optional[MicrophoneListener] = None,
        transcriber: Optional[WhisperTranscriber] = None,
        ai_client: Optional[AIClient] = None,
        tts: Optional[TTSProvider] = None,
    ) -> None:
        self.state = state
        self.connection = connection
        self.listener = listener
        self.transcriber = transcriber
        self.ai_client = ai_client
        self.tts = tts

        self._voice_lock = RLock()
        self._interaction_thread: Optional[Thread] = None
        self._shutdown_event = Event()

        # Serial callbacks execute in the serial background thread.
        self.connection.on_connection_change = self._on_connection_change
        self.connection.on_message = self._on_serial_message

    def start(self) -> None:
        """Start communication with the physical BMO."""

        self._shutdown_event.clear()
        self.connection.start()

    def stop(self) -> None:
        """Stop microphone, speech, and serial communication cleanly."""

        self._shutdown_event.set()

        if self.listener is not None:
            self.listener.cancel_recording()

        if self.tts is not None:
            self.tts.cancel()

        self.connection.stop()
        self.state.set_connected(False)

    def toggle_listening(self) -> None:
        """
        Start or stop a voice interaction.

        Button presses are ignored while BMO is thinking or talking. This
        prevents overlapping interactions and stops BMO from recording its
        own synthesized voice.
        """

        snapshot = self.state.snapshot()

        if snapshot.thinking or snapshot.speaking:
            return

        if snapshot.listening:
            if self._voice_is_configured():
                self._stop_listening_and_process()
            else:
                self.enter_idle()
        else:
            if self._voice_is_configured():
                self._start_listening()
            else:
                self.enter_listening()

    def enter_idle(self) -> None:
        """Return BMO to IDLE and notify the ESP32."""

        self.state.enter_idle()
        self._send_expression(BMOExpression.IDLE)

    def enter_listening(self) -> None:
        """Put BMO into LISTENING and notify the ESP32."""

        self.state.enter_listening()
        self._send_expression(BMOExpression.LISTENING)

    def enter_thinking(self) -> None:
        """Put BMO into THINKING and notify the ESP32."""

        self.state.enter_thinking()
        self._send_expression(BMOExpression.THINKING)

    def enter_talking(self) -> None:
        """Put BMO into TALKING and notify the ESP32."""

        self.state.enter_talking()
        self._send_expression(BMOExpression.TALKING)

    def _voice_is_configured(self) -> bool:
        """Return whether both required voice-input components are available."""

        return self.listener is not None and self.transcriber is not None

    def _start_listening(self) -> None:
        """Start recording through the PC microphone."""

        if self.listener is None:
            return

        with self._voice_lock:
            if self.listener.is_recording:
                return

            self.state.clear_error()

            # Remove the previous response while a new interaction is active.
            self.state.set_last_bmo_response("—")

            try:
                self.listener.start_recording()
            except MicrophoneError as error:
                self.state.set_error(f"Microphone: {error}")
                self.enter_idle()
                return

            self.enter_listening()

    def _stop_listening_and_process(self) -> None:
        """
        Stop recording and start the background interaction worker.

        The worker performs:

            recorded audio
                -> Whisper
                -> Ollama
                -> TTS
        """

        if self.listener is None or self.transcriber is None:
            self.enter_idle()
            return

        with self._voice_lock:
            try:
                audio = self.listener.stop_recording()
            except MicrophoneError as error:
                self.state.set_error(f"Microphone: {error}")
                self.enter_idle()
                return

            self.enter_thinking()

            self._interaction_thread = Thread(
                target=self._process_interaction,
                args=(audio,),
                name="BMO-Interaction",
                daemon=True,
            )
            self._interaction_thread.start()

    def _process_interaction(self, audio: np.ndarray) -> None:
        """
        Run Whisper, Ollama, and TTS in a background thread.

        This method only modifies the thread-safe central state. It never
        accesses Tkinter widgets directly.
        """

        if self.transcriber is None:
            self.state.set_error("Whisper transcriber is not configured.")
            self.enter_idle()
            return

        try:
            # Stage 1: microphone audio -> transcript
            transcript = self.transcriber.transcribe(audio)

            if self._shutdown_event.is_set():
                return

            if not transcript:
                self.state.set_last_user_input("—")
                self.state.set_error("No speech was detected.")
                print("Whisper: No speech was detected.")

                self._deliver_fallback_response(
                    "I didn't catch that. Can you repeat it?"
                )
                return

            self.state.set_last_user_input(transcript)
            self.state.clear_error()
            print(f"You: {transcript}")

            # Keeping AI optional preserves modularity.
            if self.ai_client is None:
                return

                       # Stage 2: transcript -> BMO response and optional tool results
            ai_response = self.ai_client.generate_response(transcript)

            if self._shutdown_event.is_set():
                return

            response = ai_response.text

            # Store canonical response text before preparing it for TTS.
            self.state.set_last_bmo_response(response)
            self.state.clear_error()
            print(f"BMO: {response}")

            # Tool results remain structured. We never extract screen data
            # from the AI's generated sentence.
            for tool_result in ai_response.tool_results:
                self._handle_tool_result(tool_result)

            # Keeping TTS optional preserves text-only operation.
            if self.tts is None:
                return

            # Stage 3: BMO response -> speech
            self.enter_talking()

            if self._shutdown_event.is_set():
                return

            self.tts.speak(response)

        except TranscriptionError as error:
            if not self._shutdown_event.is_set():
                message = f"Whisper: {error}"
                self.state.set_error(message)
                print(message)

                self._deliver_fallback_response(
                    "I didn't catch that. Can you repeat it?"
                )

        except AIError as error:
            if not self._shutdown_event.is_set():
                message = f"AI: {error}"
                self.state.set_error(message)
                print(message)

                self._deliver_fallback_response(
                    "I didn't quite get that. Can you repeat it?"
                )

        except TTSError as error:
            if not self._shutdown_event.is_set():
                message = f"TTS: {error}"
                self.state.set_error(message)
                print(message)

        except Exception as error:
            if not self._shutdown_event.is_set():
                message = f"Unexpected interaction error: {error}"
                self.state.set_error(message)
                print(message)

                self._deliver_fallback_response(
                    "Oops, I didn't quite get that. Can you repeat it?"
                )

        finally:
            if not self._shutdown_event.is_set():
                self.enter_idle()

    def _deliver_fallback_response(
        self,
        text: str = "I didn't quite get that. Can you repeat it?",
    ) -> None:
        """
        Display and speak a short fallback after a recoverable failure.

        This method runs in the existing interaction worker, so blocking TTS
        playback does not freeze Tkinter.
        """

        if self._shutdown_event.is_set():
            return

        self.state.set_last_bmo_response(text)
        print(f"BMO: {text}")

        if self.tts is None:
            return

        self.enter_talking()

        try:
            self.tts.speak(text)
        except TTSError as error:
            message = f"TTS: {error}"
            self.state.set_error(message)
            print(message)
    
    def _send_expression(self, expression: BMOExpression) -> bool:
        """Send one expression command to the ESP32."""

        command = f"EXPRESSION:{expression.value}"
        return self.connection.send_line(command)

    def _handle_tool_result(self, result: ToolResult) -> None:
        """
        Store and publish structured information produced by a tool.

        The state copy is consumed by the development GUI. The JSON message
        prepares the serial protocol for the future physical screen renderer.
        """

        if not result.display_type:
            return

        display_type = result.display_type.strip().upper()

        self.state.set_tool_display(
            display_type=display_type,
            display_data=result.display_data,
        )

        payload = {
            "protocol_version": 1,
            "type": "screen_data",
            "screen": display_type,
            "data": result.display_data,
        }

        serialized_payload = json.dumps(
            payload,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
        )

        sent = self.connection.send_paced_line(
            serialized_payload,
            chunk_size=32,
            chunk_delay=0.03,
        )

        print(
            f"Tool display: {display_type} "
            f"({'sent to ESP32' if sent else 'stored locally'})"
        )
        print(f"Display data: {result.display_data}")
    
    def _on_connection_change(self, connected: bool) -> None:
        """Update central state when serial connectivity changes."""

        self.state.set_connected(connected)

        if connected:
            print(
                f"Connected to BMO on "
                f"{self.connection.port} at {self.connection.baudrate} baud."
            )

            # Synchronize the physical BMO with the current application state.
            current_expression = self.state.snapshot().expression
            self._send_expression(current_expression)
        else:
            print("BMO serial connection is disconnected.")

    def _on_serial_message(self, message: str) -> None:
        """Log incoming ESP32 messages during development."""

        print(f"ESP32: {message}")
