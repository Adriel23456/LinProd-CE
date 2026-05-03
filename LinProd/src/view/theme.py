from __future__ import annotations
import pathlib

# System default font — no custom TTF loaded
FONT_FAMILY: str = "TkDefaultFont"

# Logo asset resolved relative to this file (LinProd/src/view/ → LinProd/assets/)
LOGO_PATH: pathlib.Path = (
    pathlib.Path(__file__).resolve().parent.parent.parent / "assets" / "LOGO.png"
)

# ── Palette ───────────────────────────────────────────────────────────────────
BG_MAIN    = "#090918"
BG_PANEL   = "#0d0d2b"
BG_ROW     = "#111133"
BG_INPUT   = "#0a0a22"
NEON       = "#00ff9f"
NEON_BLUE  = "#00cfff"
NEON_RED   = "#ff3f5a"
NEON_AMBER = "#ffb300"
BORDER     = "#1e2d5e"
BORDER_LIT = "#2a4080"
TEXT       = "#e8e8ff"
TEXT_DIM   = "#6677aa"

# ── TTK scrollbar style names (registered in main.py) ─────────────────────────
H_SCROLL = "Arcade.Horizontal.TScrollbar"
V_SCROLL = "Arcade.Vertical.TScrollbar"


def font(size: int = 12, bold: bool = False) -> tuple:
    """Return a Tkinter font tuple using the system default font."""
    return (FONT_FAMILY, size, "bold" if bold else "normal")
