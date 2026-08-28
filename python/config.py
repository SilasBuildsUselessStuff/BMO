"""Central configuration for the BMO Companion App."""

# ---------------------------------------------------------------------------
# Serial connection
# ---------------------------------------------------------------------------

SERIAL_PORT = "COM3"
BAUDRATE = 115200
SERIAL_TIMEOUT = 0.2


# ---------------------------------------------------------------------------
# BMO identity
# ---------------------------------------------------------------------------

BMO_NAME = "BMO"


# ---------------------------------------------------------------------------
# Display dimensions
# ---------------------------------------------------------------------------

# Physical BMO display
BMO_WIDTH = 480
BMO_HEIGHT = 320

# Development GUI
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
WINDOW_TITLE = "BMO Companion App - Development"


# ---------------------------------------------------------------------------
# PC microphone recording
# ---------------------------------------------------------------------------

AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1
AUDIO_DTYPE = "float32"

# None uses the default Windows input device.
AUDIO_INPUT_DEVICE = None


# ---------------------------------------------------------------------------
# Local Whisper speech recognition
# ---------------------------------------------------------------------------

WHISPER_MODEL = "base.en"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"
WHISPER_LANGUAGE = "en"

# These hints help Whisper recognize the unusual name "BMO".
WHISPER_INITIAL_PROMPT = (
    "This is a conversation with BMO, a small robot companion. "
    "The robot's name is pronounced Beemo and spelled BMO."
)

WHISPER_HOTWORDS = "BMO, Beemo"


# ---------------------------------------------------------------------------
# Local AI through Ollama
# ---------------------------------------------------------------------------

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "qwen2.5:7b"
OLLAMA_TIMEOUT = 120.0
OLLAMA_KEEP_ALIVE = "10m"

# Response generation
OLLAMA_TEMPERATURE = 0.7
OLLAMA_MAX_TOKENS = 120


# ---------------------------------------------------------------------------
# Local Windows text-to-speech
# ---------------------------------------------------------------------------

# None uses the default Windows SAPI voice.
TTS_VOICE_NAME = None

# Windows SAPI rate range is approximately -10 to 10.
TTS_RATE = 1

# Volume range is 0 to 100.
TTS_VOLUME = 100

# Text displayed in the GUI remains "BMO", while text sent to the speech
# engine temporarily uses "Beemo" so it does not say "B M O".
TTS_BMO_PRONUNCIATION = "Beemo"

# ---------------------------------------------------------------------------
# Online services
# ---------------------------------------------------------------------------

WEATHER_GEOCODING_URL = (
    "https://geocoding-api.open-meteo.com/v1/search"
)
WEATHER_FORECAST_URL = (
    "https://api.open-meteo.com/v1/forecast"
)
WEATHER_TIMEOUT = 10.0

# Used if no location is supplied.
WEATHER_DEFAULT_LOCATION = "Höpfingen, Germany"
WEATHER_DEFAULT_POSTAL_CODE = "74746"

# Canonical queries for known ambiguous location names.
WEATHER_LOCATION_ALIASES = {
    "palma de mallorca": "Palma, Spain",
    "palma, mallorca": "Palma, Spain",
    "höpfingen": "Höpfingen, Germany",
    "74746": "Höpfingen, Germany",
}
