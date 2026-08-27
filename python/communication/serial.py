"""Non-blocking serial communication with the physical BMO."""

from collections.abc import Callable
from threading import Event, RLock, Thread, current_thread
from typing import Optional

import serial as pyserial
from serial import SerialException


# These callback types keep the communication layer independent from the GUI.
MessageCallback = Callable[[str], None]
ConnectionCallback = Callable[[bool], None]


class BMOConnection:
    """
    Manage the USB serial connection to the ESP32.

    Connecting and receiving happen in a background thread. This prevents
    serial operations from blocking Tkinter's GUI thread.

    The first version makes one connection attempt when start() is called.
    Automatic reconnection can be added later.
    """

    def __init__(
        self,
        port: str,
        baudrate: int,
        timeout: float = 0.2,
        on_message: Optional[MessageCallback] = None,
        on_connection_change: Optional[ConnectionCallback] = None,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout

        self.on_message = on_message
        self.on_connection_change = on_connection_change

        self._serial: Optional[pyserial.Serial] = None
        self._thread: Optional[Thread] = None

        self._stop_event = Event()
        self._connection_lock = RLock()
        self._write_lock = RLock()

        self._connected = False
        self._last_error: Optional[str] = None

    @property
    def is_connected(self) -> bool:
        """Return whether the ESP32 serial connection is currently active."""

        with self._connection_lock:
            return self._connected

    @property
    def last_error(self) -> Optional[str]:
        """Return the latest serial error, if one occurred."""

        with self._connection_lock:
            return self._last_error

    def start(self) -> None:
        """
        Start the serial worker thread.

        This method returns immediately. The connection attempt itself happens
        in the background.
        """

        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = Thread(
            target=self._serial_worker,
            name="BMO-Serial",
            daemon=True,
        )
        self._thread.start()

        def stop(self) -> None:
        """
        Stop the serial worker and close the serial port.

        The worker thread owns the serial connection and closes it in its
        finally block. Because readline() uses a short timeout, setting the
        stop event is enough to let the worker exit without another thread
        closing the same Windows handle concurrently.
        """

        self._stop_event.set()

        thread = self._thread

        if (
            thread is not None
            and thread.is_alive()
            and thread is not current_thread()
        ):
            thread.join(timeout=max(1.0, self.timeout + 0.5))

        self._thread = None
        self._set_connected(False)

    def send_line(self, message: str) -> bool:
        """
        Send one newline-terminated message to the ESP32.

        Returns True when the message was written successfully.
        Returns False if BMO is disconnected or writing fails.
        """

        message = message.strip()

        if not message:
            return False

        with self._connection_lock:
            connection = self._serial
            connected = self._connected

        if not connected or connection is None or not connection.is_open:
            return False

        try:
            encoded_message = f"{message}\n".encode("utf-8")

            with self._write_lock:
                connection.write(encoded_message)
                connection.flush()

            return True

        except (SerialException, OSError) as error:
            self._record_error(error)
            self._set_connected(False)

            # Let the serial worker close its own connection.
            self._stop_event.set()
            return False

    def _serial_worker(self) -> None:
        """Connect to the ESP32 and receive messages until stopped."""

        try:
            connection = pyserial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
            )

            with self._connection_lock:
                self._serial = connection
                self._last_error = None

            self._set_connected(True)

            while not self._stop_event.is_set():
                raw_line = connection.readline()

                if not raw_line:
                    continue

                message = raw_line.decode(
                    "utf-8",
                    errors="replace",
                ).strip()

                if message:
                    self._notify_message(message)

        except (SerialException, OSError) as error:
            # This includes COM3 not existing, being busy, or disconnecting.
            self._record_error(error)

        finally:
            with self._connection_lock:
                connection = self._serial
                self._serial = None

            if connection is not None:
                try:
                    connection.close()
                except (SerialException, OSError):
                    pass

            self._set_connected(False)

    def _set_connected(self, connected: bool) -> None:
        """Update connection state and notify the application if it changed."""

        with self._connection_lock:
            changed = self._connected != connected
            self._connected = connected

        if changed and self.on_connection_change is not None:
            try:
                self.on_connection_change(connected)
            except Exception as error:
                # A faulty callback must not kill the serial worker.
                print(f"Serial connection callback error: {error}")

    def _notify_message(self, message: str) -> None:
        """Pass an incoming ESP32 message to the application."""

        if self.on_message is None:
            return

        try:
            self.on_message(message)
        except Exception as error:
            # A faulty callback must not kill the serial worker.
            print(f"Serial message callback error: {error}")

    def _record_error(self, error: Exception) -> None:
        """Store an error so that the GUI can display or log it later."""

        with self._connection_lock:
            self._last_error = str(error)


// .\.venv\Scripts\python.exe -c "from communication.serial import BMOConnection; print('Serial module loaded successfully')"
// .\.venv\Scripts\python.exe -c "import time; from communication.serial import BMOConnection; connection = BMOConnection('COM99', 115200); connection.start(); time.sleep(1); print('Connected:', connection.is_connected); print('Error:', connection.last_error); connection.stop(); print('Program finished normally')"
// .\.venv\Scripts\python.exe -c "import time; from config import SERIAL_PORT, BAUDRATE, SERIAL_TIMEOUT; from communication.serial import BMOConnection; connection = BMOConnection(SERIAL_PORT, BAUDRATE, SERIAL_TIMEOUT); connection.start(); time.sleep(2); print('Connected:', connection.is_connected); print('Error:', connection.last_error); connection.stop(); print('Connection closed')"
// .\.venv\Scripts\python.exe -c "import time; from config import SERIAL_PORT, BAUDRATE, SERIAL_TIMEOUT; from communication.serial import BMOConnection; connection = BMOConnection(SERIAL_PORT, BAUDRATE, SERIAL_TIMEOUT, on_message=lambda message: print('BMO:', message), on_connection_change=lambda connected: print('Connected:', connected)); connection.start(); time.sleep(2); print('PING sent:', connection.send_line('PING')); time.sleep(2); connection.stop()"
