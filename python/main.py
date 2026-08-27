"""Entry point for the BMO Companion App."""

import tkinter as tk

from ai.client import OllamaClient
from ai.personality import BMO_SYSTEM_PROMPT
from communication.serial import BMOConnection
from config import (
    AUDIO_CHANNELS,
    AUDIO_DTYPE,
    AUDIO_INPUT_DEVICE,
    AUDIO_SAMPLE_RATE,
    BAUDRATE,
    OLLAMA_BASE_URL,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_MAX_TOKENS,
    OLLAMA_MODEL,
    OLLAMA_TEMPERATURE,
    OLLAMA_TIMEOUT,
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

    # Central thread-safe application state.
    state = BMOState()

    # Non-blocking USB serial connection to the ESP32.
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

    # Local Whisper speech-to-text model.
    transcriber = WhisperTranscriber(
        model_name=WHISPER_MODEL,
        device=WHISPER_DEVICE,
        compute_type=WHISPER_COMPUTE_TYPE,
        language=WHISPER_LANGUAGE,
    )

    # Provider-independent AI implementation backed by local Ollama.
    ai_client = OllamaClient(
        base_url=OLLAMA_BASE_URL,
        model=OLLAMA_MODEL,
        system_prompt=BMO_SYSTEM_PROMPT,
        timeout=OLLAMA_TIMEOUT,
        keep_alive=OLLAMA_KEEP_ALIVE,
        temperature=OLLAMA_TEMPERATURE,
        max_tokens=OLLAMA_MAX_TOKENS,
    )

    # Coordinator for serial, microphone, Whisper, AI, and state.
    assistant = BMOAssistant(
        state=state,
        connection=connection,
        listener=listener,
        transcriber=transcriber,
        ai_client=ai_client,
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

    # Serial communication runs in its background worker.
    assistant.start()

    try:
        root.mainloop()
    finally:
        # Also clean up after an unexpected exit from Tkinter.
        assistant.stop()


if __name__ == "__main__":
    main()
