"""Central configuration for the BMO Companion App."""

# Serial connection
SERIAL_PORT = "COM3"
BAUDRATE = 115200
SERIAL_TIMEOUT = 0.2

# BMO identity
BMO_NAME = "BMO"

# Physical BMO display dimensions
BMO_WIDTH = 480
BMO_HEIGHT = 320

# Development GUI dimensions
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
WINDOW_TITLE = "BMO Companion App - Development"

# PC microphone recording
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1
AUDIO_DTYPE = "float32"

# None uses the default Windows input device.
AUDIO_INPUT_DEVICE = None
