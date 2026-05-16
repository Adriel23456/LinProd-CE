"""
setup_view.py
-------------
Production-line configuration screen (Setup phase).

SetupView is a CTkFrame that fills the root window during the setup phase.
It provides the entire UI for building the production line before simulation:
  - Left column  : app branding, JSON load/save buttons.
  - Right column : process tiles (scrollable horizontal strip), task list,
                   canvas line-preview, and footer confirm button.

Key design patterns used here:
  - Deferred rendering: structural changes to the process tiles or preview
    canvas are batched via after_idle() (see _schedule_tiles_rebuild and
    _schedule_preview_redraw) so rapid successive mutations only trigger
    one redraw per event loop iteration.
  - Fast recolor: when only the selection changes (no add/remove), only
    border colours are updated (_refresh_tile_colors) without destroying and
    recreating tiles.
  - Canvas scrollregion: both the process-tiles canvas and the line-preview
    canvas maintain correct scrollregion values via _sync_proc_tiles_scrollregion
    and the scrollregion=(0,0,W,content_h) pattern.

Relationships:
    - Created by: MainController.start_setup()
    - Controller set after creation: SetupController (via view.controller = ...)
    - Calls into: SetupController.on_*() methods for all user actions
    - Uses: dialogs.ask_process_name(), dialogs.ask_task_details() for input
"""

from __future__ import annotations
import math
import tkinter as tk
import tkinter.ttk as ttk
from typing import TYPE_CHECKING, Callable
from tkinter import filedialog, messagebox
import customtkinter as ctk

from . import theme
from . import dialogs

if TYPE_CHECKING:
    from src.controller.setup_controller import SetupController
    from src.model.process import Process


def _load_logo(parent, size: tuple[int, int] = (40, 40)) -> ctk.CTkLabel | None:
    """
    Create a CTkLabel containing the LOGO.png asset, or return None if unavailable.

    Uses PIL/Pillow to open the PNG and wraps it in a CTkImage so CustomTkinter
    can display it at the requested size without pixelation. A strong reference
    to the image is stored on the label (_logo_img) to prevent garbage collection.

    Parameters
    ----------
    parent : ctk.CTkWidget
        The parent widget for the label.
    size : tuple[int, int]
        Desired (width, height) in pixels for the displayed image.

    Returns
    -------
    ctk.CTkLabel | None
        A label ready to be packed/gridded, or None if PIL is not installed
        or the logo file does not exist.
    """
    if not theme.LOGO_PATH.exists():
        return None
    try:
        from PIL import Image
        img = ctk.CTkImage(
            light_image=Image.open(theme.LOGO_PATH),
            dark_image=Image.open(theme.LOGO_PATH),
            size=size,
        )
        lbl = ctk.CTkLabel(parent, image=img, text="")
        lbl._logo_img = img   # prevent GC of the CTkImage reference
        return lbl
    except Exception:
        return None


class SetupView(ctk.CTkFrame):
    """
    Production-line configuration interface shown during the Setup phase.

    Layout: two-column grid inside the root window.
      Left column  — app branding (title card, credits) and JSON I/O.
      Right column — process tiles, task list, line preview, confirm button.

    The view is intentionally stateless with respect to the model: it reads
    data from the controller on every render call and does not cache model
    objects. The only mutable state it owns is UI-selection state
    (_selected_proc) and deferred-render flags.

    Diagram attributes (V-CD-06):
        process_form : CTkFrame           — process-tiles section container
        task_list    : CTkScrollableFrame — horizontal task strip
        line_canvas  : tk.Canvas          — snake-pattern line preview

    Relationships:
        - Created by: MainController.start_setup()
        - Controller injected after creation: SetupController
        - Uses: dialogs.ask_process_name(), dialogs.ask_task_details()
    """

    def __init__(self, parent, on_confirm: Callable) -> None:
        """
        Parameters
        ----------
        parent : ctk.CTk | ctk.CTkFrame
            Root window or parent frame that hosts this view.
        on_confirm : Callable
            Zero-argument callback invoked when the user clicks "start simulation"
            and validation passes. Supplied by MainController.
        """
        super().__init__(parent, fg_color="transparent")
        self.controller:  "SetupController | None" = None
        self._on_confirm: Callable = on_confirm

        # Diagram-required widget attributes (set during _build)
        self.process_form: ctk.CTkFrame             | None = None
        self.task_list:    ctk.CTkScrollableFrame   | None = None
        self.line_canvas:  tk.Canvas                | None = None

        # Currently selected process name (drives task-list display)
        self._selected_proc:  str | None = None
        self._err_label:      ctk.CTkLabel | None = None   # footer error label
        self._sel_label:      ctk.CTkLabel | None = None   # "tasks for: X" label

        # Process-tiles horizontal canvas and its embedded frame
        self._proc_tiles_canvas: tk.Canvas | None = None
        self._proc_tiles_frame:  tk.Frame  | None = None

        # Fast-recolor cache: proc.name → {"tile", "name_lbl", "task_lbl"}
        # Populated by _render_proc_tiles(); used by _refresh_tile_colors()
        self._tile_widgets: dict[str, dict] = {}

        # Deferred-render flags — prevent multiple redraws per event loop tick
        self._preview_redraw_scheduled: bool = False
        self._tiles_rebuild_scheduled:  bool = False

        self._build()

    # ── Canvas drawing helpers ────────────────────────────────────────────────

    def _rounded_rect(self, c, x1, y1, x2, y2, r=10, **kw):
        """
        Draw a filled rounded rectangle on a tk.Canvas using a smooth polygon.

        Parameters
        ----------
        c : tk.Canvas
            Target canvas.
        x1, y1, x2, y2 : int
            Bounding box of the rectangle.
        r : int
            Corner radius in pixels.
        **kw
            Additional keyword arguments forwarded to canvas.create_polygon
            (e.g. fill, outline, width).
        """
        pts = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1, x1 + r, y1,
        ]
        return c.create_polygon(pts, smooth=True, **kw)

    # ── Deferred-render scheduling ────────────────────────────────────────────

    def _schedule_preview_redraw(self) -> None:
        """
        Schedule a preview canvas redraw at the next idle moment.

        Coalesces multiple rapid calls into a single redraw per event loop
        iteration. Safe to call multiple times — only one after_idle is queued.
        """
        if self._preview_redraw_scheduled:
            return
        self._preview_redraw_scheduled = True
        self.after_idle(self._do_preview_redraw)

    def _do_preview_redraw(self) -> None:
        """Execute the deferred preview canvas redraw."""
        self._preview_redraw_scheduled = False
        if self.controller:
            self._update_canvas_preview(self.controller._production_line.processes)

    def _schedule_tiles_rebuild(self) -> None:
        """
        Schedule a full process-tiles rebuild at the next idle moment.

        Coalesces multiple rapid structural changes (add/remove/reorder)
        into a single rebuild per event loop iteration.
        """
        if self._tiles_rebuild_scheduled:
            return
        self._tiles_rebuild_scheduled = True
        self.after_idle(self._do_tiles_rebuild)

    def _do_tiles_rebuild(self) -> None:
        """Execute the deferred full process-tiles rebuild."""
        self._tiles_rebuild_scheduled = False
        self._render_proc_tiles()

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build(self) -> None:
        """
        Construct the full two-column layout and all sub-sections.

        Grid layout:
          column 0 (fixed 300 px) — left panel (branding + JSON I/O)
          column 1 (expandable)   — right panel (processes, tasks, preview, footer)
        """
        self.configure(fg_color=theme.BG_MAIN)

        self.columnconfigure(0, weight=0, minsize=300)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        left_col = ctk.CTkFrame(self, fg_color="transparent")
        left_col.grid(row=0, column=0, sticky="nsew", padx=(24, 12), pady=24)

        right_col = ctk.CTkFrame(self, fg_color="transparent")
        right_col.grid(row=0, column=1, sticky="nsew", padx=(12, 24), pady=24)
        right_col.rowconfigure(0, weight=0)
        right_col.rowconfigure(1, weight=0)
        right_col.rowconfigure(2, weight=1)
        right_col.rowconfigure(3, weight=0)
        right_col.columnconfigure(0, weight=1)

        self._build_left_panel(left_col)
        self._build_process_section_new(right_col)
        self._build_task_section_new(right_col)
        self._build_preview_section_new(right_col)
        self._build_footer_new(right_col)

    # ── Left column ───────────────────────────────────────────────────────────

    def _build_left_panel(self, parent: ctk.CTkFrame) -> None:
        """
        Build the left panel containing branding, credits, and JSON I/O controls.

        Four rows stacked vertically:
          row 0 — credits card (course name + authors)
          row 1 — title card ("production line simulator")
          row 2 — load JSON button
          row 3 — save JSON button

        Parameters
        ----------
        parent : ctk.CTkFrame
            The left-column container frame.
        """
        parent.rowconfigure(0, weight=0)
        parent.rowconfigure(1, weight=0)
        parent.rowconfigure(2, weight=0)
        parent.rowconfigure(3, weight=0)
        parent.columnconfigure(0, weight=1)

        credits_frame = ctk.CTkFrame(
            parent, fg_color=theme._PANEL_BG, corner_radius=14,
            border_width=1, border_color=theme._PANEL_BD,
        )
        credits_frame.grid(row=0, column=0, sticky="ew", pady=(0, 16))

        ctk.CTkLabel(
            credits_frame,
            text="Modelación de hardware y software orientado a objetos",
            font=theme.font(9),
            text_color=theme._TEXT_DIM2,
            wraplength=240,
            justify="center",
        ).pack(pady=(12, 2))

        ctk.CTkLabel(
            credits_frame,
            text="Chaves · Duarte · Madrigal · Molina",
            font=theme.font(10, bold=True),
            text_color=theme._TEXT_MAIN,
            justify="center",
        ).pack(pady=(0, 12))

        title_frame = ctk.CTkFrame(
            parent,
            fg_color=theme._PANEL_BG,
            corner_radius=14,
            border_width=1,
            border_color=theme._PANEL_BD,
            height=365,
            width=300,
        )
        title_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 16))
        title_frame.pack_propagate(False)

        ctk.CTkLabel(
            title_frame,
            text="production\nline",
            font=theme.font(40, family=theme.FONT_BOLD),
            text_color=theme._TITLE_BIG,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(24, 0))
        ctk.CTkLabel(
            title_frame,
            text="simulator",
            font=theme.font(36, family=theme.FONT_BOLD),
            text_color=theme._TEXT_MAIN,
            justify="right",
        ).pack(anchor="w", padx=20, pady=(0, 24))

        load_frame = ctk.CTkFrame(
            parent, fg_color=theme._PANEL_BG, corner_radius=14,
            border_width=1, border_color=theme._PANEL_BD,
        )
        load_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        load_frame.columnconfigure(0, weight=1)

        inner_load = ctk.CTkFrame(load_frame, fg_color="transparent")
        inner_load.pack(fill="x", padx=16, pady=14)
        inner_load.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            inner_load, text="load file",
            font=theme.font(16, bold=True), text_color=theme._TEXT_MAIN,
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            inner_load, text="json",
            font=theme.font(10), text_color=theme._TEXT_DIM2,
        ).grid(row=1, column=0, sticky="w")
        ctk.CTkButton(
            inner_load, text="+", width=40, height=40, corner_radius=10,
            fg_color=theme._BTN_ADD, hover_color=theme._BTN_ADD_H,
            text_color=theme._TEXT_MAIN, font=theme.font(22, bold=True),
            command=self._load_json,
        ).grid(row=0, column=1, rowspan=2, padx=(8, 0))

        save_frame = ctk.CTkFrame(
            parent, fg_color=theme._PANEL_BG, corner_radius=14,
            border_width=1, border_color=theme._PANEL_BD,
        )
        save_frame.grid(row=3, column=0, sticky="ew")

        inner_save = ctk.CTkFrame(save_frame, fg_color="transparent")
        inner_save.pack(fill="x", padx=16, pady=14)
        inner_save.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            inner_save, text="save file",
            font=theme.font(16, bold=True), text_color=theme._TEXT_MAIN,
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            inner_save, text="json",
            font=theme.font(10), text_color=theme._TEXT_DIM2,
        ).grid(row=1, column=0, sticky="w")
        ctk.CTkButton(
            inner_save, text="⬇", width=40, height=40, corner_radius=10,
            fg_color=theme._BTN_ADD, hover_color=theme._BTN_ADD_H,
            text_color=theme._TEXT_MAIN, font=theme.font(18, bold=True),
            command=self._save_json,
        ).grid(row=0, column=1, rowspan=2, padx=(8, 0))

    # ── Right column sections ─────────────────────────────────────────────────

    def _build_process_section_new(self, parent: ctk.CTkFrame) -> None:
        """
        Build the process-tiles section (row 0 of the right column).

        Contains:
          - Header row with "processes" label and "+add process" button.
          - A horizontally scrollable tk.Canvas embedding a tk.Frame that holds
            the individual process tiles. The frame's width drives the scrollregion.

        Parameters
        ----------
        parent : ctk.CTkFrame
            The right-column container frame.
        """
        container = ctk.CTkFrame(
            parent, fg_color=theme._PANEL_BG, corner_radius=14,
            border_width=1, border_color=theme._PANEL_BD,
        )
        container.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.process_form = container

        hdr = ctk.CTkFrame(container, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(12, 4))

        ctk.CTkLabel(
            hdr, text="processes",
            font=theme.font(15, bold=True), text_color=theme._TEXT_MAIN,
        ).pack(side="left")
        ctk.CTkButton(
            hdr, text="+add process", width=130, height=30, corner_radius=10,
            fg_color=theme._BTN_ADD, hover_color=theme._BTN_ADD_H,
            text_color=theme._TEXT_MAIN, font=theme.font(11, bold=True),
            command=self._add_process,
        ).pack(side="right")

        canvas_row = tk.Frame(container, bg=theme._PANEL_BG)
        canvas_row.pack(fill="x", padx=16, pady=(0, 12))

        self._proc_tiles_canvas = tk.Canvas(
            canvas_row, bg=theme._PANEL_BG, height=110, highlightthickness=0,
        )
        self._proc_tiles_canvas.pack(side="top", fill="x")

        h_scroll = ttk.Scrollbar(
            canvas_row, orient="horizontal", style=theme.H_SCROLL,
            command=self._on_proc_tiles_xscroll,
        )
        h_scroll.pack(side="top", fill="x")
        self._proc_tiles_canvas.configure(xscrollcommand=h_scroll.set)

        self._proc_tiles_frame = tk.Frame(self._proc_tiles_canvas, bg=theme._PANEL_BG)
        self._proc_tiles_canvas.create_window(0, 0, anchor="nw",
                                              window=self._proc_tiles_frame)
        self._proc_tiles_frame.bind(
            "<Configure>",
            lambda _e: self._sync_proc_tiles_scrollregion(),
        )
        self._proc_tiles_canvas.bind(
            "<Configure>",
            lambda _e: self._sync_proc_tiles_scrollregion(),
        )

    def _build_task_section_new(self, parent: ctk.CTkFrame) -> None:
        """
        Build the task list section (row 1 of the right column).

        Contains:
          - Header row with "tasks" label and "+add tasks" button.
          - A status label showing which process is currently selected.
          - A horizontal CTkScrollableFrame (self.task_list) holding task tiles.

        Parameters
        ----------
        parent : ctk.CTkFrame
            The right-column container frame.
        """
        container = ctk.CTkFrame(
            parent, fg_color=theme._PANEL_BG, corner_radius=14,
            border_width=1, border_color=theme._PANEL_BD,
        )
        container.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        hdr = ctk.CTkFrame(container, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(12, 4))

        ctk.CTkLabel(
            hdr, text="tasks",
            font=theme.font(15, bold=True), text_color=theme._TEXT_MAIN,
        ).pack(side="left")
        ctk.CTkButton(
            hdr, text="+add tasks", width=120, height=30, corner_radius=10,
            fg_color=theme._BTN_ADD, hover_color=theme._BTN_ADD_H,
            text_color=theme._TEXT_MAIN, font=theme.font(11, bold=True),
            command=self._add_task,
        ).pack(side="right")

        self._sel_label = ctk.CTkLabel(
            container, text="< select a process from above",
            font=theme.font(10), text_color=theme._TEXT_DIM2,
        )
        self._sel_label.pack(anchor="w", padx=16, pady=(0, 4))

        self.task_list = ctk.CTkScrollableFrame(
            container, fg_color="transparent",
            label_text="TASK ORDER",
            label_font=theme.font(10, bold=True),
            label_text_color=theme._TEXT_DIM2,
            scrollbar_fg_color=theme._PANEL_BG,
            scrollbar_button_color=theme._PANEL_BD,
            scrollbar_button_hover_color=theme._BTN_ADD_H,
            height=120,
            orientation="horizontal",
        )
        self.task_list.pack(fill="x", expand=False, padx=12, pady=(0, 12))

    def _build_preview_section_new(self, parent: ctk.CTkFrame) -> None:
        """
        Build the line-preview canvas section (row 2, weight=1, of the right column).

        Contains a vertically scrollable tk.Canvas (self.line_canvas) that renders
        the production line as a snake-pattern diagram of rounded process boxes
        connected by arrows.

        Parameters
        ----------
        parent : ctk.CTkFrame
            The right-column container frame.
        """
        container = ctk.CTkFrame(
            parent, fg_color=theme._PANEL_BG, corner_radius=14,
            border_width=1, border_color=theme._PANEL_BD,
        )
        container.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        container.rowconfigure(1, weight=1)
        container.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            container, text="line preview",
            font=theme.font(14, family=theme.FONT_BOLD), text_color=theme._TEXT_MAIN,
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))

        preview_wrap = tk.Frame(container, bg=theme._PANEL_BG)
        preview_wrap.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        self.line_canvas = tk.Canvas(
            preview_wrap, bg=theme._PANEL_BG, highlightthickness=1,
            highlightbackground=theme._PANEL_BD,
        )
        v_scroll = ttk.Scrollbar(
            preview_wrap, orient="vertical", style=theme.V_SCROLL,
            command=self.line_canvas.yview,
        )
        v_scroll.pack(side="right", fill="y")
        self.line_canvas.pack(side="left", fill="both", expand=True)
        self.line_canvas.configure(yscrollcommand=v_scroll.set)

    def _build_footer_new(self, parent: ctk.CTkFrame) -> None:
        """
        Build the footer row (row 3 of the right column).

        Contains:
          - An error label (left) that shows validation messages in NEON_RED.
          - A "start simulation" button (right) that triggers _confirm().

        Parameters
        ----------
        parent : ctk.CTkFrame
            The right-column container frame.
        """
        footer = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=16)
        footer.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        footer.columnconfigure(0, weight=1)

        self._err_label = ctk.CTkLabel(
            footer, text="", font=theme.font(10), text_color=theme.NEON_RED,
        )
        self._err_label.grid(row=0, column=0, sticky="w", padx=4)

        ctk.CTkButton(
            footer, text="start simulation",
            height=52, corner_radius=26,
            fg_color=theme._BTN_SIM, hover_color=theme._BTN_SIM_H,
            border_width=1, border_color=theme._PANEL_BD,
            text_color=theme._TEXT_MAIN,
            font=theme.font(18, family=theme.FONT_BOLD),
            command=self._confirm,
        ).grid(row=0, column=1, padx=(12, 0))

    # ── Public render methods (called by controller) ──────────────────────────

    def render_process_form(self) -> None:
        """
        Refresh the process tiles and line preview after any structural change.

        Called by SetupController after add/remove/reorder process or task
        operations. Schedules both a tiles rebuild and a preview redraw so
        that multiple rapid calls coalesce into a single UI update.
        """
        self._schedule_tiles_rebuild()
        self._schedule_preview_redraw()

    def render_task_list(self, processes) -> None:
        """
        Repopulate the task strip for the currently selected process.

        Clears all existing task tiles and re-renders them from the current
        task list of the selected process. No-op if no process is selected.

        Parameters
        ----------
        processes : list[Process]
            Current ordered process list from the production line.
        """
        if self.task_list is None or self._selected_proc is None:
            return
        for w in self.task_list.winfo_children():
            w.destroy()

        proc = next((p for p in processes if p.name == self._selected_proc), None)
        if proc is None:
            return
        for idx, task in enumerate(proc.tasks):
            self._render_task_row(proc.name, task, idx, len(proc.tasks))

    def render_line_preview(self, processes) -> None:
        """
        Schedule a redraw of the snake-pattern line preview canvas.

        Parameters
        ----------
        processes : list[Process]
            Accepted for interface compatibility; the actual data is read
            from the controller inside the scheduled redraw.
        """
        self._schedule_preview_redraw()

    def show_validation_error(self, msg: str) -> None:
        """
        Display a validation error message in the footer error label.

        Parameters
        ----------
        msg : str
            Human-readable error text shown in NEON_RED.
        """
        if self._err_label:
            self._err_label.configure(text=msg)

    # ── Process tiles: full rebuild vs fast recolor ───────────────────────────

    def _render_proc_tiles(self) -> None:
        """
        Fully destroy and recreate all process tiles from the current model state.

        This is the expensive path — call only after structural changes (add,
        remove, reorder). For selection-only changes use _refresh_tile_colors().
        Repopulates self._tile_widgets with widget references for future recolors.
        """
        if self._proc_tiles_frame is None:
            return

        for w in self._proc_tiles_frame.winfo_children():
            w.destroy()
        self._tile_widgets = {}

        if not self.controller:
            return

        pl    = self.controller._production_line
        total = len(pl.processes)
        for idx, proc in enumerate(pl.processes):
            self._render_process_tile(proc, idx, total)

        if self._proc_tiles_canvas:
            self._sync_proc_tiles_scrollregion()

    def _refresh_tile_colors(self) -> None:
        """
        Update only the border colours of existing tiles to reflect the current
        selection, without destroying or recreating any widgets.

        Called after _select_process() when only the highlighted tile changes.
        Much faster than _render_proc_tiles() for high-frequency interactions.
        """
        for proc_name, refs in self._tile_widgets.items():
            is_sel = (proc_name == self._selected_proc)
            hl = theme.NEON if is_sel else theme._PANEL_BD

            refs["tile"].configure(border_color=hl)

    # ── Process tile ──────────────────────────────────────────────────────────

    def _render_process_tile(self, proc, idx: int, total: int) -> None:
        """
        Render one process card inside the horizontal tiles strip.

        Each tile shows the process name, task count, and left/right/delete
        buttons. The selected tile uses NEON colours; others use the standard
        panel style. Widget references are stored in _tile_widgets for later
        fast recoloring.

        Parameters
        ----------
        proc : Process
            The process model object to represent.
        idx : int
            0-based position of this process in the ordered list (used to
            enable/disable the left/right reorder buttons).
        total : int
            Total number of processes (used to disable the right button on
            the last tile).
        """
        is_sel = (proc.name == self._selected_proc)
        bg     = theme.NEON    if is_sel else theme._BTN_ADD
        fg     = theme.BG_MAIN if is_sel else theme._TEXT_MAIN
        hl     = theme.NEON    if is_sel else theme._PANEL_BD

        tile = ctk.CTkFrame(
            self._proc_tiles_frame,
            fg_color=bg,
            border_color=hl,
            border_width=1,
            corner_radius=12,
        )
        tile.pack(side="left", padx=4, pady=(0,6))

        name_lbl = ctk.CTkLabel(
            tile, text=proc.name, text_color=fg,
            font=theme.font(12, family=theme.FONT_BOLD),
        )
        name_lbl.pack(padx=12, pady=(8, 0))

        task_lbl = ctk.CTkLabel(
            tile, text=f"{len(proc.tasks)} task(s)", text_color=fg,
            font=theme.font(9, family=theme.FONT_BOLD),
        )
        task_lbl.pack(padx=12, pady=(2, 0))

        btn_row = ctk.CTkFrame(tile, fg_color="transparent")
        btn_row.pack(padx=6, pady=(4, 8))

        ctk.CTkButton(
            btn_row, text="◄", width=28, height=24,
            fg_color="transparent", text_color=theme._ACCENT,
            hover_color=theme._PANEL_BD,
            font=theme.font(9, family=theme.FONT_BOLD),
            cursor="hand2" if idx > 0 else "arrow",
            state="normal" if idx > 0 else "disabled",
            command=lambda n=proc.name, i=idx: self._reorder_proc(n, i - 1),
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            btn_row, text="✕", width=28, height=24,
            fg_color="transparent", text_color=theme.NEON_RED,
            hover_color=theme._PANEL_BD,
            font=theme.font(9, family=theme.FONT_BOLD),
            cursor="hand2",
            command=lambda n=proc.name: self._remove_process(n),
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            btn_row, text="►", width=28, height=24,
            fg_color="transparent", text_color=theme._ACCENT,
            hover_color=theme._PANEL_BD,
            font=theme.font(9, family=theme.FONT_BOLD),
            cursor="hand2" if idx < total - 1 else "arrow",
            state="normal" if idx < total - 1 else "disabled",
            command=lambda n=proc.name, i=idx: self._reorder_proc(n, i + 1),
        ).pack(side="left", padx=2)

        # Store refs for fast recoloring
        self._tile_widgets[proc.name] = {
            "tile":     tile,
            "name_lbl": name_lbl,
            "task_lbl": task_lbl,
        }

        select_cmd = lambda _e, n=proc.name: self._select_process(n)
        for widget in (tile, name_lbl, task_lbl):
            widget.bind("<Button-1>", select_cmd)
            widget.configure(cursor="hand2")

    # ── Task row ──────────────────────────────────────────────────────────────

    def _render_task_row(self, proc_name: str, task, idx: int, total: int) -> None:
        """
        Render one task card inside the horizontal task strip.

        Each tile shows the task name, processing time (t=N), and
        left/right/delete buttons for reordering and removal.

        Parameters
        ----------
        proc_name : str
            Name of the parent process (passed to controller on remove/reorder).
        task : Task
            The task model object to represent.
        idx : int
            0-based position of this task within the process (disables left
            button when idx == 0).
        total : int
            Total task count in the process (disables right button on last).
        """
        tile = ctk.CTkFrame(
            self.task_list,
            fg_color=theme._BTN_ADD,
            corner_radius=10,
            border_width=1,
            border_color=theme._PANEL_BD,
        )
        tile.pack(side="left", padx=6, pady=6)

        ctk.CTkLabel(
            tile,
            text=task.name,
            fg_color="transparent",
            text_color=theme._TEXT_MAIN,
            font=theme.font(10, family=theme.FONT_BOLD),
        ).pack(padx=14, pady=(8, 2))

        ctk.CTkLabel(
            tile,
            text=f"t={task.processing_time}",
            fg_color="transparent",
            text_color=theme._TEXT_DIM2,
            font=theme.font(9),
        ).pack(padx=10, pady=(0, 4))

        btn_row = ctk.CTkFrame(tile, fg_color="transparent")
        btn_row.pack(padx=6, pady=(2, 8))

        ctk.CTkButton(
            btn_row, text="◄", width=28, height=26, corner_radius=6,
            fg_color=theme._PANEL_BG, hover_color=theme._PANEL_BD,
            text_color=theme._ACCENT, font=theme.font(11),
            state="normal" if idx > 0 else "disabled",
            command=lambda tn=task.name, i=idx: self._reorder_task(tn, i - 1),
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            btn_row, text="✕", width=28, height=26, corner_radius=6,
            fg_color="transparent", hover_color=theme._PANEL_BG,
            text_color=theme.NEON_RED, font=theme.font(11),
            command=lambda tn=task.name: self._remove_task(tn),
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            btn_row, text="►", width=28, height=26, corner_radius=6,
            fg_color=theme._PANEL_BG, hover_color=theme._PANEL_BD,
            text_color=theme._ACCENT, font=theme.font(11),
            state="normal" if idx < total - 1 else "disabled",
            command=lambda tn=task.name, i=idx: self._reorder_task(tn, i + 1),
        ).pack(side="left", padx=2)

    # ── Snake-pattern canvas preview ──────────────────────────────────────────

    def _update_canvas_preview(self, processes) -> None:
        """
        Redraw the line-preview canvas with a snake-pattern process diagram.

        Calculates how many process boxes fit per row based on the canvas width,
        then lays them out left-to-right on even rows and right-to-left on odd
        rows (snake/boustrophedon pattern). Arrows connect adjacent boxes.

        The first process box is coloured NEON (green), the last NEON_RED, and
        all intermediate boxes use the standard panel colour.

        Parameters
        ----------
        processes : list[Process]
            Ordered list of processes to visualise.
        """
        if self.line_canvas is None:
            return
        c = self.line_canvas
        c.delete("all")
        W = c.winfo_width()  or 500
        H = c.winfo_height() or 200

        if not processes:
            c.create_text(
                10, 20, anchor="w", text="No processes yet.",
                fill=theme._TEXT_DIM2, font=(theme.FONT_FAMILY, 9),
            )
            c.configure(scrollregion=(0, 0, W, H))
            return

        n = len(processes)

        BOX_W  = 110
        BOX_H  = 44
        GAP_H  = 14
        GAP_V  = 38
        MARGIN = 18

        avail_w = W - 2 * MARGIN
        per_row = max(1, (avail_w + GAP_H) // (BOX_W + GAP_H))
        per_row = min(per_row, n)

        positions: list[tuple[int, int]] = []
        for i in range(n):
            row        = i // per_row
            col_in_row = i % per_row
            row_start  = row * per_row
            row_count  = min(per_row, n - row_start)
            screen_col = col_in_row if row % 2 == 0 else row_count - 1 - col_in_row
            row_w   = row_count * BOX_W + (row_count - 1) * GAP_H
            x_start = MARGIN + max(0, (avail_w - row_w) // 2)
            x       = x_start + screen_col * (BOX_W + GAP_H)
            y       = 10 + row * (BOX_H + GAP_V)
            positions.append((x, y))

        # Arrows first (behind boxes)
        for i in range(n - 1):
            row_i  = i // per_row
            row_n  = (i + 1) // per_row
            xi, yi = positions[i]
            xn, yn = positions[i + 1]
            mid_y_i = yi + BOX_H // 2
            mid_y_n = yn + BOX_H // 2

            if row_i == row_n:
                if row_i % 2 == 0:
                    c.create_line(xi + BOX_W, mid_y_i, xn, mid_y_i,
                                  fill=theme._ACCENT, width=2, arrow="last")
                else:
                    c.create_line(xi, mid_y_i, xn + BOX_W, mid_y_i,
                                  fill=theme._ACCENT, width=2, arrow="last")
            else:
                if row_i % 2 == 0:
                    rx = W - 8
                    c.create_line(
                        xi + BOX_W, mid_y_i, rx, mid_y_i, rx, mid_y_n, xn + BOX_W, mid_y_n,
                        fill=theme._ACCENT, width=2, arrow="last", joinstyle="round",
                    )
                else:
                    lx = 6
                    c.create_line(
                        xi, mid_y_i, lx, mid_y_i, lx, mid_y_n, xn, mid_y_n,
                        fill=theme._ACCENT, width=2, arrow="last", joinstyle="round",
                    )

        # Boxes — native canvas drawing (fast)
        for i, proc in enumerate(processes):
            x, y = positions[i]

            color = (
                theme.NEON     if i == 0 else
                theme.NEON_RED if i == n - 1 else
                theme._BTN_ADD
            )
            fg = (
                theme.BG_MAIN
                if color in (theme.NEON, theme.NEON_RED)
                else theme._TEXT_MAIN
            )

            self._rounded_rect(
                c, x, y, x + BOX_W, y + BOX_H, r=12,
                fill=color, outline=theme._PANEL_BD, width=1,
            )
            c.create_text(
                x + BOX_W // 2, y + 14,
                text=proc.name[:16], fill=fg,
                font=theme.font(10, family=theme.FONT_BOLD),
            )
            c.create_text(
                x + BOX_W // 2, y + 30,
                text=f"{len(proc.tasks)} task(s)", fill=fg,
                font=theme.font(9, family=theme.FONT_BOLD),
            )

        rows = math.ceil(n / per_row)
        content_h = 10 + rows * BOX_H + max(0, rows - 1) * GAP_V + 10
        c.configure(scrollregion=(0, 0, W, max(H, content_h)))

    # ── Scrollbar helpers ─────────────────────────────────────────────────────

    def _sync_proc_tiles_scrollregion(self) -> None:
        """
        Recalculate and apply the scrollregion for the process-tiles canvas.

        Computes the bounding box of all canvas items, expands it to at least
        the canvas viewport size, and applies it so the horizontal scrollbar
        reflects the true content width. Also resets xview to 0 when all
        content fits without scrolling.
        """
        if self._proc_tiles_canvas is None:
            return
        c = self._proc_tiles_canvas
        c.update_idletasks()
        bbox = c.bbox("all")
        if not bbox:
            c.configure(scrollregion=(0, 0, c.winfo_width(), c.winfo_height()))
            c.xview_moveto(0)
            return

        x1, y1, x2, y2 = bbox
        view_w    = max(1, c.winfo_width())
        view_h    = max(1, c.winfo_height())
        content_w = max(0, x2 - x1)
        content_h = max(0, y2 - y1)
        region_w  = max(view_w, content_w)
        region_h  = max(view_h, content_h)
        c.configure(scrollregion=(0, 0, region_w, region_h))
        if content_w <= view_w + 2:
            c.xview_moveto(0)

    def _proc_tiles_has_overflow(self) -> bool:
        """
        Return True if the process-tiles content is wider than the canvas viewport.

        Used by _on_proc_tiles_xscroll() to decide whether scrolling should
        be allowed or immediately clamped back to position 0.
        """
        if self._proc_tiles_canvas is None:
            return False
        c = self._proc_tiles_canvas
        c.update_idletasks()
        bbox = c.bbox("all")
        if not bbox:
            return False
        x1, _y1, x2, _y2 = bbox
        return max(0, x2 - x1) > (c.winfo_width() + 2)

    def _on_proc_tiles_xscroll(self, *args) -> None:
        """
        Custom xscrollcommand handler that prevents scrolling past the left edge.

        When content fits without scrolling, the view is locked at position 0.
        Negative scroll units (scroll left) are clamped if already at the edge.
        This prevents the tiles from appearing partially off-screen when the
        scrollbar is dragged on a narrower-than-content canvas.

        Parameters
        ----------
        *args
            Standard Tkinter scrollbar command arguments:
            ("scroll", units, "units") or ("moveto", fraction).
        """
        if self._proc_tiles_canvas is None:
            return
        c = self._proc_tiles_canvas

        if not self._proc_tiles_has_overflow():
            c.xview_moveto(0)
            return

        if len(args) >= 3 and args[0] == "scroll":
            units = int(args[1])
            if units < 0:
                left, _right = c.xview()
                if left <= 0.0:
                    c.xview_moveto(0)
                    return
            c.xview(*args)
            return

        if len(args) >= 2 and args[0] == "moveto":
            frac = max(0.0, min(1.0, float(args[1])))
            c.xview_moveto(frac)
            if c.xview()[0] < 0.001:
                c.xview_moveto(0)
            return

        c.xview(*args)

    # ── Button / event handlers ───────────────────────────────────────────────

    def _select_process(self, name: str) -> None:
        """
        Set the active process selection and refresh the task strip.

        Updates _selected_proc, the status label text, tile border colours
        (fast recolor), and repopulates the task strip for the new selection.

        Parameters
        ----------
        name : str
            Name of the process tile that was clicked.
        """
        self._selected_proc = name
        if self._sel_label:
            self._sel_label.configure(
                text=f"Tasks for:  {name}", text_color=theme._TEXT_MAIN,
            )
        # Fast recolor only — no rebuild
        self._refresh_tile_colors()
        if self.controller:
            self.render_task_list(self.controller._production_line.processes)

    def _add_process(self) -> None:
        """
        Open the add-process dialog and delegate to the controller if confirmed.

        Shows dialogs.ask_process_name(); on confirmation, calls
        SetupController.on_add_process() and schedules a full tiles/preview rebuild.
        """
        if not self.controller:
            return
        name = dialogs.ask_process_name(self)
        if not name:
            return
        self.controller.on_add_process(name)
        self._clear_error()
        # Structural change → full rebuild
        self._schedule_tiles_rebuild()
        self._schedule_preview_redraw()

    def _remove_process(self, name: str) -> None:
        """
        Remove a process tile and clear the task list if it was selected.

        If the removed process was selected, clears _selected_proc and empties
        the task strip before delegating to SetupController.on_remove_process().

        Parameters
        ----------
        name : str
            Name of the process to remove.
        """
        if not self.controller:
            return
        if self._selected_proc == name:
            self._selected_proc = None
            if self._sel_label:
                self._sel_label.configure(
                    text="< selecciona un proceso arriba", text_color=theme._TEXT_DIM2,
                )
            if self.task_list:
                for w in self.task_list.winfo_children():
                    w.destroy()
        self.controller.on_remove_process(name)
        # Structural change → full rebuild
        self._schedule_tiles_rebuild()
        self._schedule_preview_redraw()

    def _reorder_proc(self, name: str, new_idx: int) -> None:
        """
        Move a process to a new position and schedule a full tiles/preview rebuild.

        Parameters
        ----------
        name : str
            Name of the process to reorder.
        new_idx : int
            Target 0-based position in the ordered list.
        """
        if not self.controller:
            return
        self.controller.on_reorder_process(name, new_idx)
        # Structural change → full rebuild
        self._schedule_tiles_rebuild()
        self._schedule_preview_redraw()

    def _add_task(self) -> None:
        """
        Open the add-task dialog and delegate to the controller if confirmed.

        Requires a process to be selected first; shows an info messagebox if not.
        On confirmation, calls SetupController.on_add_task() with the selected
        process name, task name, and processing time.
        """
        if not self.controller or not self._selected_proc:
            messagebox.showinfo(
                "No process selected",
                "Select a process tile first, then add a task.",
            )
            return
        result = dialogs.ask_task_details(self)
        if not result:
            return
        name, t = result
        self.controller.on_add_task(self._selected_proc, name, t)
        self._clear_error()

    def _remove_task(self, task_name: str) -> None:
        """
        Delegate task removal to the controller for the currently selected process.

        Parameters
        ----------
        task_name : str
            Name of the task to remove.
        """
        if self.controller and self._selected_proc:
            self.controller.on_remove_task(self._selected_proc, task_name)

    def _reorder_task(self, task_name: str, new_idx: int) -> None:
        """
        Delegate task reordering to the controller and immediately refresh the
        task strip to reflect the new order.

        Parameters
        ----------
        task_name : str
            Name of the task to move.
        new_idx : int
            Target 0-based position within the process's task list.
        """
        if self.controller and self._selected_proc:
            self.controller.on_reorder_task(self._selected_proc, task_name, new_idx)
            self.render_task_list(self.controller._production_line.processes)

    # ── JSON persistence ──────────────────────────────────────────────────────

    def _load_json(self) -> None:
        """
        Open a file-picker dialog and load a production-line JSON config.

        On success, delegates to SetupController.load_from_json(), clears the
        current selection state, and schedules a full UI rebuild. Shows an
        error messagebox if loading fails.
        """
        if not self.controller:
            return
        path = filedialog.askopenfilename(
            title="Load production line",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self.controller.load_from_json(path)
            self._selected_proc = None
            if self._sel_label:
                self._sel_label.configure(
                    text="< selecciona un proceso arriba", text_color=theme._TEXT_DIM2,
                )
            if self.task_list:
                for w in self.task_list.winfo_children():
                    w.destroy()
            self._clear_error()
            self._render_proc_tiles()
            self._schedule_tiles_rebuild()
            self._schedule_preview_redraw()
        except Exception as exc:
            messagebox.showerror("Load error", str(exc))

    def _save_json(self) -> None:
        """
        Open a save-file dialog and persist the current line configuration as JSON.

        Shows a success info box or an error messagebox depending on the outcome.
        """
        if not self.controller:
            return
        path = filedialog.asksaveasfilename(
            title="Save production line",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self.controller.save_to_json(path)
            messagebox.showinfo("Saved", f"Saved to:\n{path}")
        except Exception as exc:
            messagebox.showerror("Save error", str(exc))

    # ── Start simulation ──────────────────────────────────────────────────────

    def _confirm(self) -> None:
        """
        Handle the "start simulation" button press.

        Clears any existing error, runs validation via the controller, and
        invokes the on_confirm callback if validation passes. The callback
        is MainController._on_setup_confirmed() which calls start_simulation().
        """
        self._clear_error()
        if self.controller and self.controller.on_confirm_setup():
            self._on_confirm()

    def _clear_error(self) -> None:
        """Reset the footer error label to an empty string."""
        if self._err_label:
            self._err_label.configure(text="")