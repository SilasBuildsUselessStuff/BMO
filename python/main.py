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
    OLLAMA_MAX_TOOL_ROUNDS,
    OLLAMA_MODEL,
    OLLAMA_TEMPERATURE,
    OLLAMA_TIMEOUT,
    SERIAL_PORT,
    SERIAL_TIMEOUT,
    TTS_BMO_PRONUNCIATION,
    TTS_RATE,
    TTS_VOICE_NAME,
    TTS_VOLUME,
    WEATHER_DEFAULT_LOCATION,
    WEATHER_FORECAST_URL,
    WEATHER_GEOCODING_URL,
    WEATHER_LOCATION_ALIASES,
    WEATHER_TIMEOUT,
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_HOTWORDS,
    WHISPER_INITIAL_PROMPT,
    WHISPER_LANGUAGE,
    WHISPER_MODEL,
    WINDOW_HEIGHT,
    WINDOW_TITLE,
    WINDOW_WIDTH,
)
from core.assistant import BMOAssistant
from core.state import BMOState
from core.tools import ToolRegistry
from services.weather import OpenMeteoWeatherService
from services.weather_tool import CurrentWeatherTool
from ui.app import BMOApp
from voice.listener import MicrophoneListener
from voice.tts import WindowsTTS
from voice.whisper import WhisperTranscriber


def main() -> None:
    """Create and run the BMO Companion development application."""

    state = BMOState()

    connection = BMOConnection(
        port=SERIAL_PORT,
        baudrate=BAUDRATE,
        timeout=SERIAL_TIMEOUT,
    )

    listener = MicrophoneListener(
        sample_rate=AUDIO_SAMPLE_RATE,
        channels=AUDIO_CHANNELS,
        dtype=AUDIO_DTYPE,
        device=AUDIO_INPUT_DEVICE,
    )

    transcriber = WhisperTranscriber(
        model_name=WHISPER_MODEL,
        device=WHISPER_DEVICE,
        compute_type=WHISPER_COMPUTE_TYPE,
        language=WHISPER_LANGUAGE,
        initial_prompt=WHISPER_INITIAL_PROMPT,
        hotwords=WHISPER_HOTWORDS,
    )

    # Services retrieve data. Tools expose selected services to the AI.
    weather_service = OpenMeteoWeatherService(
        geocoding_url=WEATHER_GEOCODING_URL,
        forecast_url=WEATHER_FORECAST_URL,
        timeout=WEATHER_TIMEOUT,
    )

    tool_registry = ToolRegistry()
    tool_registry.register(
        CurrentWeatherTool(
            weather_service=weather_service,
            default_location=WEATHER_DEFAULT_LOCATION,
            location_aliases=WEATHER_LOCATION_ALIASES,
        ).definition()
    )

    ai_client = OllamaClient(
        base_url=OLLAMA_BASE_URL,
        model=OLLAMA_MODEL,
        system_prompt=BMO_SYSTEM_PROMPT,
        timeout=OLLAMA_TIMEOUT,
        keep_alive=OLLAMA_KEEP_ALIVE,
        temperature=OLLAMA_TEMPERATURE,
        max_tokens=OLLAMA_MAX_TOKENS,
        tool_registry=tool_registry,
        max_tool_rounds=OLLAMA_MAX_TOOL_ROUNDS,
    )

    tts = WindowsTTS(
        voice_name=TTS_VOICE_NAME,
        rate=TTS_RATE,
        volume=TTS_VOLUME,
        bmo_pronunciation=TTS_BMO_PRONUNCIATION,
    )

    assistant = BMOAssistant(
        state=state,
        connection=connection,
        listener=listener,
        transcriber=transcriber,
        ai_client=ai_client,
        tts=tts,
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

    assistant.start()

    try:
        root.mainloop()
    finally:
        assistant.stop()


if __name__ == "__main__":
    main()
