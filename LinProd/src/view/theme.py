from __future__ import annotations
import pathlib
import pyglet
from customtkinter import CTkFont


# ── Paths ───────────────────────────────────────────────────────────

ASSETS_DIR = pathlib.Path(__file__).parent.parent.parent / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"

# System default font — no custom TTF loaded
FONT_FAMILY: str = "TkDefaultFont"

# Logo asset resolved relative to this file (LinProd/src/view/ → LinProd/assets/)
LOGO_PATH: pathlib.Path = (
    pathlib.Path(__file__).resolve().parent.parent.parent / "assets" / "LOGO.png"
)
BG_IMAGE_PATH: pathlib.Path = (
    pathlib.Path(__file__).resolve().parent.parent.parent / "assets" / "background.png"
)


# ── Registrar fuentes ───────────────────────────────────────────────

FONT_FILES = [
    "TRYToshA-Black-BF677df27a667c8.ttf",
    "TRYToshA-Bold-BF677df27a68b37.ttf",
    "TRYToshA-Light-BF677df27a6a41e.ttf",
    "TRYToshA-Medium-BF677df27a6785d.ttf",
    "TRYToshA-Regular-BF677df27a66806.ttf",
    "TRYToshA-Thin-BF677df27a67374.ttf",

    "TRYToshB-Black-BF677df279930bb.ttf",
    "TRYToshB-Bold-BF677df279b315e.ttf",
    "TRYToshB-Light-BF677df27a54b9d.ttf",
    "TRYToshB-Medium-BF677df27a667bb.ttf",
    "TRYToshB-Regular-BF677df27a4c491.ttf",
    "TRYToshB-Thin-BF677df27a680ff.ttf",
]

for font_file in FONT_FILES:
    pyglet.font.add_file(str(FONTS_DIR / font_file))

# ── Familias ────────────────────────────────────────────────────────

FONT_BLACK   = "Try Tosh A Black"
FONT_BOLD    = "Try Tosh A Bold"
FONT_MEDIUM  = "Try Tosh A Medium"
FONT_REGULAR = "Try Tosh A Regular"
FONT_LIGHT   = "Try Tosh A Light"
FONT_THIN    = "Try Tosh A Thin"

# ── Palette ───────────────────────────────────────────────────────────────────
BG_MAIN    = "#090918"
BG_PANEL   = "#0d0d2b"
BG_ROW     = "#111133"
BG_INPUT   = "#0a0a22"
NEON       = "#a8a8a8"
NEON_BLUE  = "#00cfff"
NEON_RED   = "#ff3f5a"
NEON_AMBER = "#ffb300"
BORDER     = "#1e2d5e"
BORDER_LIT = "#2a4080"
TEXT       = "#e8e8ff"
TEXT_DIM   = "#7c7e81"

# ── Colores del nuevo diseño (imagen 2) ──────────────────────────────────────
# Panel semitransparente oscuro para las secciones
_PANEL_BG   = "#0d1b2a"       # azul muy oscuro casi negro
_PANEL_BD   = "#1e3a5f"       # borde azul sutil
_BTN_ADD    = "#1a2f4a"       # botón +add oscuro
_BTN_ADD_H  = "#243d5e"       # hover
_BTN_SIM    = "#1a2f4a"       # start simulation
_BTN_SIM_H  = "#243d5e"
_TEXT_MAIN  = "#e8f4fd"       # blanco azulado
_TEXT_DIM2  = "#8ab4d4"       # texto tenue azulado
_TITLE_BIG  = "#ffffff"       # títulos grandes
_ACCENT     = "#4a9eca"       # azul accent para íconos


# ── TTK scrollbar style names (registered in main.py) ─────────────────────────
H_SCROLL = "Arcade.Horizontal.TScrollbar"
V_SCROLL = "Arcade.Vertical.TScrollbar"


def font(
    size: int = 12,
    weight: str | None = None,
    bold: bool = False,
    family: str | None = None,
):
    """
    Flexible font helper.

    Examples:
        theme.font(14)
        theme.font(14, bold=True)
        theme.font(14, "bold")
        theme.font(20, family=theme.FONT_BLACK)
    """

    # Compatibilidad con theme.font(14, "bold")
    if isinstance(weight, str):
        weight_value = weight
    else:
        weight_value = "bold" if bold else "normal"

    # Elegir familia automáticamente
    if family is None:
        if weight_value == "bold":
            family = FONT_BOLD
        else:
            family = FONT_REGULAR

    return CTkFont(
        family=family,
        size=size,
        weight=weight_value,
    )
