"""
main.py
-------
Application entry point for LinProd — Production Line Simulator.

Responsibilities:
  1. Configure CustomTkinter's global appearance (dark mode, blue colour theme).
  2. Register custom TTK scrollbar styles used by the canvas-based views.
  3. Set the window icon with a graceful fallback chain (Tk 8.6 → PIL → skip).
  4. Instantiate the root CTk window and hand it to MainController, which
     bootstraps the full MVC stack and transitions into the setup phase.
  5. Enter the Tk main event loop.

Startup sequence:
  ctk.CTk (root)
    └─ _setup_ttk_styles()      — register H_SCROLL / V_SCROLL style names
    └─ _set_window_icon()       — load LOGO.png into the OS title bar
    └─ MainController(root)     — wires EventDispatcher, ProductionLine,
    |                             SimulationEngine, SetupController,
    |                             SimulationController, and all views
    └─ app.start_setup()        — show SetupView (phase 1)
    └─ root.mainloop()          — block until the window is closed

Relationships:
  Owns:    ctk.CTk root window
  Creates: MainController (which owns the rest of the object graph)
  Imports: theme (for colour constants and scrollbar style names)
"""

from __future__ import annotations
import pathlib
import tkinter as tk
import tkinter.ttk as ttk

import customtkinter as ctk
import src.view.theme as _theme
from src.controller.main_controller import MainController


def _setup_ttk_styles() -> None:
    """
    Register the custom TTK scrollbar styles used by SetupView and SimulationView.

    CustomTkinter does not style native TTK widgets, so the scrollbars that wrap
    the canvas regions are registered manually here via ``ttk.Style``.  The style
    names (``_theme.H_SCROLL``, ``_theme.V_SCROLL``) are the single source of
    truth — views reference those constants directly rather than hard-coding names.

    The "default" TTK theme is activated first to provide a clean baseline before
    overrides are applied.
    """
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
    """
    Load LOGO.png as the OS title-bar / taskbar icon for the root window.

    Two-path approach:
      1. ``tk.PhotoImage`` — handles PNG natively in Tk 8.6+.  Preferred because
         it avoids an optional Pillow dependency.
      2. ``PIL.ImageTk.PhotoImage`` — fallback for environments where Tk's built-in
         PNG support is unavailable (rare, but possible on some Linux builds).

    If both paths fail the icon is silently skipped; the app still runs normally.

    The loaded image object is stored on ``root._icon_ref`` to prevent Python's
    garbage collector from freeing it while the window is open — without this pin,
    Tkinter keeps only a C-level reference which is invisible to the GC.

    Parameters
    ----------
    root : ctk.CTk
        The application's root window; receives ``iconphoto()`` and the GC-pin
        attribute ``_icon_ref``.
    """
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
    # ── Global CTk appearance ─────────────────────────────────────────────────
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    # ── Root window ───────────────────────────────────────────────────────────
    root = ctk.CTk()
    root.title("LinProd — Production Line Simulator")
    root.geometry("1280x720")   # initial size; user may resize freely
    root.minsize(1300, 800)     # guard against layouts breaking at small sizes
    root.configure(fg_color=_theme.BG_MAIN)

    # ── Pre-MainController setup ──────────────────────────────────────────────
    _setup_ttk_styles()   # must run before any view creates a scrollbar
    _set_window_icon(root)

    # ── Bootstrap MVC stack and enter setup phase ─────────────────────────────
    app = MainController(root)
    app.start_setup()     # renders SetupView and waits for user configuration

    # ── Hand control to the Tk event loop (blocks until the window is closed) ─
    root.mainloop()
