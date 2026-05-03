from __future__ import annotations
import customtkinter as ctk
from . import theme


class _Modal(ctk.CTkToplevel):
    """Base class for all blocking modal dialogs."""

    def __init__(
        self, parent_widget, title: str, width: int = 380, height: int = 230
    ) -> None:
        root = parent_widget.winfo_toplevel()
        super().__init__(root)
        self.title(title)
        self.resizable(False, False)
        self.configure(fg_color=theme.BG_MAIN)
        self.result = None

        # Size first so update_idletasks can compute position
        self.geometry(f"{width}x{height}")
        self.update_idletasks()
        rx = root.winfo_x() + root.winfo_width() // 2 - width // 2
        ry = root.winfo_y() + root.winfo_height() // 2 - height // 2
        self.geometry(f"{width}x{height}+{max(0, rx)}+{max(0, ry)}")

        self.transient(root)

    def _wait(self):
        self.grab_set()
        self.wait_window(self)
        return self.result


class _ProcessDialog(_Modal):
    def __init__(self, parent_widget) -> None:
        super().__init__(parent_widget, "ADD PROCESS", 380, 220)

        ctk.CTkLabel(
            self, text="ADD PROCESS",
            font=theme.font(16, bold=True), text_color=theme.NEON,
        ).pack(pady=(22, 4))

        self._name_var = ctk.StringVar()
        entry = ctk.CTkEntry(
            self, textvariable=self._name_var,
            placeholder_text="Process name...",
            font=theme.font(12),
            fg_color=theme.BG_INPUT, border_color=theme.BORDER,
            text_color=theme.TEXT, corner_radius=0, height=36,
        )
        entry.pack(padx=32, fill="x", pady=6)
        entry.focus()
        entry.bind("<Return>", lambda _e: self._ok())

        self._err = ctk.CTkLabel(self, text="", text_color=theme.NEON_RED,
                                 font=theme.font(9))
        self._err.pack()

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=8)
        ctk.CTkButton(
            row, text="ADD", width=110, corner_radius=0,
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
        name = self._name_var.get().strip()
        if not name:
            self._err.configure(text="Name cannot be empty.")
            return
        self.result = name
        self.destroy()


class _TaskDialog(_Modal):
    def __init__(self, parent_widget) -> None:
        super().__init__(parent_widget, "ADD TASK", 380, 290)

        ctk.CTkLabel(
            self, text="ADD TASK",
            font=theme.font(16, bold=True), text_color=theme.NEON,
        ).pack(pady=(18, 4))

        self._name_var = ctk.StringVar()
        self._time_var = ctk.StringVar(value="1")

        ctk.CTkLabel(self, text="Task name", font=theme.font(9),
                     text_color=theme.TEXT_DIM).pack(anchor="w", padx=32)
        name_entry = ctk.CTkEntry(
            self, textvariable=self._name_var,
            placeholder_text="e.g. Mix, Bake, Pack...",
            font=theme.font(12), fg_color=theme.BG_INPUT,
            border_color=theme.BORDER, text_color=theme.TEXT,
            corner_radius=0, height=34,
        )
        name_entry.pack(padx=32, fill="x", pady=(0, 6))
        name_entry.focus()

        ctk.CTkLabel(self, text="Processing time (cycles)", font=theme.font(9),
                     text_color=theme.TEXT_DIM).pack(anchor="w", padx=32)
        ctk.CTkEntry(
            self, textvariable=self._time_var,
            font=theme.font(12), fg_color=theme.BG_INPUT,
            border_color=theme.BORDER, text_color=theme.TEXT,
            corner_radius=0, height=34,
        ).pack(padx=32, fill="x", pady=(0, 4))

        self._err = ctk.CTkLabel(self, text="", text_color=theme.NEON_RED,
                                 font=theme.font(9))
        self._err.pack()

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=6)
        ctk.CTkButton(
            row, text="ADD", width=110, corner_radius=0,
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
        name = self._name_var.get().strip()
        if not name:
            self._err.configure(text="Name cannot be empty.")
            return
        try:
            t = int(self._time_var.get())
            if t < 1:
                raise ValueError
        except ValueError:
            self._err.configure(text="Time must be a positive integer.")
            return
        self.result = (name, t)
        self.destroy()


class _ProductCountDialog(_Modal):
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
        try:
            n = int(self._count_var.get())
            if n < 1:
                raise ValueError
        except ValueError:
            self._err.configure(text="Enter a positive integer.")
            return
        self.result = n
        self.destroy()


# ── Public helpers ────────────────────────────────────────────────────────────

def ask_process_name(widget) -> str | None:
    return _ProcessDialog(widget)._wait()


def ask_task_details(widget) -> tuple[str, int] | None:
    return _TaskDialog(widget)._wait()


def ask_product_count(widget) -> int | None:
    return _ProductCountDialog(widget)._wait()
