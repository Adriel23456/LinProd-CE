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
    """Return a CTkLabel with the logo image, or None if unavailable."""
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
        lbl._logo_img = img  # prevent GC
        return lbl
    except Exception:
        return None


class SetupView(ctk.CTkFrame):
    """
    Production-line configuration interface.

    Process tiles: horizontal scrollable row, auto-width, with ◄/► reorder.
    Task list:     vertical CTkScrollableFrame for the selected process.
    Line preview:  snake-pattern tk.Canvas in the right body column.

    Controller wired by MainController after construction (V-CD-05).
    Diagram attributes (V-CD-06):
        process_form : CTkFrame           (process-tiles section)
        task_list    : CTkScrollableFrame
        line_canvas  : tk.Canvas
    """

    def __init__(self, parent, on_confirm: Callable) -> None:
        super().__init__(parent, fg_color=theme.BG_MAIN)
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

        self._build()

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build(self) -> None:
        self._build_header()
        self._build_process_section()
        self._build_body()
        self._build_footer()

    def _build_header(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=theme.BG_PANEL, corner_radius=0,
                           border_width=1, border_color=theme.BORDER)
        bar.pack(fill="x")

        # Logo
        logo_lbl = _load_logo(bar, size=(38, 38))
        if logo_lbl:
            logo_lbl.pack(side="left", padx=(10, 0), pady=8)

        ctk.CTkLabel(
            bar, text="LinProd  —  Setup",
            font=theme.font(20, bold=True), text_color=theme.NEON,
        ).pack(side="left", padx=12, pady=12)

        credits = "Chaves  ·  Duarte  ·  Madrigal  ·  Molina"
        ctk.CTkLabel(
            bar, text=credits, font=theme.font(10), text_color=theme.TEXT_DIM,
        ).pack(side="right", padx=16)

        jrow = ctk.CTkFrame(bar, fg_color="transparent")
        jrow.pack(side="right", padx=6)
        ctk.CTkButton(
            jrow, text="LOAD JSON", width=96, corner_radius=0, height=28,
            fg_color="transparent", text_color=theme.NEON_BLUE,
            border_width=1, border_color=theme.NEON_BLUE,
            hover_color=theme.BG_PANEL, font=theme.font(10, bold=True),
            command=self._load_json,
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            jrow, text="SAVE JSON", width=96, corner_radius=0, height=28,
            fg_color="transparent", text_color=theme.NEON_BLUE,
            border_width=1, border_color=theme.NEON_BLUE,
            hover_color=theme.BG_PANEL, font=theme.font(10, bold=True),
            command=self._save_json,
        ).pack(side="left", padx=2)

    def _build_process_section(self) -> None:
        """Horizontal scrollable row of process tiles (auto-width, reorder buttons)."""
        self.process_form = ctk.CTkFrame(
            self, fg_color=theme.BG_PANEL, corner_radius=0,
            border_width=1, border_color=theme.BORDER,
        )
        self.process_form.pack(fill="x", padx=12, pady=(10, 0))

        lbl_row = ctk.CTkFrame(self.process_form, fg_color="transparent")
        lbl_row.pack(fill="x", padx=10, pady=(8, 2))
        ctk.CTkLabel(
            lbl_row, text="PROCESSES",
            font=theme.font(13, bold=True), text_color=theme.NEON,
        ).pack(side="left")
        ctk.CTkButton(
            lbl_row, text="+ ADD PROCESS", width=130, corner_radius=0, height=28,
            fg_color=theme.NEON, text_color=theme.BG_MAIN,
            hover_color="#00cc7a", font=theme.font(11, bold=True),
            command=self._add_process,
        ).pack(side="right")

        canvas_row = tk.Frame(self.process_form, bg=theme.BG_PANEL)
        canvas_row.pack(fill="x", padx=10, pady=(0, 4))

        # Taller canvas so cards never clip into the scrollbar
        self._proc_tiles_canvas = tk.Canvas(
            canvas_row, bg=theme.BG_PANEL, height=130, highlightthickness=0,
        )
        self._proc_tiles_canvas.pack(side="top", fill="x")

        h_scroll = ttk.Scrollbar(
            canvas_row, orient="horizontal", style=theme.H_SCROLL,
            command=self._proc_tiles_canvas.xview,
        )
        h_scroll.pack(side="top", fill="x")
        self._proc_tiles_canvas.configure(xscrollcommand=h_scroll.set)

        self._proc_tiles_frame = tk.Frame(self._proc_tiles_canvas, bg=theme.BG_PANEL)
        self._proc_tiles_canvas.create_window(0, 0, anchor="nw",
                                              window=self._proc_tiles_frame)
        self._proc_tiles_frame.bind(
            "<Configure>",
            lambda _e: self._proc_tiles_canvas.configure(
                scrollregion=self._proc_tiles_canvas.bbox("all")
            ),
        )

    def _build_body(self) -> None:
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=8)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, fg_color=theme.BG_PANEL, corner_radius=0,
                             border_width=1, border_color=theme.BORDER)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self._build_task_panel(left)

        right = ctk.CTkFrame(body, fg_color=theme.BG_PANEL, corner_radius=0,
                              border_width=1, border_color=theme.BORDER)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self._build_preview_panel(right)

    def _build_task_panel(self, parent: ctk.CTkFrame) -> None:
        task_hdr = ctk.CTkFrame(parent, fg_color="transparent")
        task_hdr.pack(fill="x", padx=10, pady=(10, 2))
        ctk.CTkLabel(
            task_hdr, text="TASKS",
            font=theme.font(13, bold=True), text_color=theme.NEON,
        ).pack(side="left")
        ctk.CTkButton(
            task_hdr, text="+ ADD TASK", width=110, corner_radius=0, height=28,
            fg_color=theme.NEON_BLUE, text_color=theme.BG_MAIN,
            hover_color="#009fcc", font=theme.font(11, bold=True),
            command=self._add_task,
        ).pack(side="right")

        self._sel_label = ctk.CTkLabel(
            parent, text="< select a process above",
            font=theme.font(10), text_color=theme.TEXT_DIM,
        )
        self._sel_label.pack(anchor="w", padx=10, pady=(0, 4))

        self.task_list = ctk.CTkScrollableFrame(
            parent, fg_color=theme.BG_PANEL,
            label_text="TASK ORDER",
            label_font=theme.font(10, bold=True),
            label_text_color=theme.TEXT_DIM,
            scrollbar_fg_color=theme.BG_PANEL,
            scrollbar_button_color=theme.BORDER,
            scrollbar_button_hover_color=theme.BORDER_LIT,
        )
        self.task_list.pack(fill="both", expand=True, padx=8, pady=(0, 10))

    def _build_preview_panel(self, parent: ctk.CTkFrame) -> None:
        ctk.CTkLabel(
            parent, text="LINE PREVIEW",
            font=theme.font(12, bold=True), text_color=theme.TEXT_DIM,
        ).pack(anchor="w", padx=10, pady=(10, 4))

        self.line_canvas = tk.Canvas(
            parent, bg=theme.BG_MAIN, highlightthickness=1,
            highlightbackground=theme.BORDER,
        )
        self.line_canvas.pack(fill="both", expand=True, padx=8, pady=(0, 10))

    def _build_footer(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=theme.BG_PANEL, corner_radius=0,
                           border_width=1, border_color=theme.BORDER)
        bar.pack(fill="x")

        self._err_label = ctk.CTkLabel(
            bar, text="", font=theme.font(10), text_color=theme.NEON_RED,
        )
        self._err_label.pack(side="left", padx=16, pady=10)

        ctk.CTkButton(
            bar, text="▶  START SIMULATION", width=200, corner_radius=0, height=38,
            fg_color=theme.NEON, text_color=theme.BG_MAIN,
            hover_color="#00cc7a", font=theme.font(15, bold=True),
            command=self._confirm,
        ).pack(side="right", padx=16, pady=8)

    # ── Public render methods (called by controller) ──────────────────────────

    def render_process_form(self) -> None:
        if self._proc_tiles_frame is None or not self.controller:
            return
        for w in self._proc_tiles_frame.winfo_children():
            w.destroy()

        pl    = self.controller._production_line
        total = len(pl.processes)
        for idx, proc in enumerate(pl.processes):
            self._render_process_tile(proc, idx, total)

        self._proc_tiles_frame.update_idletasks()
        if self._proc_tiles_canvas:
            self._proc_tiles_canvas.configure(
                scrollregion=self._proc_tiles_canvas.bbox("all")
            )
        self._update_canvas_preview(pl.processes)

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

    # ── Process tile (auto-width, ◄ reorder ►, select, delete) ───────────────

    def _render_process_tile(self, proc, idx: int, total: int) -> None:
        is_sel = (proc.name == self._selected_proc)
        bg     = theme.NEON if is_sel else theme.BG_ROW
        fg     = theme.BG_MAIN if is_sel else theme.TEXT
        hl     = theme.NEON if is_sel else theme.BORDER

        tile = tk.Frame(
            self._proc_tiles_frame, bg=bg,
            highlightthickness=1, highlightbackground=hl,
        )
        tile.pack(side="left", padx=4, pady=6)

        name_lbl = tk.Label(
            tile, text=proc.name, bg=bg, fg=fg,
            font=(theme.FONT_FAMILY, 10, "bold"),
            padx=12, pady=5,
        )
        name_lbl.pack()

        task_lbl = tk.Label(
            tile, text=f"{len(proc.tasks)} task(s)", bg=bg, fg=fg,
            font=(theme.FONT_FAMILY, 9),
            padx=12, pady=2,
        )
        task_lbl.pack()

        # Bottom row: ◄ delete ►
        btn_row = tk.Frame(tile, bg=bg)
        btn_row.pack(padx=6, pady=(2, 6))

        tk.Button(
            btn_row, text="◄", bg=bg, fg=theme.NEON_BLUE,
            font=(theme.FONT_FAMILY, 9), relief="flat", bd=0,
            cursor="hand2" if idx > 0 else "arrow",
            state="normal" if idx > 0 else "disabled",
            command=lambda n=proc.name, i=idx: self._reorder_proc(n, i - 1),
        ).pack(side="left", padx=2)

        tk.Button(
            btn_row, text="✕", bg=bg, fg=theme.NEON_RED,
            font=(theme.FONT_FAMILY, 9), relief="flat", bd=0,
            cursor="hand2",
            command=lambda n=proc.name: self._remove_process(n),
        ).pack(side="left", padx=2)

        tk.Button(
            btn_row, text="►", bg=bg, fg=theme.NEON_BLUE,
            font=(theme.FONT_FAMILY, 9), relief="flat", bd=0,
            cursor="hand2" if idx < total - 1 else "arrow",
            state="normal" if idx < total - 1 else "disabled",
            command=lambda n=proc.name, i=idx: self._reorder_proc(n, i + 1),
        ).pack(side="left", padx=2)

        for widget in (tile, name_lbl, task_lbl):
            widget.bind("<Button-1>", lambda _e, n=proc.name: self._select_process(n))
            widget.configure(cursor="hand2")

    # ── Task row ──────────────────────────────────────────────────────────────

    def _render_task_row(self, proc_name: str, task, idx: int, total: int) -> None:
        row = ctk.CTkFrame(self.task_list, fg_color=theme.BG_ROW, corner_radius=0,
                           border_width=1, border_color=theme.BORDER)
        row.pack(fill="x", pady=1, padx=2)

        ctk.CTkLabel(
            row, text=task.name, font=theme.font(12, bold=True), text_color=theme.TEXT,
        ).pack(side="left", padx=10, pady=4)
        ctk.CTkLabel(
            row, text=f"t={task.processing_time}",
            font=theme.font(10), text_color=theme.TEXT_DIM,
        ).pack(side="left")

        ctrl = ctk.CTkFrame(row, fg_color="transparent")
        ctrl.pack(side="right", padx=6)

        ctk.CTkButton(
            ctrl, text="↑", width=28, corner_radius=0, height=26,
            fg_color=theme.BG_PANEL, text_color=theme.NEON_BLUE,
            hover_color=theme.BORDER, font=theme.font(11),
            state="normal" if idx > 0 else "disabled",
            command=lambda tn=task.name, i=idx: self._reorder_task(tn, i - 1),
        ).pack(side="left", padx=1)
        ctk.CTkButton(
            ctrl, text="↓", width=28, corner_radius=0, height=26,
            fg_color=theme.BG_PANEL, text_color=theme.NEON_BLUE,
            hover_color=theme.BORDER, font=theme.font(11),
            state="normal" if idx < total - 1 else "disabled",
            command=lambda tn=task.name, i=idx: self._reorder_task(tn, i + 1),
        ).pack(side="left", padx=1)
        ctk.CTkButton(
            ctrl, text="✕", width=28, corner_radius=0, height=26,
            fg_color="transparent", text_color=theme.NEON_RED,
            hover_color=theme.BG_PANEL, font=theme.font(11),
            command=lambda tn=task.name: self._remove_task(tn),
        ).pack(side="left", padx=1)

    # ── Snake-pattern canvas preview ──────────────────────────────────────────

    def _update_canvas_preview(self, processes) -> None:
        if self.line_canvas is None:
            return
        c = self.line_canvas
        c.delete("all")

        if not processes:
            c.create_text(
                10, 20, anchor="w", text="No processes yet.",
                fill=theme.TEXT_DIM, font=(theme.FONT_FAMILY, 9),
            )
            return

        c.update_idletasks()
        W = c.winfo_width()  or 500
        H = c.winfo_height() or 300
        n = len(processes)

        BOX_W   = 110
        BOX_H   = 44
        GAP_H   = 14
        GAP_V   = 38
        MARGIN  = 18

        avail_w  = W - 2 * MARGIN
        per_row  = max(1, (avail_w + GAP_H) // (BOX_W + GAP_H))
        per_row  = min(per_row, n)

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
                                  fill=theme.NEON_BLUE, width=2, arrow="last")
                else:
                    c.create_line(xi, mid_y_i, xn + BOX_W, mid_y_i,
                                  fill=theme.NEON_BLUE, width=2, arrow="last")
            else:
                if row_i % 2 == 0:
                    rx = W - 8
                    c.create_line(
                        xi + BOX_W, mid_y_i, rx, mid_y_i, rx, mid_y_n, xn + BOX_W, mid_y_n,
                        fill=theme.NEON_BLUE, width=2, arrow="last", joinstyle="round",
                    )
                else:
                    lx = 6
                    c.create_line(
                        xi, mid_y_i, lx, mid_y_i, lx, mid_y_n, xn, mid_y_n,
                        fill=theme.NEON_BLUE, width=2, arrow="last", joinstyle="round",
                    )

        for i, proc in enumerate(processes):
            x, y  = positions[i]
            color = (theme.NEON     if i == 0 and n == 1 else
                     theme.NEON     if i == 0 else
                     theme.NEON_RED if i == n - 1 else
                     "#3d5a80")
            fg    = theme.BG_MAIN if color in (theme.NEON, theme.NEON_RED) else theme.TEXT
            c.create_rectangle(x, y, x + BOX_W, y + BOX_H,
                               fill=color, outline=theme.BORDER, width=1)
            c.create_text(x + BOX_W // 2, y + BOX_H // 2 - 8,
                          text=proc.name[:16], fill=fg,
                          font=(theme.FONT_FAMILY, 8, "bold"))
            c.create_text(x + BOX_W // 2, y + BOX_H // 2 + 9,
                          text=f"{len(proc.tasks)} task(s)", fill=fg,
                          font=(theme.FONT_FAMILY, 7))

    # ── Button / event handlers ───────────────────────────────────────────────

    def _select_process(self, name: str) -> None:
        self._selected_proc = name
        if self._sel_label:
            self._sel_label.configure(
                text=f"Tasks for:  {name}", text_color=theme.TEXT,
            )
        if self.controller:
            self.render_process_form()
            self.render_task_list(self.controller._production_line.processes)

    def _add_process(self) -> None:
        if not self.controller:
            return
        name = dialogs.ask_process_name(self)
        if not name:
            return
        self.controller.on_add_process(name)
        self._clear_error()

    def _remove_process(self, name: str) -> None:
        if not self.controller:
            return
        if self._selected_proc == name:
            self._selected_proc = None
            if self._sel_label:
                self._sel_label.configure(
                    text="< select a process above", text_color=theme.TEXT_DIM,
                )
            if self.task_list:
                for w in self.task_list.winfo_children():
                    w.destroy()
        self.controller.on_remove_process(name)

    def _reorder_proc(self, name: str, new_idx: int) -> None:
        if self.controller:
            self.controller.on_reorder_process(name, new_idx)

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
                    text="< select a process above", text_color=theme.TEXT_DIM,
                )
            if self.task_list:
                for w in self.task_list.winfo_children():
                    w.destroy()
            self._clear_error()
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
