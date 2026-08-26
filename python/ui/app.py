"""Tkinter development interface for the BMO Companion App."""

import tkinter as tk
from tkinter import ttk
from typing import Callable

from config import BMO_NAME
from core.assistant import BMOAssistant
from core.state import BMOExpression, BMOState, BMOStateSnapshot


class BMOApp(ttk.Frame):
    """
    Development and debugging interface for BMO.

    This GUI represents the Windows Companion App, not the 480x320 display
    shown on the physical BMO.
    """

    UPDATE_INTERVAL_MS = 100

    def __init__(
        self,
        master: tk.Tk,
        state: BMOState,
        assistant: BMOAssistant,
        on_close: Callable[[], None],
    ) -> None:
        super().__init__(master, padding=20)

        self.master = master
        self.state = state
        self.assistant = assistant
        self.on_close = on_close

        self._closing = False

        # Tkinter variables make it easy to update labels.
        self.face_text = tk.StringVar(value="^_^")
        self.status_text = tk.StringVar(value="idle")
        self.expression_text = tk.StringVar(value="IDLE")
        self.connection_text = tk.StringVar(value="DISCONNECTED")
        self.serial_error_text = tk.StringVar(value="")
        self.user_input_text = tk.StringVar(value="—")
        self.bmo_response_text = tk.StringVar(value="—")
        self.listen_button_text = tk.StringVar(value="LISTEN")

        self._configure_styles()
        self._build_layout()

        # Closing through the window's X button follows the same cleanup path.
        self.master.protocol("WM_DELETE_WINDOW", self._handle_close)

        # Poll the thread-safe state regularly. Tkinter widgets are only
        # updated here on the main GUI thread.
        self.after(self.UPDATE_INTERVAL_MS, self._refresh_from_state)

    def _configure_styles(self) -> None:
        """Configure the visual style of the development GUI."""

        style = ttk.Style(self.master)

        style.configure(
            "Title.TLabel",
            font=("Segoe UI", 22, "bold"),
        )
        style.configure(
            "Face.TLabel",
            font=("Consolas", 54, "bold"),
            anchor="center",
        )
        style.configure(
            "Section.TLabel",
            font=("Segoe UI", 11, "bold"),
        )
        style.configure(
            "Value.TLabel",
            font=("Segoe UI", 11),
        )
        style.configure(
            "Listen.TButton",
            font=("Segoe UI", 12, "bold"),
            padding=(20, 10),
        )

    def _build_layout(self) -> None:
        """Create all visible GUI elements."""

        self.pack(fill="both", expand=True)

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        title_label = ttk.Label(
            self,
            text=BMO_NAME,
            style="Title.TLabel",
        )
        title_label.grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 10),
        )

        content = ttk.Frame(self, padding=15)
        content.grid(
            row=1,
            column=0,
            sticky="nsew",
        )

        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)

        face_label = ttk.Label(
            content,
            textvariable=self.face_text,
            style="Face.TLabel",
        )
        face_label.grid(
            row=0,
            column=0,
            sticky="nsew",
            pady=(5, 20),
        )

        information = ttk.Frame(content)
        information.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=20,
        )

        information.columnconfigure(1, weight=1)

        self._add_information_row(
            information,
            row=0,
            label="Status:",
            value_variable=self.status_text,
        )
        self._add_information_row(
            information,
            row=1,
            label="Expression:",
            value_variable=self.expression_text,
        )
        self._add_information_row(
            information,
            row=2,
            label="Connection:",
            value_variable=self.connection_text,
        )

        serial_error_label = ttk.Label(
            information,
            textvariable=self.serial_error_text,
            foreground="#a04040",
            wraplength=550,
        )
        serial_error_label.grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(5, 10),
        )

        conversation = ttk.LabelFrame(
            content,
            text="Conversation",
            padding=12,
        )
        conversation.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=20,
            pady=(15, 15),
        )

        conversation.columnconfigure(1, weight=1)

        self._add_information_row(
            conversation,
            row=0,
            label="You:",
            value_variable=self.user_input_text,
        )
        self._add_information_row(
            conversation,
            row=1,
            label="BMO:",
            value_variable=self.bmo_response_text,
        )

        button_frame = ttk.Frame(content)
        button_frame.grid(
            row=3,
            column=0,
            pady=(5, 5),
        )

        listen_button = ttk.Button(
            button_frame,
            textvariable=self.listen_button_text,
            command=self._toggle_listening,
            style="Listen.TButton",
        )
        listen_button.pack()

    @staticmethod
    def _add_information_row(
        parent: ttk.Frame,
        row: int,
        label: str,
        value_variable: tk.StringVar,
    ) -> None:
        """Add one label/value row to a frame."""

        label_widget = ttk.Label(
            parent,
            text=label,
            style="Section.TLabel",
        )
        label_widget.grid(
            row=row,
            column=0,
            sticky="nw",
            padx=(0, 12),
            pady=3,
        )

        value_widget = ttk.Label(
            parent,
            textvariable=value_variable,
            style="Value.TLabel",
            wraplength=550,
        )
        value_widget.grid(
            row=row,
            column=1,
            sticky="nw",
            pady=3,
        )

    def _toggle_listening(self) -> None:
        """Handle the LISTEN button without performing blocking work."""

        self.assistant.toggle_listening()

    def _refresh_from_state(self) -> None:
        """
        Refresh GUI values from the central state.

        Serial callbacks run in a background thread and must never manipulate
        Tkinter widgets directly. Reading a state snapshot here keeps all GUI
        work safely on Tkinter's main thread.
        """

        if self._closing:
            return

        snapshot = self.state.snapshot()

        self.status_text.set(snapshot.status.value)
        self.expression_text.set(snapshot.expression.value)

        if snapshot.connected:
            self.connection_text.set("CONNECTED")
            self.serial_error_text.set("")
        else:
            self.connection_text.set("DISCONNECTED")

            error = self.assistant.connection.last_error
            if error:
                self.serial_error_text.set(f"Serial: {error}")
            else:
                self.serial_error_text.set("")

        if snapshot.listening:
            self.listen_button_text.set("STOP LISTENING")
        else:
            self.listen_button_text.set("LISTEN")

        self.face_text.set(self._face_for_expression(snapshot))

        self.after(self.UPDATE_INTERVAL_MS, self._refresh_from_state)

    @staticmethod
    def _face_for_expression(snapshot: BMOStateSnapshot) -> str:
        """Return a simple debug face for the current expression."""

        faces = {
            BMOExpression.IDLE: "^_^",
            BMOExpression.HAPPY: "^‿^",
            BMOExpression.LISTENING: "O_O",
            BMOExpression.THINKING: "o_O",
            BMOExpression.TALKING: "^o^",
            BMOExpression.SLEEPY: "-_-",
            BMOExpression.SLEEPING: "u_u",
            BMOExpression.SURPRISED: "O_O",
            BMOExpression.CONFUSED: "?_?",
            BMOExpression.SAD: "T_T",
            BMOExpression.ANGRY: ">_<",
        }

        return faces.get(snapshot.expression, "^_^")

    def _handle_close(self) -> None:
        """Prevent duplicate close operations."""

        if self._closing:
            return

        self._closing = True
        self.on_close()
