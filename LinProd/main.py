from __future__ import annotations
import pathlib
import tkinter as tk
import tkinter.ttk as ttk

import customtkinter as ctk
import src.view.theme as _theme
from src.controller.main_controller import MainController


def _setup_ttk_styles() -> None:
    style = ttk.Style()
    style.theme_use("default")
    _sb = dict(
        background=_theme.BORDER,
        troughcolor=_theme.BG_PANEL,
        arrowcolor=_theme.NEON,
        borderwidth=0,
        relief="flat",
        gripcount=0,
    )
    style.configure(_theme.H_SCROLL, **_sb, sliderlength=30)
    style.configure(_theme.V_SCROLL, **_sb)
    style.map(_theme.H_SCROLL, background=[("active", _theme.BORDER_LIT)])
    style.map(_theme.V_SCROLL, background=[("active", _theme.BORDER_LIT)])


def _set_window_icon(root: ctk.CTk) -> None:
    if not _theme.LOGO_PATH.exists():
        return
    try:
        # tk.PhotoImage handles PNG natively in Tk 8.6+
        _icon = tk.PhotoImage(file=str(_theme.LOGO_PATH))
        root.iconphoto(True, _icon)
        root._icon_ref = _icon  # prevent GC
    except Exception:
        try:
            from PIL import Image, ImageTk
            _img = ImageTk.PhotoImage(Image.open(_theme.LOGO_PATH))
            root.iconphoto(True, _img)
            root._icon_ref = _img
        except Exception:
            pass


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("LinProd — Production Line Simulator")
    root.geometry("1280x720")
    root.minsize(1920, 1080)
    root.configure(fg_color=_theme.BG_MAIN)

    _setup_ttk_styles()
    _set_window_icon(root)

    app = MainController(root)
    app.start_setup()

    root.mainloop()
