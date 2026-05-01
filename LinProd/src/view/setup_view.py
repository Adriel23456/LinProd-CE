from __future__ import annotations
from typing import Callable
import customtkinter as ctk


class SetupView(ctk.CTkFrame):
    def __init__(self, parent, on_confirm: Callable) -> None:
        super().__init__(parent)
        self._on_confirm = on_confirm
        self._build()

    def _build(self) -> None:
        ctk.CTkLabel(self, text="Production Line Setup", font=("Arial", 20, "bold")).pack(pady=16)
        # TODO: process/task form widgets

    def render_process_form(self) -> None:
        pass  # TODO

    def render_task_list(self, processes) -> None:
        pass  # TODO

    def render_line_preview(self, processes) -> None:
        pass  # TODO

    def show_validation_error(self, msg: str) -> None:
        ctk.CTkLabel(self, text=msg, text_color="red").pack()