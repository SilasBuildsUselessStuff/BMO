"""Entry point for the BMO Companion App."""

import tkinter as tk

from communication.serial import BMOConnection
from config import (
    AUDIO_CHANNELS,
    AUDIO_DTYPE,
    AUDIO_INPUT_DEVICE,
    AUDIO_SAMPLE_RATE,
    BAUDRATE,
    SERIAL_PORT,
    SERIAL_TIMEOUT,
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_LANGUAGE,
    WHISPER_MODEL,
    WINDOW_HEIGHT,
    WINDOW_TITLE,
    WINDOW_WIDTH,
)
from core.assistant import BMOAssistant
from core.state import BMOState
from ui.app import BMOApp
from voice.listener import MicrophoneListener
from voice.whisper import WhisperTranscriber


def main() -> None:
    """Create and run the BMO Companion development application."""

    # Central thread-safe state shared by the controller and GUI.
    state = BMOState()

    # Non-blocking USB serial communication with the ESP32.
    connection = BMOConnection(
        port=SERIAL_PORT,
        baudrate=BAUDRATE,
        timeout=SERIAL_TIMEOUT,
    )

    # PC microphone recorder.
    listener = MicrophoneListener(
        sample_rate=AUDIO_SAMPLE_RATE,
        channels=AUDIO_CHANNELS,
        dtype=AUDIO_DTYPE,
        device=AUDIO_INPUT_DEVICE,
    )

    # Local speech-to-text model. The model is loaded lazily during the first
    # transcription, so application startup remains quick.
    transcriber = WhisperTranscriber(
        model_name=WHISPER_MODEL,
        device=WHISPER_DEVICE,
        compute_type=WHISPER_COMPUTE_TYPE,
        language=WHISPER_LANGUAGE,
    )

    # The assistant coordinates state, serial communication, recording,
    # and background transcription.
    assistant = BMOAssistant(
        state=state,
        connection=connection,
        listener=listener,
        transcriber=transcriber,
    )

    root = tk.Tk()
    root.title(WINDOW_TITLE)
    root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
    root.minsize(600, 450)

    def close_application() -> None:
        """Cleanly stop voice and serial resources before exiting."""

        assistant.stop()
        root.destroy()

    BMOApp(
        master=root,
        state=state,
        assistant=assistant,
        on_close=close_application,
    )

    # Serial work occurs in a background thread.
    assistant.start()

    try:
        root.mainloop()
    finally:
        # This also covers unexpected exits from the Tkinter event loop.
        assistant.stop()


if __name__ == "__main__":
    main()

  
