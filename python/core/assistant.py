"""Controller connecting BMO state, voice, and serial communication."""

from threading import Event, RLock, Thread
from typing import Optional

import numpy as np

from communication.serial import BMOConnection
from core.state import BMOExpression, BMOState
from voice.listener import MicrophoneError, MicrophoneListener
from voice.whisper import TranscriptionError, WhisperTranscriber


class BMOAssistant:
    """
    Coordinate BMO's state, voice components, and physical ESP32 connection.

    Slow Whisper transcription is performed in a worker thread so it cannot
    freeze the Tkinter GUI.
    """

    def __init__(
        self,
        state: BMOState,
        connection: BMOConnection,
        listener: Optional[MicrophoneListener] = None,
        transcriber: Optional[WhisperTranscriber] = None,
    ) -> None:
        self.state = state
        self.connection = connection
        self.listener = listener
        self.transcriber = transcriber

        self._voice_lock = RLock()
        self._transcription_thread: Optional[Thread] = None
        self._shutdown_event = Event()

        # Serial callbacks execute in the serial background thread.
        self.connection.on_connection_change = self._on_connection_change
        self.connection.on_message = self._on_serial_message

    def start(self) -> None:
        """Start the connection to the physical BMO."""

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
        Start or stop the voice interaction.

        If voice components have not been supplied, this retains the original
        V0.1 state-only behavior.
        """

        snapshot = self.state.snapshot()

        # Do not start another interaction while Whisper is working.
        if snapshot.thinking:
            return

        if snapshot.listening:
            if self._voice_is_configured():
                self._stop_listening_and_transcribe()
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
        """Return whether both required V0.2 voice components exist."""

        return self.listener is not None and self.transcriber is not None

    def _start_listening(self) -> None:
        """Start PC microphone recording."""

        if self.listener is None:
            return

        with self._voice_lock:
            if self.listener.is_recording:
                return

            self.state.clear_error()

            try:
                self.listener.start_recording()
            except MicrophoneError as error:
                self.state.set_error(str(error))
                self.enter_idle()
                return

            self.enter_listening()

    def _stop_listening_and_transcribe(self) -> None:
        """Stop microphone recording and begin transcription."""

        if self.listener is None or self.transcriber is None:
            self.enter_idle()
            return

        with self._voice_lock:
            try:
                audio = self.listener.stop_recording()
            except MicrophoneError as error:
                self.state.set_error(str(error))
                self.enter_idle()
                return

            self.enter_thinking()

            self._transcription_thread = Thread(
                target=self._transcribe_audio,
                args=(audio,),
                name="BMO-Whisper",
                daemon=True,
            )
            self._transcription_thread.start()

    def _transcribe_audio(self, audio: np.ndarray) -> None:
        """
        Transcribe recorded audio in a background worker.

        This function must not manipulate Tkinter widgets directly. It only
        updates the thread-safe central state.
        """

        if self.transcriber is None:
            self.state.set_error("Whisper transcriber is not configured.")
            self.enter_idle()
            return

        try:
            transcript = self.transcriber.transcribe(audio)

            if self._shutdown_event.is_set():
                return

            if transcript:
                self.state.set_last_user_input(transcript)
                self.state.clear_error()
                print(f"You: {transcript}")
            else:
                self.state.set_last_user_input("—")
                self.state.set_error("No speech was detected.")
                print("Whisper: No speech was detected.")

        except TranscriptionError as error:
            if not self._shutdown_event.is_set():
                self.state.set_error(str(error))
                print(f"Whisper error: {error}")

        except Exception as error:
            # Protect the application from unexpected library-level errors.
            if not self._shutdown_event.is_set():
                message = f"Unexpected transcription error: {error}"
                self.state.set_error(message)
                print(message)

        finally:
            if not self._shutdown_event.is_set():
                self.enter_idle()

    def _send_expression(self, expression: BMOExpression) -> bool:
        """Send one expression command to the physical ESP32."""

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

            current_expression = self.state.snapshot().expression
            self._send_expression(current_expression)
        else:
            print("BMO serial connection is disconnected.")

    def _on_serial_message(self, message: str) -> None:
        """Log incoming ESP32 messages during development."""

        print(f"ESP32: {message}")

//.\.venv\Scripts\python.exe -c "from core.assistant import BMOAssistant; from core.state import BMOState; print('Voice controller loaded successfully')"
