"""Entry point for the BMO Companion App."""

import tkinter as tk

from communication.serial import BMOConnection
from config import (
    BAUDRATE,
    SERIAL_PORT,
    SERIAL_TIMEOUT,
    WINDOW_HEIGHT,
    WINDOW_TITLE,
    WINDOW_WIDTH,
)
from core.assistant import BMOAssistant
from core.state import BMOState
from ui.app import BMOApp


def main() -> None:
    """Create and run the BMO Companion development application."""

    # Central state shared by the controller and GUI.
    state = BMOState()

    # Serial communication remains independent from the GUI.
    connection = BMOConnection(
        port=SERIAL_PORT,
        baudrate=BAUDRATE,
        timeout=SERIAL_TIMEOUT,
    )

    # The assistant coordinates state transitions and serial commands.
    assistant = BMOAssistant(
        state=state,
        connection=connection,
    )

    root = tk.Tk()
    root.title(WINDOW_TITLE)
    root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
    root.minsize(600, 450)

    def close_application() -> None:
        """Cleanly stop the serial worker before closing the window."""

        assistant.stop()
        root.destroy()

    BMOApp(
        master=root,
        state=state,
        assistant=assistant,
        on_close=close_application,
    )

    # start() returns immediately because serial work occurs in its own thread.
    assistant.start()

    try:
        root.mainloop()
    finally:
        # Also clean up if Tkinter exits through an unexpected path.
        assistant.stop()


if __name__ == "__main__":
    main()


//.\.venv\Scripts\python.exe -c "from ui.app import BMOApp; from core.assistant import BMOAssistant; from communication.serial import BMOConnection; print('All modules loaded successfully')"

//.\.venv\Scripts\python.exe main.py
  
