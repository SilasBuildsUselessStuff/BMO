"""Central state model for the BMO Companion App."""

from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from enum import Enum
from threading import RLock


class BMOScreen(str, Enum):
    """Screens that BMO may eventually display."""

    FACE = "FACE"
    WEATHER = "WEATHER"
    SPOTIFY = "SPOTIFY"
    TODO = "TODO"
    CLOCK = "CLOCK"
    GAMES = "GAMES"
    CHANCE = "CHANCE"
    ANIMATION = "ANIMATION"
    SETTINGS = "SETTINGS"
    LOW_BATTERY_SCREEN = "LOW_BATTERY_SCREEN"
    SYSTEM_INFORMATION = "SYSTEM_INFORMATION"
    NOTIFICATION_SCREEN = "NOTIFICATION_SCREEN"


class BMOExpression(str, Enum):
    """Expressions available to BMO."""

    HAPPY = "HAPPY"
    IDLE = "IDLE"

    SLEEPY = "SLEEPY"
    THINKING = "THINKING"
    LISTENING = "LISTENING"
    HYPED = "HYPED"

    SAD = "SAD"
    CONCERNED = "CONCERNED"
    ANGRY = "ANGRY"
    SURPRISED = "SURPRISED"
    DETECTIVE = "DETECTIVE"
    MUSIC_ENJOYING = "MUSIC_ENJOYING"

    TALKING = "TALKING"
    LOW_BATTERY = "LOW_BATTERY"
    CONFUSED = "CONFUSED"
    SLEEPING = "SLEEPING"


class BMOStatus(str, Enum):
    """Current activity of the Companion App."""

    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    TALKING = "talking"


# Larger numbers represent more important expressions.
EXPRESSION_PRIORITIES = {
    BMOExpression.HAPPY: 1,
    BMOExpression.IDLE: 1,

    BMOExpression.SLEEPY: 2,
    BMOExpression.THINKING: 2,
    BMOExpression.LISTENING: 2,
    BMOExpression.HYPED: 2,

    BMOExpression.SAD: 3,
    BMOExpression.CONCERNED: 3,
    BMOExpression.ANGRY: 3,
    BMOExpression.SURPRISED: 3,
    BMOExpression.DETECTIVE: 3,
    BMOExpression.MUSIC_ENJOYING: 3,

    BMOExpression.TALKING: 4,
    BMOExpression.LOW_BATTERY: 4,
    BMOExpression.CONFUSED: 4,
    BMOExpression.SLEEPING: 4,
}


@dataclass(frozen=True)
class BMOStateSnapshot:
    """Read-only copy of BMO's current state."""

    screen: BMOScreen
    expression: BMOExpression
    status: BMOStatus

    connected: bool
    listening: bool
    thinking: bool
    speaking: bool

    last_user_input: str
    last_bmo_response: str
    error_message: str
    display_type: str
    display_data: dict[str, Any]


class BMOState:
    """
    Thread-safe central application state.

    Tkinter runs on the main thread, while serial communication and Whisper
    use worker threads. Every state read and write therefore uses a lock.
    """

    def __init__(self) -> None:
        self._lock = RLock()

        self._screen = BMOScreen.FACE
        self._expression = BMOExpression.IDLE
        self._status = BMOStatus.IDLE

        self._connected = False
        self._listening = False
        self._thinking = False
        self._speaking = False

        self._last_user_input = "—"
        self._last_bmo_response = "—"
        self._error_message = ""

            # Structured data produced by tools. This will eventually drive both
        # the development GUI and the physical BMO display.
        self._display_type = ""
        self._display_data: dict[str, Any] = {}

    def set_connected(self, connected: bool) -> None:
        """Update the ESP32 connection state."""

        with self._lock:
            self._connected = connected

    def set_screen(self, screen: BMOScreen) -> None:
        """Change the active BMO screen."""

        with self._lock:
            self._screen = screen

    def set_expression(
        self,
        expression: BMOExpression,
        force: bool = False,
    ) -> bool:
        """
        Attempt to change BMO's expression.

        Unless force is True, an expression cannot replace one with a higher
        priority.
        """

        with self._lock:
            current_priority = EXPRESSION_PRIORITIES[self._expression]
            new_priority = EXPRESSION_PRIORITIES[expression]

            if not force and new_priority < current_priority:
                return False

            self._expression = expression
            return True

    def set_last_user_input(self, text: str) -> None:
        """Store the latest recognized user speech."""

        with self._lock:
            self._last_user_input = text

    def set_last_bmo_response(self, text: str) -> None:
        """Store BMO's latest response for future AI integration."""

        with self._lock:
            self._last_bmo_response = text

    def set_error(self, message: str) -> None:
        """Store a recoverable application error."""

        with self._lock:
            self._error_message = message

    def clear_error(self) -> None:
        """Remove the current application error."""

        with self._lock:
            self._error_message = ""

    def set_tool_display(
        self,
        display_type: str,
        display_data: dict[str, Any],
    ) -> None:
        """
        Store structured information produced by a tool.

        If the display type matches a known BMO screen, that screen becomes
        active. The data is copied so callers cannot modify central state
        without acquiring the state lock.
        """

        cleaned_type = display_type.strip().upper()

        with self._lock:
            self._display_type = cleaned_type
            self._display_data = deepcopy(display_data)

            try:
                self._screen = BMOScreen(cleaned_type)
            except ValueError:
                # Unknown future display types may still be stored and shown
                # by the development GUI.
                pass

    def clear_tool_display(self) -> None:
        """Clear the latest structured tool result and return to FACE."""

        with self._lock:
            self._display_type = ""
            self._display_data = {}
            self._screen = BMOScreen.FACE
    
    def enter_idle(self) -> None:
        """Return BMO to its normal idle state."""

        with self._lock:
            self._expression = BMOExpression.IDLE
            self._status = BMOStatus.IDLE

            self._listening = False
            self._thinking = False
            self._speaking = False

    def enter_listening(self) -> None:
        """Put BMO into its listening state."""

        with self._lock:
            self._expression = BMOExpression.LISTENING
            self._status = BMOStatus.LISTENING

            self._listening = True
            self._thinking = False
            self._speaking = False

    def enter_thinking(self) -> None:
        """Put BMO into its thinking state."""

        with self._lock:
            self._expression = BMOExpression.THINKING
            self._status = BMOStatus.THINKING

            self._listening = False
            self._thinking = True
            self._speaking = False

    def enter_talking(self) -> None:
        """Put BMO into its talking state for future TTS support."""

        with self._lock:
            self._expression = BMOExpression.TALKING
            self._status = BMOStatus.TALKING

            self._listening = False
            self._thinking = False
            self._speaking = True

    def snapshot(self) -> BMOStateSnapshot:
        """Return a consistent, read-only state copy."""

        with self._lock:
            return BMOStateSnapshot(
                screen=self._screen,
                expression=self._expression,
                status=self._status,
                connected=self._connected,
                listening=self._listening,
                thinking=self._thinking,
                speaking=self._speaking,
                last_user_input=self._last_user_input,
                last_bmo_response=self._last_bmo_response,
                error_message=self._error_message,
                display_type=self._display_type,
                display_data=deepcopy(self._display_data),
            )
