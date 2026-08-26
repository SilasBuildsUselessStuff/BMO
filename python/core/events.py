"""Hardware-independent events understood by the BMO application."""

from enum import Enum


class BMOEvent(str, Enum):
    """
    Events that may come from hardware, the GUI, or simulated input.

    Keeping these events hardware-independent means that a keyboard key can
    simulate an event now, while a physical sensor can produce the same event
    later without changing the application logic.
    """

    BUTTON_PRESS = "BUTTON_PRESS"
    BUTTON_LONGPRESS = "BUTTON_LONGPRESS"
    TOUCH = "TOUCH"

    BATTERY_LOW = "BATTERY_LOW"
    BATTERY_CHARGING = "BATTERY_CHARGING"

    MUSIC_STARTED = "MUSIC_STARTED"
    MUSIC_STOPPED = "MUSIC_STOPPED"

    VOICE_DETECTED = "VOICE_DETECTED"
    WAKE = "WAKE"
    SLEEP_TIMER = "SLEEP_TIMER"

    SHAKE = "SHAKE"
    TILT = "TILT"
    PICKUP = "PICKUP"

    NOTIFICATION = "NOTIFICATION"
    COMPUTER_DISCONNECTED = "COMPUTER_DISCONNECTED"
