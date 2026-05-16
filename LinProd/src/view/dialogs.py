"""
dialogs.py
----------
Blocking modal dialogs used by SetupView and SimulationView.

All dialogs in this module follow the same pattern:
  1. Subclass _Modal, which centres the window over the root and sets the
     standard dark background.
  2. Build the UI in __init__.
  3. Call _wait() which calls grab_set() + wait_window() to block the caller
     until the user confirms or cancels.
  4. Store the validated result in self.result; _wait() returns it.

Public API — three module-level helpers wrap the private dialog classes:
  ask_process_name(widget) → str | None
  ask_task_details(widget)  → tuple[str, int] | None
  ask_product_count(widget) → int | None

These are the only symbols that view code should import from this module.
The private _Modal / _ProcessDialog / _TaskDialog / _ProductCountDialog classes
are implementation details and should not be instantiated directly.
"""

from __future__ import annotations
import customtkinter as ctk
from . import theme


class _Modal(ctk.CTkToplevel):
    """
    Abstract base class for all blocking modal dialogs in LinProd.

    Centres itself over the root window, enforces a fixed size, and applies
    the standard dark background from theme.BG_MAIN. Subclasses build their
    UI in __init__ and call _wait() to block until the dialog is dismissed.

    Attributes
    ----------
    result : Any
        Set by the subclass's _ok() method to the validated user input.
        Remains None if the user cancels or closes the window.
    """

    def __init__(
        self, parent_widget, title: str, width: int = 380, height: int = 230
    ) -> None:
        """
        Parameters
        ----------
        parent_widget : tk.Widget
            Any widget whose root window is used as the transient parent.
        title : str
            Window title shown in the OS title bar.
        width : int
            Fixed dialog width in pixels.
        height : int
            Fixed dialog height in pixels.
        """
        root = parent_widget.winfo_toplevel()
        super().__init__(root)
        self.title(title)
        self.resizable(False, False)
        self.configure(fg_color=theme.BG_MAIN)
        self.result = None

        # Size first so update_idletasks can compute position
        self.geometry(f"{width}x{height}")
        self.update_idletasks()
        # Centre over the root window
        rx = root.winfo_x() + root.winfo_width() // 2 - width // 2
        ry = root.winfo_y() + root.winfo_height() // 2 - height // 2
        self.geometry(f"{width}x{height}+{max(0, rx)}+{max(0, ry)}")

        self.transient(root)

    def _wait(self):
        """
        Block until the dialog is dismissed and return the result.

        Grabs all events (preventing interaction with the parent window),
        then enters the Tk event loop until this window is destroyed.

        Returns
        -------
        Any
            self.result as set by the subclass's _ok() method, or None if
            the user closed/cancelled without confirming.
        """
        self.grab_set()
        self.wait_window(self)
        return self.result


class _ProcessDialog(_Modal):
    """
    Modal dialog for creating a new Process.

    Prompts the user for a process name (non-empty string). Pressing Enter
    or clicking "add" validates and closes the dialog with the name as result.
    """

    def __init__(self, parent_widget) -> None:
        super().__init__(parent_widget, "ADD PROCESS", 380, 220)

        ctk.CTkLabel(
            self,
            text="add process",
            font=theme.font(18, bold=True),
            text_color=theme._TEXT_MAIN,
        ).pack(pady=(22, 10))

        self._name_var = ctk.StringVar()

        entry = ctk.CTkEntry(
            self,
            textvariable=self._name_var,
            placeholder_text="Process name...",
            font=theme.font(12),

            # colores
            fg_color=theme._BTN_ADD,
            border_color=theme._PANEL_BD,
            text_color=theme._TEXT_MAIN,
            placeholder_text_color=theme._TEXT_DIM2,

            # rounded
            corner_radius=12,
            border_width=1,
            height=42,
        )
        entry.pack(padx=32, fill="x", pady=6)

        entry.focus()
        entry.bind("<Return>", lambda _e: self._ok())

        self._err = ctk.CTkLabel(
            self,
            text="",
            text_color=theme.NEON_RED,
            font=theme.font(9),
        )
        self._err.pack(pady=(4, 0))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=14)

        # ADD BUTTON
        ctk.CTkButton(
            row,
            text="add",
            width=120,
            height=40,

            corner_radius=12,

            fg_color=theme._BTN_ADD,
            hover_color=theme._BTN_ADD_H,

            border_width=1,
            border_color=theme._PANEL_BD,

            text_color=theme._TEXT_MAIN,
            font=theme.font(12, bold=True),

            command=self._ok,
        ).pack(side="left", padx=8)

        # CANCEL BUTTON
        ctk.CTkButton(
            row,
            text="cancel",
            width=120,
            height=40,

            corner_radius=12,

            fg_color="transparent",
            hover_color=theme._PANEL_BG,

            border_width=1,
            border_color=theme._PANEL_BD,

            text_color=theme._TEXT_MAIN,
            font=theme.font(11, bold=True),

            command=self.destroy,
        ).pack(side="left", padx=8)

    def _ok(self) -> None:
        """Validate the name entry and close with the result, or show an error."""
        name = self._name_var.get().strip()

        if not name:
            self._err.configure(text="Name cannot be empty.")
            return

        self.result = name
        self.destroy()


class _TaskDialog(_Modal):
    """
    Modal dialog for adding a Task to a Process.

    Collects both a task name (non-empty string) and a processing time
    (positive integer, representing simulation cycles). Returns a
    (name, processing_time) tuple as the result.
    """

    def __init__(self, parent_widget) -> None:
        super().__init__(parent_widget, "ADD TASK", 400, 320)

        ctk.CTkLabel(
            self,
            text="add task",
            font=theme.font(18, bold=True),
            text_color=theme._TEXT_MAIN,
        ).pack(pady=(20, 10))

        self._name_var = ctk.StringVar()
        self._time_var = ctk.StringVar(value="1")

        # ---------- TASK NAME ----------
        ctk.CTkLabel(
            self,
            text="Task name",
            font=theme.font(10, bold=True),
            text_color=theme._TEXT_DIM2,
        ).pack(anchor="w", padx=32)

        name_entry = ctk.CTkEntry(
            self,
            textvariable=self._name_var,
            placeholder_text="e.g. Mix, Bake, Pack...",
            font=theme.font(12),

            fg_color=theme._BTN_ADD,
            border_color=theme._PANEL_BD,
            border_width=1,

            text_color=theme._TEXT_MAIN,
            placeholder_text_color=theme._TEXT_DIM2,

            corner_radius=12,
            height=42,
        )
        name_entry.pack(padx=32, fill="x", pady=(4, 12))

        name_entry.focus()

        # ---------- TIME ----------
        ctk.CTkLabel(
            self,
            text="Processing time (cycles)",
            font=theme.font(10, bold=True),
            text_color=theme._TEXT_DIM2,
        ).pack(anchor="w", padx=32)

        time_entry = ctk.CTkEntry(
            self,
            textvariable=self._time_var,
            font=theme.font(12),

            fg_color=theme._BTN_ADD,
            border_color=theme._PANEL_BD,
            border_width=1,

            text_color=theme._TEXT_MAIN,

            corner_radius=12,
            height=42,
        )
        time_entry.pack(padx=32, fill="x", pady=(4, 10))

        self._err = ctk.CTkLabel(
            self,
            text="",
            text_color=theme.NEON_RED,
            font=theme.font(9),
        )
        self._err.pack()

        # ---------- BUTTON ROW ----------
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=14)

        # ADD BUTTON
        ctk.CTkButton(
            row,
            text="add",
            width=120,
            height=40,

            corner_radius=12,

            fg_color=theme._BTN_ADD,
            hover_color=theme._BTN_ADD_H,

            border_width=1,
            border_color=theme._PANEL_BD,

            text_color=theme._TEXT_MAIN,
            font=theme.font(12, bold=True),

            command=self._ok,
        ).pack(side="left", padx=8)

        # CANCEL BUTTON
        ctk.CTkButton(
            row,
            text="cancel",
            width=120,
            height=40,

            corner_radius=12,

            fg_color="transparent",
            hover_color=theme._PANEL_BG,

            border_width=1,
            border_color=theme._PANEL_BD,

            text_color=theme._TEXT_MAIN,
            font=theme.font(11, bold=True),

            command=self.destroy,
        ).pack(side="left", padx=8)

    def _ok(self) -> None:
        """Validate both fields and close with (name, time) tuple, or show an error."""
        name = self._name_var.get().strip()

        if not name:
            self._err.configure(text="Name cannot be empty.")
            return

        try:
            t = int(self._time_var.get())

            if t < 1:
                raise ValueError

        except ValueError:
            self._err.configure(
                text="Time must be a positive integer."
            )
            return

        self.result = (name, t)
        self.destroy()


class _ProductCountDialog(_Modal):
    """
    Modal dialog for specifying how many products to inject at simulation start.

    Accepts a non-negative integer (0 = run continuously until manually stopped).
    Returns the count as an int result.
    """

    def __init__(self, parent_widget) -> None:
        super().__init__(parent_widget, "START SIMULATION", 380, 240)

        ctk.CTkLabel(
            self, text="START SIMULATION",
            font=theme.font(16, bold=True), text_color=theme.NEON,
        ).pack(pady=(22, 2))
        ctk.CTkLabel(
            self, text="How many products to simulate?",
            font=theme.font(10), text_color=theme.TEXT_DIM,
        ).pack(pady=(0, 6))

        self._count_var = ctk.StringVar(value="3")
        entry = ctk.CTkEntry(
            self, textvariable=self._count_var,
            font=theme.font(14, bold=True), justify="center",
            fg_color=theme.BG_INPUT, border_color=theme.BORDER,
            text_color=theme.NEON, corner_radius=0, height=40,
        )
        entry.pack(padx=64, fill="x", pady=4)
        entry.focus()
        entry.bind("<Return>", lambda _e: self._ok())

        self._err = ctk.CTkLabel(self, text="", text_color=theme.NEON_RED,
                                 font=theme.font(9))
        self._err.pack()

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=8)
        ctk.CTkButton(
            row, text="▶  START", width=130, corner_radius=0,
            fg_color=theme.NEON, text_color=theme.BG_MAIN,
            hover_color="#00cc7a", font=theme.font(12, bold=True),
            command=self._ok,
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            row, text="CANCEL", width=110, corner_radius=0,
            fg_color="transparent", text_color=theme.TEXT_DIM,
            border_width=1, border_color=theme.BORDER,
            hover_color=theme.BG_PANEL, font=theme.font(11),
            command=self.destroy,
        ).pack(side="left", padx=6)

    def _ok(self) -> None:
        """Validate the count entry and close with the integer result, or show an error."""
        try:
            n = int(self._count_var.get())
            if n < 0:
                raise ValueError
        except ValueError:
            self._err.configure(text="Enter a positive integer or 0.")
            return
        self.result = n
        self.destroy()


# ── Public helpers ────────────────────────────────────────────────────────────

def ask_process_name(widget) -> str | None:
    """
    Open a blocking modal dialog to collect a process name from the user.

    Parameters
    ----------
    widget : tk.Widget
        Any widget in the application; used to locate the root window for
        transient parenting and screen-centre calculation.

    Returns
    -------
    str | None
        The validated non-empty process name, or None if the user cancelled.
    """
    return _ProcessDialog(widget)._wait()


def ask_task_details(widget) -> tuple[str, int] | None:
    """
    Open a blocking modal dialog to collect task name and processing time.

    Parameters
    ----------
    widget : tk.Widget
        Any widget in the application.

    Returns
    -------
    tuple[str, int] | None
        A (name, processing_time) pair where processing_time is a positive
        integer (simulation cycles), or None if the user cancelled.
    """
    return _TaskDialog(widget)._wait()


def ask_product_count(widget) -> int | None:
    """
    Open a blocking modal dialog to ask how many products to simulate.

    Parameters
    ----------
    widget : tk.Widget
        Any widget in the application.

    Returns
    -------
    int | None
        A non-negative integer product count, or None if the user cancelled.
    """
    return _ProductCountDialog(widget)._wait()
