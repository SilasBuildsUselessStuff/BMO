"""Controller connecting BMO state, voice, AI, and serial communication."""

from threading import Event, RLock, Thread
from typing import Optional

import numpy as np

from ai.client import AIClient, AIError
from communication.serial import BMOConnection
from core.state import BMOExpression, BMOState
from voice.listener import MicrophoneError, MicrophoneListener
from voice.whisper import TranscriptionError, WhisperTranscriber


class BMOAssistant:
    """
    Coordinate BMO's state, voice components, AI, and ESP32 connection.

    Whisper transcription and AI response generation run in a worker thread,
    preventing slow operations from freezing Tkinter.
    """

    def __init__(
        self,
        state: BMOState,
        connection: BMOConnection,
        listener: Optional[MicrophoneListener] = None,
        transcriber: Optional[WhisperTranscriber] = None,
        ai_client: Optional[AIClient] = None,
    ) -> None:
        self.state = state
        self.connection = connection
        self.listener = listener
        self.transcriber = transcriber
        self.ai_client = ai_client

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
        """Stop microphone and serial communication cleanly."""

        self._shutdown_event.set()

        if self.listener is not None:
            self.listener.cancel_recording()

        self.connection.stop()
        self.state.set_connected(False)

    def toggle_listening(self) -> None:
        """
        Start or stop a voice interaction.

        While BMO is thinking, additional button presses are ignored to
        prevent multiple overlapping Whisper or Ollama operations.
        """

        snapshot = self.state.snapshot()

        if snapshot.thinking:
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

    def _voice_is_configured(self) -> bool:
        """Return whether both required voice components are available."""

        return self.listener is not None and self.transcriber is not None

    def _start_listening(self) -> None:
        """Start recording through the PC microphone."""

        if self.listener is None:
            return

        with self._voice_lock:
            if self.listener.is_recording:
                return

            self.state.clear_error()

            # Remove the previous answer while a new interaction is active.
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
        Stop microphone recording and start the interaction worker.

        The worker first transcribes the recording and then, if configured,
        asks the AI client to generate BMO's response.
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
        Run Whisper followed by the AI backend.

        This method executes in a background thread. It only updates the
        thread-safe BMOState and never accesses Tkinter widgets directly.
        """

        if self.transcriber is None:
            self.state.set_error("Whisper transcriber is not configured.")
            self.enter_idle()
            return

        try:
            # Stage 1: microphone audio -> text
            transcript = self.transcriber.transcribe(audio)

            if self._shutdown_event.is_set():
                return

            if not transcript:
                self.state.set_last_user_input("—")
                self.state.set_error("No speech was detected.")
                print("Whisper: No speech was detected.")
                return

            self.state.set_last_user_input(transcript)
            self.state.clear_error()
            print(f"You: {transcript}")

            # Keeping the AI optional preserves the modular V0.2 behavior.
            if self.ai_client is None:
                return

            # Stage 2: transcript -> BMO response
            response = self.ai_client.generate_response(transcript)

            if self._shutdown_event.is_set():
                return

            self.state.set_last_bmo_response(response)
            self.state.clear_error()
            print(f"BMO: {response}")

        except TranscriptionError as error:
            if not self._shutdown_event.is_set():
                message = f"Whisper: {error}"
                self.state.set_error(message)
                print(message)

        except AIError as error:
            if not self._shutdown_event.is_set():
                message = f"AI: {error}"
                self.state.set_error(message)
                self.state.set_last_bmo_response("—")
                print(message)

        except Exception as error:
            # Protect the application from unexpected library-level errors.
            if not self._shutdown_event.is_set():
                message = f"Unexpected interaction error: {error}"
                self.state.set_error(message)
                print(message)

        finally:
            if not self._shutdown_event.is_set():
                self.enter_idle()

    def _send_expression(self, expression: BMOExpression) -> bool:
        """Send one expression command to the ESP32."""

        command = f"EXPRESSION:{expression.value}"
        return self.connection.send_line(command)

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
