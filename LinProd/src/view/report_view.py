from __future__ import annotations
from typing import Callable
from tkinter import filedialog, messagebox
import tkinter as tk
import customtkinter as ctk

from src.model.report import Report
from . import theme


class ReportView(ctk.CTkFrame):
    """
    Renders the final simulation report with navigation and PDF export.

    Diagram attributes (V-CD-11):
        metrics_frame : CTkFrame
        chart_canvas  : tk.Canvas

    Navigation callbacks:
        on_go_to_simulation : Callable — return to SimulationView
        on_go_to_setup      : Callable — full reset → SetupView
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
        self._build_top_bar()
        self._build_scroll_area()
        self._build_bottom_bar()

    def _build_top_bar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=theme.BG_PANEL, corner_radius=0,
                           border_width=1, border_color=theme.BORDER)
        bar.pack(fill="x")

        ctk.CTkLabel(
            bar, text="LinProd  —  Report",
            font=theme.font(18, bold=True), text_color=theme.NEON,
        ).pack(side="left", padx=16, pady=10)

        ctk.CTkButton(
            bar, text="◀ SIMULATION", width=120, corner_radius=0, height=32,
            fg_color="transparent", text_color=theme.TEXT_DIM,
            border_width=1, border_color=theme.BORDER,
            hover_color=theme.BG_PANEL, font=theme.font(11, bold=True),
            command=self._go_to_sim,
        ).pack(side="right", padx=6, pady=8)

        ctk.CTkButton(
            bar, text="⟳ NEW SETUP", width=120, corner_radius=0, height=32,
            fg_color=theme.NEON_RED, text_color="white",
            hover_color="#cc2040", font=theme.font(11, bold=True),
            command=self._confirm_new_setup,
        ).pack(side="right", padx=2, pady=8)

    def _build_scroll_area(self) -> None:
        scroll = ctk.CTkScrollableFrame(
            self, fg_color=theme.BG_MAIN,
            label_text="FULL REPORT",
            label_font=theme.font(13, bold=True),
            label_text_color=theme.NEON,
            scrollbar_fg_color=theme.BG_PANEL,
            scrollbar_button_color=theme.BORDER,
            scrollbar_button_hover_color=theme.BORDER_LIT,
        )
        scroll.pack(fill="both", expand=True, padx=16, pady=8)

        # Metrics frame
        self.metrics_frame = ctk.CTkFrame(
            scroll, fg_color=theme.BG_PANEL, corner_radius=0,
            border_width=1, border_color=theme.BORDER,
        )
        self.metrics_frame.pack(fill="x", padx=4, pady=(4, 8))
        self.render_metrics(self.report)

        # Timeline chart
        ctk.CTkLabel(
            scroll, text="COMPLETION TIMELINE",
            font=theme.font(13, bold=True), text_color=theme.NEON,
        ).pack(anchor="w", padx=4, pady=(8, 2))

        self.chart_canvas = tk.Canvas(
            scroll, bg=theme.BG_MAIN, height=170,
            highlightthickness=1, highlightbackground=theme.BORDER,
        )
        self.chart_canvas.pack(fill="x", padx=4, pady=(0, 8))
        self.render_timeline_chart(self.report)

        # Histogram
        self.render_wait_histogram(self.report, scroll)

    def _build_bottom_bar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=theme.BG_PANEL, corner_radius=0,
                           border_width=1, border_color=theme.BORDER)
        bar.pack(fill="x")
        ctk.CTkButton(
            bar, text="EXPORT PDF", width=160, corner_radius=0, height=36,
            fg_color=theme.NEON_BLUE, text_color=theme.BG_MAIN,
            hover_color="#009fcc", font=theme.font(14, bold=True),
            command=lambda: self.export_pdf(self.report),
        ).pack(side="right", padx=16, pady=8)

    # ── Render methods ────────────────────────────────────────────────────────

    def render_metrics(self, r: Report) -> None:
        if self.metrics_frame is None:
            return
        for w in self.metrics_frame.winfo_children():
            w.destroy()

        def section(label: str, row: int) -> None:
            """Render a non-data section header row."""
            hdr = ctk.CTkFrame(self.metrics_frame, fg_color=theme.BG_INPUT, corner_radius=0)
            hdr.grid(row=row, column=0, columnspan=2, sticky="ew", padx=6, pady=(6, 1))
            self.metrics_frame.columnconfigure(0, weight=1)
            ctk.CTkLabel(
                hdr, text=label,
                font=theme.font(11, bold=True), text_color=theme.NEON_BLUE, anchor="w",
            ).pack(side="left", padx=12, pady=4)

        def data_row(label: str, value: str, row: int, even: bool) -> None:
            bg    = theme.BG_ROW if even else theme.BG_PANEL
            row_f = ctk.CTkFrame(self.metrics_frame, fg_color=bg, corner_radius=0)
            row_f.grid(row=row, column=0, columnspan=2, sticky="ew", padx=6, pady=1)
            self.metrics_frame.columnconfigure(0, weight=1)
            ctk.CTkLabel(
                row_f, text=label,
                font=theme.font(12), text_color=theme.TEXT, anchor="w",
            ).pack(side="left", padx=16, pady=6)
            ctk.CTkLabel(
                row_f, text=value,
                font=theme.font(12, bold=True), text_color=theme.NEON_BLUE, anchor="e",
            ).pack(side="right", padx=16, pady=6)

        r_idx = 0

        # ── Section: Timing ───────────────────────────────────────────────────
        section("COMPLETION TIMING", r_idx); r_idx += 1
        timing_rows = [
            ("First product completed",   f"cycle {r.first_product_completed_time}"),
            ("Last product completed",    f"cycle {r.last_product_completed_time}"),
            ("Simulation makespan",       f"{r.total_processing_time} cycles"),
            ("Avg completion time",       f"{r.average_execution_time:.2f} cycles"),
            ("Throughput",                f"{r.throughput_rate:.4f} products / cycle"),
        ]
        for i, (lbl, val) in enumerate(timing_rows):
            data_row(lbl, val, r_idx, i % 2 == 0); r_idx += 1

        # ── Section: Products ─────────────────────────────────────────────────
        section("PRODUCTS", r_idx); r_idx += 1
        data_row("Products completed", str(r.completed_products), r_idx, True); r_idx += 1

        # ── Section: Bottleneck & Congestion ─────────────────────────────────
        section("BOTTLENECK & CONGESTION", r_idx); r_idx += 1
        bottleneck_rows = [
            ("Bottleneck process (highest total load)", r.bottleneck),
            ("Max time a product spent in one process", f"{r.max_waiting_time_process} cycles"),
            ("Avg queue wait across all tasks",         f"{r.average_waiting_time_to_start_task:.2f} cycles"),
            ("Max single-task queue wait",              f"{r.max_waiting_time_task} cycles"),
            ("  ↳ Task with max queue wait",            r.max_waiting_task_name  or "N/A"),
            ("  ↳ Process of that task",                r.max_waiting_task_process or "N/A"),
        ]
        for i, (lbl, val) in enumerate(bottleneck_rows):
            data_row(lbl, val, r_idx, i % 2 == 0); r_idx += 1

        # Bottleneck highlight banner
        bn = ctk.CTkFrame(
            self.metrics_frame, fg_color="#1c0a1a", corner_radius=0,
            border_width=1, border_color=theme.NEON_RED,
        )
        bn.grid(row=r_idx, column=0, columnspan=2, sticky="ew", padx=6, pady=(6, 10))
        ctk.CTkLabel(
            bn, text=f"🔴  BOTTLENECK:  {r.bottleneck}",
            font=theme.font(14, bold=True), text_color=theme.NEON_RED,
        ).pack(padx=12, pady=8)

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
        H = c.winfo_height() or 170

        total  = max(r.total_processing_time, 1)
        margin = 70

        def x_of(t: int) -> float:
            return margin + (t / total) * (W - margin * 2)

        c.create_line(margin, H - 32, W - margin, H - 32,
                      fill=theme.BORDER_LIT, width=1)

        x1 = x_of(r.first_product_completed_time)
        c.create_rectangle(margin, 20, x1, 64, fill=theme.NEON, outline="")
        c.create_text(margin + 6, 42,
                      text=f"First: t={r.first_product_completed_time}",
                      fill=theme.BG_MAIN, anchor="w",
                      font=(theme.FONT_FAMILY, 9, "bold"))

        x2 = x_of(r.last_product_completed_time)
        c.create_rectangle(margin, 74, x2, 118, fill=theme.NEON_BLUE, outline="")
        c.create_text(margin + 6, 96,
                      text=f"Last: t={r.last_product_completed_time}",
                      fill=theme.BG_MAIN, anchor="w",
                      font=(theme.FONT_FAMILY, 9, "bold"))

        xa = x_of(int(r.average_execution_time))
        c.create_line(xa, 10, xa, H - 32, fill=theme.NEON_AMBER, dash=(4, 3), width=2)
        c.create_text(xa + 4, 14,
                      text=f"avg={r.average_execution_time:.1f}",
                      fill=theme.NEON_AMBER, anchor="w",
                      font=(theme.FONT_FAMILY, 8))

        for pct in range(0, 101, 25):
            tx = margin + (pct / 100) * (W - margin * 2)
            tv = int(total * pct / 100)
            c.create_line(tx, H - 35, tx, H - 29, fill=theme.TEXT_DIM)
            c.create_text(tx, H - 16, text=str(tv),
                          fill=theme.TEXT_DIM, font=(theme.FONT_FAMILY, 8))

    def render_wait_histogram(self, r: Report, scroll_parent) -> None:
        """Bar chart for key wait / congestion metrics."""
        frame = ctk.CTkFrame(scroll_parent, fg_color="transparent")
        frame.pack(fill="x", padx=4, pady=(0, 12))

        ctk.CTkLabel(
            frame, text="CONGESTION METRICS (bar chart)",
            font=theme.font(13, bold=True), text_color=theme.NEON,
        ).pack(anchor="w", padx=4, pady=(4, 4))

        hist_canvas = tk.Canvas(
            frame, bg=theme.BG_MAIN, height=160,
            highlightthickness=1, highlightbackground=theme.BORDER,
        )
        hist_canvas.pack(fill="x", padx=4)
        self.after(150, self._draw_histogram, hist_canvas, r)

    def _draw_histogram(self, c: tk.Canvas, r: Report) -> None:
        c.delete("all")
        c.update_idletasks()
        W = c.winfo_width() or 600
        H = c.winfo_height() or 160

        metrics = [
            ("Avg\nqueue wait",  r.average_waiting_time_to_start_task, theme.NEON_BLUE),
            ("Max task\nwait",   r.max_waiting_time_task,              theme.NEON_RED),
            ("Max proc\ntime",   r.max_waiting_time_process,           theme.NEON_AMBER),
            ("Avg\ncompletion",  r.average_execution_time,             theme.NEON),
        ]
        max_val   = max((v for _, v, _ in metrics), default=1) or 1
        n         = len(metrics)
        bar_w     = (W - 60) // n - 16
        margin    = 30
        bar_max_h = H - 56

        for i, (label, val, color) in enumerate(metrics):
            bh   = max(4, int((val / max_val) * bar_max_h))
            x    = margin + i * (bar_w + 16)
            ytop = H - 34 - bh
            c.create_rectangle(x, ytop, x + bar_w, H - 34, fill=color, outline="")
            # Value above bar
            c.create_text(x + bar_w // 2, max(ytop - 10, 4),
                          text=f"{val:.1f}", fill=theme.TEXT,
                          font=(theme.FONT_FAMILY, 8, "bold"))
            # Label below axis
            for j, part in enumerate(label.split("\n")):
                c.create_text(x + bar_w // 2, H - 20 + j * 11, text=part,
                              fill=theme.TEXT_DIM, font=(theme.FONT_FAMILY, 7))

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

        doc    = SimpleDocTemplate(path, pagesize=A4,
                                   leftMargin=2*cm, rightMargin=2*cm,
                                   topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "Title2", parent=styles["Title"], fontSize=20, spaceAfter=6,
            textColor=colors.HexColor("#2c3e50"), alignment=TA_CENTER,
        )
        h2_style = ParagraphStyle(
            "H2", parent=styles["Heading2"], fontSize=13,
            textColor=colors.HexColor("#2980b9"), spaceBefore=12,
        )
        h3_style = ParagraphStyle(
            "H3", parent=styles["Heading3"], fontSize=11,
            textColor=colors.HexColor("#1a7a4a"), spaceBefore=8,
        )
        body_style = styles["BodyText"]

        story = [
            Paragraph("LinProd — Simulation Report", title_style),
            Paragraph(
                "CE-5507 · Instituto Tecnológico de Costa Rica · Semester 1, 2026",
                ParagraphStyle("Sub", parent=styles["Normal"],
                               alignment=TA_CENTER, fontSize=9,
                               textColor=colors.gray),
            ),
            Spacer(1, 0.4*cm),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor("#2980b9")),
            Spacer(1, 0.3*cm),
        ]

        # ── TIMING section ────────────────────────────────────────────────────
        story.append(Paragraph("Completion Timing", h2_style))
        timing_data = [
            ["Metric", "Value"],
            ["First product completed",    f"cycle {r.first_product_completed_time}"],
            ["Last product completed",     f"cycle {r.last_product_completed_time}"],
            ["Simulation makespan",        f"{r.total_processing_time} cycles"],
            ["Average completion time",    f"{r.average_execution_time:.2f} cycles"],
            ["Throughput",                 f"{r.throughput_rate:.4f} products / cycle"],
        ]
        story.append(_make_table(timing_data))

        # ── PRODUCTS section ──────────────────────────────────────────────────
        story.append(Paragraph("Products", h2_style))
        prod_data = [
            ["Metric", "Value"],
            ["Products completed", str(r.completed_products)],
        ]
        story.append(_make_table(prod_data))

        # ── BOTTLENECK & CONGESTION section ───────────────────────────────────
        story.append(Paragraph("Bottleneck & Congestion", h2_style))
        bottleneck_data = [
            ["Metric", "Value"],
            ["Bottleneck process (highest total load)",    r.bottleneck],
            ["Max time a product spent in one process",    f"{r.max_waiting_time_process} cycles"],
            ["Avg queue wait across all tasks",            f"{r.average_waiting_time_to_start_task:.2f} cycles"],
            ["Max single-task queue wait",                 f"{r.max_waiting_time_task} cycles"],
            ["Task with max queue wait",                   r.max_waiting_task_name  or "N/A"],
            ["Process of that task",                       r.max_waiting_task_process or "N/A"],
        ]
        story.append(_make_table(bottleneck_data))

        story += [
            Spacer(1, 0.5*cm),
            Paragraph("Bottleneck Analysis", h2_style),
            Paragraph(
                f"The process identified as the main bottleneck is "
                f"<b>{r.bottleneck}</b> — it accumulated the highest total "
                f"product-processing load across the run. "
                f"The task that caused the single longest queue wait was "
                f"<b>{r.max_waiting_task_name or 'N/A'}</b> "
                f"(in process <b>{r.max_waiting_task_process or 'N/A'}</b>), "
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


# ── PDF helper ────────────────────────────────────────────────────────────────

def _make_table(data: list[list[str]]):
    """Build a styled ReportLab Table from a list-of-rows (first row = header)."""
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import Table, TableStyle

    tbl = Table(data, colWidths=[10*cm, 6*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0), colors.HexColor("#2980b9")),
        ("TEXTCOLOR",      (0, 0), (-1, 0), colors.white),
        ("FONTNAME",       (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",       (0, 0), (-1, 0), 11),
        ("ALIGN",          (0, 0), (-1, -1), "LEFT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#ecf0f1"), colors.white]),
        ("GRID",           (0, 0), (-1, -1), 0.4, colors.HexColor("#bdc3c7")),
        ("PADDING",        (0, 0), (-1, -1), 6),
    ]))
    return tbl
