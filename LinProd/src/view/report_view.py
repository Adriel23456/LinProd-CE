from __future__ import annotations
from typing import Callable
from tkinter import filedialog, messagebox
import tkinter as tk
import tkinter.ttk as ttk
import customtkinter as ctk

from src.model.report import Report
from . import theme


class ReportView(ctk.CTkFrame):
    """
    Renders the final simulation report with navigation and PDF export.
    Aesthetic matches SimulationView: same colors, rounded panels, pill buttons.

    Diagram attributes (V-CD-11):
        metrics_frame : CTkFrame
        chart_canvas  : tk.Canvas
    """

    def __init__(
        self,
        parent,
        report: Report,
        on_go_to_simulation: Callable,
        on_go_to_setup: Callable,
    ) -> None:
        super().__init__(parent, fg_color=theme.BG_MAIN)
        self.report:       Report   = report
        self._go_to_sim:   Callable = on_go_to_simulation
        self._go_to_setup: Callable = on_go_to_setup

        self.metrics_frame: ctk.CTkFrame | None = None
        self.chart_canvas:  tk.Canvas    | None = None

        self._build()

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build(self) -> None:
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        self._build_top_bar()
        self._build_scroll_area()
        self._build_bottom_bar()

    # ── Top bar  (matches SimulationView top bar style) ───────────────────────

    def _build_top_bar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=16, pady=(12, 6))
        bar.columnconfigure(1, weight=1)

        # Left: title
        ctk.CTkLabel(
            bar,
            text="report",
            font=theme.font(16, family=theme.FONT_BOLD),
            text_color=theme._TEXT_MAIN,
        ).grid(row=0, column=0, sticky="w", padx=(4, 12))

        # Center: decorative pill (mirrors the t=0 timer pill)
        pill = ctk.CTkFrame(
            bar,
            fg_color=theme._PANEL_BG,
            corner_radius=20,
            border_width=1,
            border_color=theme._PANEL_BD,
        )
        pill.grid(row=0, column=1, sticky="ew", padx=8)

        ctk.CTkLabel(
            pill,
            text="simulation results",
            font=theme.font(22, family=theme.FONT_BOLD),
            text_color=theme._TEXT_MAIN,
        ).pack(pady=10, padx=40)

        # Right: navigation buttons
        btn_frame = ctk.CTkFrame(bar, fg_color="transparent")
        btn_frame.grid(row=0, column=2, sticky="e", padx=(12, 4))

        ctk.CTkButton(
            btn_frame, text="simulation",
            width=120, height=38, corner_radius=10,
            fg_color=theme._BTN_ADD, hover_color=theme._BTN_ADD_H,
            text_color=theme._TEXT_MAIN,
            font=theme.font(13, family=theme.FONT_BOLD),
            command=self._go_to_sim,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btn_frame, text="new setup",
            width=120, height=38, corner_radius=10,
            fg_color=theme.NEON_RED, hover_color="#cc2040",
            text_color="white",
            font=theme.font(13, family=theme.FONT_BOLD),
            command=self._confirm_new_setup,
        ).pack(side="left")

    # ── Scrollable content area ───────────────────────────────────────────────

    def _build_scroll_area(self) -> None:
        # Outer rounded panel — matches the canvas area panel in SimulationView
        outer = ctk.CTkFrame(
            self,
            fg_color=theme._PANEL_BG,
            corner_radius=16,
            border_width=1,
            border_color=theme._PANEL_BD,
        )
        outer.pack(fill="both", expand=True, padx=16, pady=(0, 6))

        scroll = ctk.CTkScrollableFrame(
            outer,
            fg_color="transparent",
            scrollbar_fg_color=theme._PANEL_BG,
            scrollbar_button_color=theme._PANEL_BD,
            scrollbar_button_hover_color=theme._BTN_ADD_H,
        )
        scroll.pack(fill="both", expand=True, padx=8, pady=8)

        # ── Metrics card ──────────────────────────────────────────────────────
        self.metrics_frame = ctk.CTkFrame(
            scroll,
            fg_color=theme.BG_MAIN,
            corner_radius=12,
            border_width=1,
            border_color=theme._PANEL_BD,
        )
        self.metrics_frame.pack(fill="x", padx=4, pady=(4, 10))
        self.render_metrics(self.report)

        # ── Completion Timeline card ──────────────────────────────────────────
        timeline_card = ctk.CTkFrame(
            scroll,
            fg_color=theme.BG_MAIN,
            corner_radius=12,
            border_width=1,
            border_color=theme._PANEL_BD,
        )
        timeline_card.pack(fill="x", padx=4, pady=(0, 10))

        ctk.CTkLabel(
            timeline_card,
            text="completion timeline",
            font=theme.font(13, family=theme.FONT_BOLD),
            text_color=theme._TEXT_MAIN,
        ).pack(anchor="w", padx=16, pady=(12, 4))

        self.chart_canvas = tk.Canvas(
            timeline_card, bg=theme.BG_MAIN, height=130,
            highlightthickness=0,
        )
        self.chart_canvas.pack(fill="x", padx=12, pady=(0, 12))
        self.render_timeline_chart(self.report)

        # ── Congestion Metrics card ───────────────────────────────────────────
        self.render_wait_histogram(self.report, scroll)

    # ── Bottom bar (matches SimulationView bottom bar style) ──────────────────

    def _build_bottom_bar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkButton(
            bar, text="export pdf",
            width=180, height=52, corner_radius=12,
            fg_color=theme.NEON, hover_color=theme._BTN_ADD_H,
            text_color=theme.BG_MAIN,
            font=theme.font(18, family=theme.FONT_BOLD),
            command=lambda: self.export_pdf(self.report),
        ).pack(side="right")

    # ── Render: metrics table ─────────────────────────────────────────────────

    def render_metrics(self, r: Report) -> None:
        if self.metrics_frame is None:
            return
        for w in self.metrics_frame.winfo_children():
            w.destroy()

        def section_header(label: str) -> None:
            hdr = ctk.CTkFrame(
                self.metrics_frame,
                fg_color=theme._BTN_ADD,
                corner_radius=8,
            )
            hdr.pack(fill="x", padx=10, pady=(10, 2))
            ctk.CTkLabel(
                hdr, text=label,
                font=theme.font(11, family=theme.FONT_BOLD),
                text_color=theme.NEON,
                anchor="w",
            ).pack(side="left", padx=12, pady=6)

        def data_row(label: str, value: str, even: bool) -> None:
            bg = theme._PANEL_BG if even else theme.BG_MAIN
            row_f = ctk.CTkFrame(
                self.metrics_frame,
                fg_color=bg,
                corner_radius=0,
            )
            row_f.pack(fill="x", padx=10, pady=1)
            ctk.CTkLabel(
                row_f, text=label,
                font=theme.font(12, family=theme.FONT_BOLD),
                text_color=theme._TEXT_MAIN,
                anchor="w",
            ).pack(side="left", padx=16, pady=8)
            ctk.CTkLabel(
                row_f, text=value,
                font=theme.font(12, family=theme.FONT_BOLD),
                text_color=theme.NEON,
                anchor="e",
            ).pack(side="right", padx=16, pady=8)

        # ── TIMING ────────────────────────────────────────────────────────────
        section_header("COMPLETION TIMING")
        timing_rows = [
            ("First product completed",  f"cycle {r.first_product_completed_time}"),
            ("Last product completed",   f"cycle {r.last_product_completed_time}"),
            ("Simulation makespan",      f"{r.total_processing_time} cycles"),
            ("Avg completion time",      f"{r.average_execution_time:.2f} cycles"),
            ("Throughput",               f"{r.throughput_rate:.4f} products / cycle"),
        ]
        for i, (lbl, val) in enumerate(timing_rows):
            data_row(lbl, val, i % 2 == 0)

        # ── PRODUCTS ──────────────────────────────────────────────────────────
        section_header("PRODUCTS")
        data_row("Products completed", str(r.completed_products), True)

        # ── BOTTLENECK & CONGESTION ───────────────────────────────────────────
        section_header("BOTTLENECK & CONGESTION")
        bottleneck_rows = [
            ("Bottleneck process (highest total load)",  r.bottleneck),
            ("Max time a product spent in one process",  f"{r.max_waiting_time_process} cycles"),
            ("Avg queue wait across all tasks",          f"{r.average_waiting_time_to_start_task:.2f} cycles"),
            ("Max single-task queue wait",               f"{r.max_waiting_time_task} cycles"),
            ("  ↳ Task with max queue wait",             r.max_waiting_task_name  or "N/A"),
            ("  ↳ Process of that task",                 r.max_waiting_task_process or "N/A"),
        ]
        for i, (lbl, val) in enumerate(bottleneck_rows):
            data_row(lbl, val, i % 2 == 0)

        # Bottleneck banner
        bn = ctk.CTkFrame(
            self.metrics_frame,
            fg_color="#1c0a1a",
            corner_radius=10,
            border_width=1,
            border_color=theme.NEON_RED,
        )
        bn.pack(fill="x", padx=10, pady=(8, 12))
        ctk.CTkLabel(
            bn,
            text=f"🔴  BOTTLENECK:  {r.bottleneck}",
            font=theme.font(14, family=theme.FONT_BOLD),
            text_color=theme.NEON_RED,
        ).pack(padx=12, pady=10)

    # ── Render: timeline chart ────────────────────────────────────────────────

    def render_timeline_chart(self, r: Report) -> None:
        if self.chart_canvas is None:
            return
        self.after(100, self._draw_timeline, r)

    def _draw_timeline(self, r: Report) -> None:
        if self.chart_canvas is None:
            return
        c = self.chart_canvas
        c.delete("all")
        c.update_idletasks()
        W = c.winfo_width() or 600
        H = c.winfo_height() or 130

        total  = max(r.total_processing_time, 1)
        margin = 60

        def x_of(t: int | float) -> float:
            return margin + (t / total) * (W - margin * 2)

        # Axis
        c.create_line(
            margin, H - 28, W - margin, H - 28,
            fill=theme._PANEL_BD, width=1,
        )

        # First product bar
        x1 = x_of(r.first_product_completed_time)
        _canvas_rounded_rect(
            c, margin, 14, x1, 50, r=6,
            fill=theme._BTN_ADD, outline="",
        )
        c.create_text(
            margin + 8, 32,
            text=f"First: t={r.first_product_completed_time}",
            fill=theme._TEXT_MAIN, anchor="w",
            font=theme.font(9, family=theme.FONT_BOLD),
        )

        # Last product bar
        x2 = x_of(r.last_product_completed_time)
        _canvas_rounded_rect(
            c, margin, 58, x2, 94, r=6,
            fill=theme.NEON, outline="",
        )
        c.create_text(
            margin + 8, 76,
            text=f"Last: t={r.last_product_completed_time}",
            fill=theme.BG_MAIN, anchor="w",
            font=theme.font(9, family=theme.FONT_BOLD),
        )

        # Avg line
        xa = x_of(r.average_execution_time)
        c.create_line(
            xa, 8, xa, H - 28,
            fill=theme.NEON_AMBER, dash=(4, 3), width=2,
        )
        c.create_text(
            xa + 4, 10,
            text=f"avg={r.average_execution_time:.1f}",
            fill=theme.NEON_AMBER, anchor="w",
            font=theme.font(8, family=theme.FONT_BOLD),
        )

        # Tick marks
        for pct in range(0, 101, 25):
            tx = margin + (pct / 100) * (W - margin * 2)
            tv = int(total * pct / 100)
            c.create_line(tx, H - 31, tx, H - 25, fill=theme._TEXT_DIM2)
            c.create_text(
                tx, H - 12, text=str(tv),
                fill=theme._TEXT_DIM2,
                font=theme.font(8, family=theme.FONT_BOLD),
            )

    # ── Render: congestion histogram ──────────────────────────────────────────

    def render_wait_histogram(self, r: Report, scroll_parent) -> None:
        card = ctk.CTkFrame(
            scroll_parent,
            fg_color=theme.BG_MAIN,
            corner_radius=12,
            border_width=1,
            border_color=theme._PANEL_BD,
        )
        card.pack(fill="x", padx=4, pady=(0, 10))

        ctk.CTkLabel(
            card,
            text="congestion metrics",
            font=theme.font(13, family=theme.FONT_BOLD),
            text_color=theme._TEXT_MAIN,
        ).pack(anchor="w", padx=16, pady=(12, 4))

        hist_canvas = tk.Canvas(
            card, bg=theme.BG_MAIN, height=160,
            highlightthickness=0,
        )
        hist_canvas.pack(fill="x", padx=12, pady=(0, 12))
        self.after(150, self._draw_histogram, hist_canvas, r)

    def _draw_histogram(self, c: tk.Canvas, r: Report) -> None:
        c.delete("all")
        c.update_idletasks()
        W = c.winfo_width() or 600
        H = c.winfo_height() or 160

        metrics = [
            ("Avg\nqueue wait",  r.average_waiting_time_to_start_task, theme.NEON),
            ("Max task\nwait",   r.max_waiting_time_task,              theme.NEON_RED),
            ("Max proc\ntime",   r.max_waiting_time_process,           theme.NEON_AMBER),
            ("Avg\ncompletion",  r.average_execution_time,             theme._BTN_ADD),
        ]
        max_val   = max((v for _, v, _ in metrics), default=1) or 1
        n         = len(metrics)
        gap       = 20
        bar_w     = (W - 60 - gap * (n - 1)) // n
        margin    = 30
        bar_max_h = H - 52

        for i, (label, val, color) in enumerate(metrics):
            bh   = max(4, int((val / max_val) * bar_max_h))
            x    = margin + i * (bar_w + gap)
            ytop = H - 34 - bh

            _canvas_rounded_rect(
                c, x, ytop, x + bar_w, H - 34,
                r=6, fill=color, outline="",
            )

            # Value above bar
            c.create_text(
                x + bar_w // 2, max(ytop - 10, 6),
                text=f"{val:.1f}",
                fill=theme._TEXT_MAIN,
                font=theme.font(8, family=theme.FONT_BOLD),
            )
            # Label below axis
            for j, part in enumerate(label.split("\n")):
                c.create_text(
                    x + bar_w // 2, H - 18 + j * 11,
                    text=part,
                    fill=theme._TEXT_DIM2,
                    font=theme.font(7, family=theme.FONT_BOLD),
                )

    # ── PDF export ────────────────────────────────────────────────────────────

    def export_pdf(self, r: Report) -> None:
        path = filedialog.asksaveasfilename(
            title="Export report as PDF",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self._write_pdf(path, r)
            messagebox.showinfo("PDF exported", f"Report saved to:\n{path}")
        except Exception as exc:
            messagebox.showerror("Export error", str(exc))

    def _write_pdf(self, path: str, r: Report) -> None:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER

        doc    = SimpleDocTemplate(
            path, pagesize=A4,
            leftMargin=2*cm, rightMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm,
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "Title2", parent=styles["Title"], fontSize=20, spaceAfter=6,
            textColor=colors.HexColor("#2c3e50"), alignment=TA_CENTER,
        )
        h2_style = ParagraphStyle(
            "H2", parent=styles["Heading2"], fontSize=13,
            textColor=colors.HexColor("#2980b9"), spaceBefore=12,
        )
        body_style = styles["BodyText"]

        story = [
            Paragraph("LinProd — Simulation Report", title_style),
            Paragraph(
                "CE-5507 · Instituto Tecnológico de Costa Rica · Semester 1, 2026",
                ParagraphStyle(
                    "Sub", parent=styles["Normal"],
                    alignment=TA_CENTER, fontSize=9,
                    textColor=colors.gray,
                ),
            ),
            Spacer(1, 0.4*cm),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor("#2980b9")),
            Spacer(1, 0.3*cm),
        ]

        story.append(Paragraph("Completion Timing", h2_style))
        story.append(_make_table([
            ["Metric", "Value"],
            ["First product completed",   f"cycle {r.first_product_completed_time}"],
            ["Last product completed",    f"cycle {r.last_product_completed_time}"],
            ["Simulation makespan",       f"{r.total_processing_time} cycles"],
            ["Average completion time",   f"{r.average_execution_time:.2f} cycles"],
            ["Throughput",                f"{r.throughput_rate:.4f} products / cycle"],
        ]))

        story.append(Paragraph("Products", h2_style))
        story.append(_make_table([
            ["Metric", "Value"],
            ["Products completed", str(r.completed_products)],
        ]))

        story.append(Paragraph("Bottleneck & Congestion", h2_style))
        story.append(_make_table([
            ["Metric", "Value"],
            ["Bottleneck process (highest total load)",   r.bottleneck],
            ["Max time a product spent in one process",   f"{r.max_waiting_time_process} cycles"],
            ["Avg queue wait across all tasks",           f"{r.average_waiting_time_to_start_task:.2f} cycles"],
            ["Max single-task queue wait",                f"{r.max_waiting_time_task} cycles"],
            ["Task with max queue wait",                  r.max_waiting_task_name  or "N/A"],
            ["Process of that task",                      r.max_waiting_task_process or "N/A"],
        ]))

        story += [
            Spacer(1, 0.5*cm),
            Paragraph("Bottleneck Analysis", h2_style),
            Paragraph(
                f"The process identified as the main bottleneck is "
                f"<b>{r.bottleneck}</b>. "
                f"The task that caused the single longest queue wait was "
                f"<b>{r.max_waiting_task_name or 'N/A'}</b> "
                f"(process <b>{r.max_waiting_task_process or 'N/A'}</b>), "
                f"with a peak wait of <b>{r.max_waiting_time_task} cycles</b>.",
                body_style,
            ),
            Spacer(1, 0.3*cm),
            Paragraph("Authors", h2_style),
            Paragraph(
                "Adriel S. Chaves Salazar · Daniel Duarte Cordero · "
                "Ma. Paula Madrigal Sánchez · Andrés Molina Redondo",
                body_style,
            ),
        ]
        doc.build(story)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _confirm_new_setup(self) -> None:
        if messagebox.askyesno(
            "Reset simulation",
            "This will clear all production data and return to setup.\nContinue?",
        ):
            self._go_to_setup()


# ── Canvas helper (mirrors _rounded_rect in simulation_view) ──────────────────

def _canvas_rounded_rect(
    canvas: tk.Canvas, x1, y1, x2, y2, r=8, **kw
) -> int:
    pts = [
        x1 + r, y1,
        x2 - r, y1,
        x2, y1,
        x2, y1 + r,
        x2, y2 - r,
        x2, y2,
        x2 - r, y2,
        x1 + r, y2,
        x1, y2,
        x1, y2 - r,
        x1, y1 + r,
        x1, y1,
        x1 + r, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kw)


# ── PDF table helper ──────────────────────────────────────────────────────────

def _make_table(data: list[list[str]]):
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import Table, TableStyle

    tbl = Table(data, colWidths=[10*cm, 6*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),  colors.HexColor("#2980b9")),
        ("TEXTCOLOR",      (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",       (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",       (0, 0), (-1, 0),  11),
        ("ALIGN",          (0, 0), (-1, -1), "LEFT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#ecf0f1"), colors.white]),
        ("GRID",           (0, 0), (-1, -1), 0.4, colors.HexColor("#bdc3c7")),
        ("PADDING",        (0, 0), (-1, -1), 6),
    ]))
    return tbl