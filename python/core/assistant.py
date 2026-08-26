"""Controller connecting BMO state with serial communication."""

from communication.serial import BMOConnection
from core.state import BMOExpression, BMOState


class BMOAssistant:
    """
    Coordinate BMO's state and physical ESP32 connection.

    The GUI should ask this controller to perform actions instead of changing
    the state or sending serial commands directly. This keeps the GUI separate
    from the application logic.
    """

    def __init__(
        self,
        state: BMOState,
        connection: BMOConnection,
    ) -> None:
        self.state = state
        self.connection = connection

        # Serial callbacks run in the serial background thread.
        # They only update thread-safe state or print debug messages.
        self.connection.on_connection_change = self._on_connection_change
        self.connection.on_message = self._on_serial_message

    def start(self) -> None:
        """Start the connection to the physical BMO."""

        self.connection.start()

    def stop(self) -> None:
        """Stop communication and cleanly disconnect from BMO."""

        self.connection.stop()
        self.state.set_connected(False)

    def toggle_listening(self) -> None:
        """Toggle BMO between IDLE and LISTENING."""

        snapshot = self.state.snapshot()

        if snapshot.listening:
            self.enter_idle()
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

    def _send_expression(self, expression: BMOExpression) -> bool:
        """
        Send an expression command to the ESP32.

        The local state still changes if the ESP32 is unavailable. This allows
        the Companion App to be developed and tested without connected
        hardware.
        """

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

            # Synchronize the ESP32 with the Companion App's current state.
            current_expression = self.state.snapshot().expression
            self._send_expression(current_expression)
        else:
            print("BMO serial connection is disconnected.")

    def _on_serial_message(self, message: str) -> None:
        """
        Handle a message received from the ESP32.

        V0.1 logs incoming messages for debugging. Structured event handling
        will be added later when the ESP32 protocol moves toward JSON.
        """

      //.\.venv\Scripts\python.exe -c "from core.state import BMOState; from core.assistant import BMOAssistant; from communication.serial import BMOConnection; state = BMOState(); connection = BMOConnection('COM99', 115200); assistant = BMOAssistant(state, connection); print(state.snapshot()); assistant.toggle_listening(); print(state.snapshot()); assistant.toggle_listening(); print(state.snapshot())"

  //.\.venv\Scripts\python.exe -c "import time; from config import SERIAL_PORT, BAUDRATE, SERIAL_TIMEOUT; from core.state import BMOState; from core.assistant import BMOAssistant; from communication.serial import BMOConnection; state = BMOState(); connection = BMOConnection(SERIAL_PORT, BAUDRATE, SERIAL_TIMEOUT); assistant = BMOAssistant(state, connection); assistant.start(); time.sleep(2); print('Initial:', state.snapshot()); assistant.toggle_listening(); print('Listening:', state.snapshot()); time.sleep(2); assistant.toggle_listening(); print('Idle:', state.snapshot()); time.sleep(2); assistant.stop()"

        

        print(f"ESP32: {message}")
