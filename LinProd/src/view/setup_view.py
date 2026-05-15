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
        lbl._logo_img = img
        return lbl
    except Exception:
        return None


class SetupView(ctk.CTkFrame):
    """
    Production-line configuration interface.

    Diagram attributes (V-CD-06):
        process_form : CTkFrame           (process-tiles section)
        task_list    : CTkScrollableFrame
        line_canvas  : tk.Canvas
    """

    def __init__(self, parent, on_confirm: Callable) -> None:
        super().__init__(parent, fg_color="transparent")
        self.controller:  "SetupController | None" = None
        self._on_confirm: Callable = on_confirm

        # Diagram-required widget attributes
        self.process_form: ctk.CTkFrame             | None = None
        self.task_list:    ctk.CTkScrollableFrame   | None = None
        self.line_canvas:  tk.Canvas                | None = None

        # Internal state
        self._selected_proc:  str | None = None
        self._err_label:      ctk.CTkLabel | None = None
        self._sel_label:      ctk.CTkLabel | None = None

        # Process-tiles canvas references
        self._proc_tiles_canvas: tk.Canvas | None = None
        self._proc_tiles_frame:  tk.Frame  | None = None

        # Fast-recolor cache: proc.name -> {"tile", "name_lbl", "task_lbl"}
        self._tile_widgets: dict[str, dict] = {}

        self._build()

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build(self) -> None:
        
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

    # ── Columna izquierda ─────────────────────────────────────────────────────

    def _build_left_panel(self, parent: ctk.CTkFrame) -> None:
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
            text="modelación de hardware y software orientado a objetos",
            font=theme.font(9),
            text_color=theme._TEXT_DIM2,
            wraplength=240,
            justify="center",
        ).pack(pady=(12, 2))

        ctk.CTkLabel(
            credits_frame,
            text="chaves · duarte · madrigal · molina",
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

    # ── Columna derecha: secciones ────────────────────────────────────────────

    def _build_process_section_new(self, parent: ctk.CTkFrame) -> None:
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
            container, text="< selecciona un proceso arriba",
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
        container = ctk.CTkFrame(
            parent, fg_color=theme._PANEL_BG, corner_radius=14,
            border_width=1, border_color=theme._PANEL_BD,
        )
        container.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        container.rowconfigure(1, weight=1)
        container.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            container, text="line preview",
            font=theme.font(14, bold=True), text_color=theme._TEXT_MAIN,
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
        footer = ctk.CTkFrame(parent, fg_color="transparent")
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
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=18, weight="bold"),
            command=self._confirm,
        ).grid(row=0, column=1, padx=(12, 0))

    # ── Public render methods (called by controller) ──────────────────────────

    def render_process_form(self) -> None:
        """Called by controller after any structural change to the process list."""
        self._render_proc_tiles()
        if self.controller:
            self._update_canvas_preview(self.controller._production_line.processes)

    def render_task_list(self, processes) -> None:
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
        self._update_canvas_preview(processes)

    def show_validation_error(self, msg: str) -> None:
        if self._err_label:
            self._err_label.configure(text=msg)

    # ── Process tiles: full rebuild vs fast recolor ───────────────────────────

    def _render_proc_tiles(self) -> None:
        """Full rebuild of the tile row — call only on structural changes."""
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

        self._proc_tiles_frame.update_idletasks()
        if self._proc_tiles_canvas:
            self._sync_proc_tiles_scrollregion()

    def _refresh_tile_colors(self) -> None:
        """Only recolor existing tiles — no destroy/recreate. Instant update."""
        for proc_name, refs in self._tile_widgets.items():
            is_sel = (proc_name == self._selected_proc)
            hl = theme.NEON if is_sel else theme._PANEL_BD

            refs["tile"].configure(border_color=hl)

    # ── Process tile ──────────────────────────────────────────────────────────

    def _render_process_tile(self, proc, idx: int, total: int) -> None:
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
        tile.pack(side="left", padx=4, pady=6)

        name_lbl = ctk.CTkLabel(
            tile, text=proc.name, text_color=fg,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=10, weight="bold"),
        )
        name_lbl.pack(padx=12, pady=(8, 0))

        task_lbl = ctk.CTkLabel(
            tile, text=f"{len(proc.tasks)} task(s)", text_color=fg,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=9),
        )
        task_lbl.pack(padx=12, pady=(2, 0))

        btn_row = ctk.CTkFrame(tile, fg_color="transparent")
        btn_row.pack(padx=6, pady=(4, 8))

        ctk.CTkButton(
            btn_row, text="◄", width=28, height=24,
            fg_color="transparent", text_color=theme._ACCENT,
            hover_color=theme._PANEL_BD,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=9),
            cursor="hand2" if idx > 0 else "arrow",
            state="normal" if idx > 0 else "disabled",
            command=lambda n=proc.name, i=idx: self._reorder_proc(n, i - 1),
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            btn_row, text="✕", width=28, height=24,
            fg_color="transparent", text_color=theme.NEON_RED,
            hover_color=theme._PANEL_BD,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=9),
            cursor="hand2",
            command=lambda n=proc.name: self._remove_process(n),
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            btn_row, text="►", width=28, height=24,
            fg_color="transparent", text_color=theme._ACCENT,
            hover_color=theme._PANEL_BD,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=9),
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
            font=theme.font(10, bold=True),
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
        if self.line_canvas is None:
            return
        c = self.line_canvas
        c.delete("all")
        c.update_idletasks()
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

        for i, proc in enumerate(processes):
            x, y  = positions[i]
            color = (theme.NEON     if i == 0 and n == 1 else
                     theme.NEON     if i == 0 else
                     theme.NEON_RED if i == n - 1 else
                     theme._BTN_ADD)
            fg    = theme.BG_MAIN if color in (theme.NEON, theme.NEON_RED) else theme._TEXT_MAIN
            c.create_rectangle(x, y, x + BOX_W, y + BOX_H,
                               fill=color, outline=theme._PANEL_BD, width=1)
            c.create_text(x + BOX_W // 2, y + BOX_H // 2 - 8,
                          text=proc.name[:16], fill=fg,
                          font=(theme.FONT_FAMILY, 8, "bold"))
            c.create_text(x + BOX_W // 2, y + BOX_H // 2 + 9,
                          text=f"{len(proc.tasks)} task(s)", fill=fg,
                          font=(theme.FONT_FAMILY, 7))

        rows = math.ceil(n / per_row)
        content_h = 10 + rows * BOX_H + max(0, rows - 1) * GAP_V + 10
        c.configure(scrollregion=(0, 0, W, max(H, content_h)))

    # ── Scrollbar helpers ─────────────────────────────────────────────────────

    def _sync_proc_tiles_scrollregion(self) -> None:
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
        if not self.controller:
            return
        name = dialogs.ask_process_name(self)
        if not name:
            return
        self.controller.on_add_process(name)
        self._clear_error()
        # Structural change → full rebuild
        self._render_proc_tiles()
        if self.controller:
            self._update_canvas_preview(self.controller._production_line.processes)

    def _remove_process(self, name: str) -> None:
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
        self._render_proc_tiles()
        if self.controller:
            self._update_canvas_preview(self.controller._production_line.processes)

    def _reorder_proc(self, name: str, new_idx: int) -> None:
        if not self.controller:
            return
        self.controller.on_reorder_process(name, new_idx)
        # Structural change → full rebuild
        self._render_proc_tiles()
        if self.controller:
            self._update_canvas_preview(self.controller._production_line.processes)

    def _add_task(self) -> None:
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
        if self.controller and self._selected_proc:
            self.controller.on_remove_task(self._selected_proc, task_name)

    def _reorder_task(self, task_name: str, new_idx: int) -> None:
        if self.controller and self._selected_proc:
            self.controller.on_reorder_task(self._selected_proc, task_name, new_idx)
            self.render_task_list(self.controller._production_line.processes)

    # ── JSON persistence ──────────────────────────────────────────────────────

    def _load_json(self) -> None:
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
            self._update_canvas_preview(self.controller._production_line.processes)
        except Exception as exc:
            messagebox.showerror("Load error", str(exc))

    def _save_json(self) -> None:
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
        self._clear_error()
        if self.controller and self.controller.on_confirm_setup():
            self._on_confirm()

    def _clear_error(self) -> None:
        if self._err_label:
            self._err_label.configure(text="")