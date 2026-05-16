"""
report_view.py
--------------
Report screen displayed after a simulation run completes (or on demand).

ReportView receives an immutable Report value object and renders its statistics
in three sections:
  1. Metrics table   — grouped into COMPLETION TIMING, PRODUCTS, BOTTLENECK &
                       CONGESTION; alternating row backgrounds for readability.
  2. Timeline chart  — a horizontal bar chart showing first-product time,
                       last-product time (makespan), and average completion time.
  3. Congestion histogram — four vertical bars comparing avg queue wait, max
                            task wait, max process time, and avg completion time.

Navigation:
  "simulation" button → returns to the simulation screen (engine preserved).
  "new setup" button  → asks for confirmation then does a full reset to SetupView.

PDF export:
  "export pdf" button → uses ReportLab to build an A4 document with the same
  three data sections as separate tables plus a narrative bottleneck analysis.

Module-level helpers (private implementation details):
  _canvas_rounded_rect() — shared rounded-rect drawing used by the two canvas charts.
  _make_table()          — builds a ReportLab Table with the standard colour scheme.

Relationships:
    - Created by: MainController.show_report()
    - Receives: Report (immutable; stored as self.report)
    - Callbacks: on_go_to_simulation → _go_back_to_sim, on_go_to_setup → _full_reset
"""

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
    Displays the simulation Report with metrics, charts, and PDF export.

    Aesthetic deliberately matches SimulationView (same colours, rounded panels,
    pill navigation buttons at the top). All content is inside a
    CTkScrollableFrame so long reports are fully accessible regardless of window
    height.

    Diagram attributes (V-CD-11):
        metrics_frame : CTkFrame   — statistics table container
        chart_canvas  : tk.Canvas  — completion timeline chart

    Relationships:
        - Created by: MainController.show_report()
        - Reads: Report (frozen dataclass; all fields are read-only)
        - Uses: ReportLab for PDF generation (imported lazily in _write_pdf)
    """

    def __init__(
        self,
        parent,
        report: Report,
        on_go_to_simulation: Callable,
        on_go_to_setup: Callable,
    ) -> None:
        """
        Parameters
        ----------
        parent : ctk.CTk | ctk.CTkFrame
            Root window or parent frame.
        report : Report
            Immutable statistics snapshot produced by ReportCenter.generate_report().
        on_go_to_simulation : Callable
            Zero-argument callback; invoked when the user clicks "simulation".
            Supplied by MainController (_go_back_to_sim).
        on_go_to_setup : Callable
            Zero-argument callback; invoked after confirmation when the user
            clicks "new setup". Supplied by MainController (_full_reset).
        """
        super().__init__(parent, fg_color=theme.BG_MAIN)
        self.report:       Report   = report
        self._go_to_sim:   Callable = on_go_to_simulation
        self._go_to_setup: Callable = on_go_to_setup

        # Diagram-required widget attributes (set during _build)
        self.metrics_frame: ctk.CTkFrame | None = None
        self.chart_canvas:  tk.Canvas    | None = None

        self._build()

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build(self) -> None:
        """
        Construct the full report screen layout.

        Three stacked rows:
          row 0 — top bar (title, nav buttons)
          row 1 — scrollable content area (metrics, timeline, histogram)
          row 2 — bottom bar (export PDF button)
        """
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        self._build_top_bar()
        self._build_scroll_area()
        self._build_bottom_bar()

    # ── Top bar  (matches SimulationView top bar style) ───────────────────────

    def _build_top_bar(self) -> None:
        """
        Build the top bar with a "report" title, a decorative pill, and nav buttons.

        "simulation" button → calls _go_to_sim (MainController._go_back_to_sim).
        "new setup" button  → calls _confirm_new_setup which asks for confirmation.
        """
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
        """
        Build the scrollable main content area containing all three report sections.

        Layout (top to bottom inside a CTkScrollableFrame):
          1. Metrics card        — statistics table (render_metrics)
          2. Timeline card       — horizontal bar chart (render_timeline_chart)
          3. Congestion metrics  — vertical histogram (render_wait_histogram)
        """
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
            timeline_card, bg=theme.BG_MAIN, height=180,
            highlightthickness=0,
        )
        self.chart_canvas.pack(fill="x", padx=12, pady=(0, 12))
        self.render_timeline_chart(self.report)

        # ── Congestion Metrics card ───────────────────────────────────────────
        self.render_wait_histogram(self.report, scroll)

    # ── Bottom bar (matches SimulationView bottom bar style) ──────────────────

    def _build_bottom_bar(self) -> None:
        """
        Build the bottom bar containing the "export pdf" action button.
        """
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
        """
        Populate the metrics_frame with a grouped statistics table.

        Clears any existing content then renders three sections, each with a
        coloured section header and alternating-background data rows:
          COMPLETION TIMING  — first/last completion, makespan, avg, throughput
          PRODUCTS           — completed product count
          BOTTLENECK & CONGESTION — bottleneck process, wait times, max-wait details

        A highlighted bottleneck banner is appended at the bottom.

        Parameters
        ----------
        r : Report
            The frozen statistics snapshot to display.
        """
        if self.metrics_frame is None:
            return
        for w in self.metrics_frame.winfo_children():
            w.destroy()

        def section_header(label: str) -> None:
            """Render a blue-accented section header row."""
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
            """Render one label/value pair row with alternating background."""
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
        """
        Bind the timeline canvas to <Configure> and schedule an initial draw.

        The actual drawing is deferred to after_idle() so the canvas has its
        real pixel width before _draw_timeline() is called.

        Parameters
        ----------
        r : Report
            Statistics used to compute bar widths and label values.
        """
        if self.chart_canvas is None:
            return
        self.chart_canvas.bind(
            "<Configure>", lambda _e: self._draw_timeline(r)
        )
        self.after_idle(self._draw_timeline, r)

    def _draw_timeline(self, r: Report) -> None:
        """
        Draw the completion timeline chart on self.chart_canvas.

        Renders:
          - A horizontal axis scaled to total_processing_time.
          - A dark bar from 0 to first_product_completed_time.
          - A NEON bar from 0 to last_product_completed_time (makespan).
          - A dashed NEON_AMBER vertical line at average_execution_time.
          - Tick marks and labels at 0%, 25%, 50%, 75%, 100% of makespan.

        Parameters
        ----------
        r : Report
            Statistics snapshot to draw.
        """
        if self.chart_canvas is None:
            return
        c = self.chart_canvas
        c.delete("all")
        W = c.winfo_width() or 600
        H = c.winfo_height() or 180

        total  = max(r.total_processing_time, 1)
        margin = 70

        def x_of(t: int | float) -> float:
            return margin + (t / total) * (W - margin * 2)

        # Axis
        c.create_line(
            margin, H - 36, W - margin, H - 36,
            fill=theme._PANEL_BD, width=1,
        )

        # First product bar
        x1 = x_of(r.first_product_completed_time)
        _canvas_rounded_rect(
            c, margin, 16, x1, 64, r=8,
            fill=theme._BTN_ADD, outline="",
        )
        c.create_text(
            margin + 10, 40,
            text=f"First: t={r.first_product_completed_time}",
            fill=theme._TEXT_MAIN, anchor="w",
            font=theme.font(13, family=theme.FONT_BOLD),
        )

        # Last product bar
        x2 = x_of(r.last_product_completed_time)
        _canvas_rounded_rect(
            c, margin, 72, x2, 120, r=8,
            fill=theme.NEON, outline="",
        )
        c.create_text(
            margin + 10, 96,
            text=f"Last: t={r.last_product_completed_time}",
            fill=theme.BG_MAIN, anchor="w",
            font=theme.font(13, family=theme.FONT_BOLD),
        )

        # Avg line
        xa = x_of(r.average_execution_time)
        c.create_line(
            xa, 10, xa, H - 36,
            fill=theme.NEON_AMBER, dash=(4, 3), width=2,
        )
        c.create_text(
            xa + 6, 12,
            text=f"avg={r.average_execution_time:.1f}",
            fill=theme.NEON_AMBER, anchor="nw",
            font=theme.font(12, family=theme.FONT_BOLD),
        )

        # Tick marks
        for pct in range(0, 101, 25):
            tx = margin + (pct / 100) * (W - margin * 2)
            tv = int(total * pct / 100)
            c.create_line(tx, H - 39, tx, H - 33, fill=theme._TEXT_DIM2)
            c.create_text(
                tx, H - 14, text=str(tv),
                fill=theme._TEXT_DIM2,
                font=theme.font(11, family=theme.FONT_BOLD),
            )

    # ── Render: congestion histogram ──────────────────────────────────────────

    def render_wait_histogram(self, r: Report, scroll_parent) -> None:
        """
        Build the congestion metrics card and schedule a histogram draw.

        Creates a card frame inside scroll_parent, then draws four vertical
        bars representing avg queue wait, max task wait, max process time, and
        avg completion time. Each bar is colour-coded by severity.

        Parameters
        ----------
        r : Report
            Statistics used for bar heights and labels.
        scroll_parent : ctk.CTkScrollableFrame
            The scrollable container to pack the card into.
        """
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
            card, bg=theme.BG_MAIN, height=220,
            highlightthickness=0,
        )
        hist_canvas.pack(fill="x", padx=12, pady=(0, 12))
        hist_canvas.bind(
            "<Configure>", lambda _e: self._draw_histogram(hist_canvas, r)
        )
        self.after_idle(self._draw_histogram, hist_canvas, r)

    def _draw_histogram(self, c: tk.Canvas, r: Report) -> None:
        """
        Draw four vertical bars on the congestion histogram canvas.

        Bar heights are scaled proportionally to the maximum value among the
        four metrics. Each bar shows its numeric value above and a two-line
        label below the axis.

        Parameters
        ----------
        c : tk.Canvas
            Target canvas (from render_wait_histogram).
        r : Report
            Statistics snapshot to draw.
        """
        c.delete("all")
        W = c.winfo_width() or 600
        H = c.winfo_height() or 220

        metrics = [
            ("Avg\nqueue wait",  r.average_waiting_time_to_start_task, theme.NEON),
            ("Max task\nwait",   r.max_waiting_time_task,              theme.NEON_RED),
            ("Max proc\ntime",   r.max_waiting_time_process,           theme.NEON_AMBER),
            ("Avg\ncompletion",  r.average_execution_time,             theme._BTN_ADD),
        ]
        max_val   = max((v for _, v, _ in metrics), default=1) or 1
        n         = len(metrics)
        gap       = 28
        margin    = 40
        bar_w     = (W - 2 * margin - gap * (n - 1)) // n
        label_h   = 44   # space reserved for two-line labels under axis
        value_h   = 22   # space reserved for value above bar
        bar_max_h = H - label_h - value_h - 10
        axis_y    = H - label_h

        for i, (label, val, color) in enumerate(metrics):
            bh   = max(4, int((val / max_val) * bar_max_h))
            x    = margin + i * (bar_w + gap)
            ytop = axis_y - bh

            _canvas_rounded_rect(
                c, x, ytop, x + bar_w, axis_y,
                r=8, fill=color, outline="",
            )

            # Value above bar
            c.create_text(
                x + bar_w // 2, max(ytop - 12, 10),
                text=f"{val:.1f}",
                fill=theme._TEXT_MAIN,
                font=theme.font(12, family=theme.FONT_BOLD),
            )
            # Label below axis
            for j, part in enumerate(label.split("\n")):
                c.create_text(
                    x + bar_w // 2, axis_y + 12 + j * 16,
                    text=part,
                    fill=theme._TEXT_DIM2,
                    font=theme.font(11, family=theme.FONT_BOLD),
                )

    # ── PDF export ────────────────────────────────────────────────────────────

    def export_pdf(self, r: Report) -> None:
        """
        Open a save-file dialog and export the report to a PDF file.

        Shows a success messagebox on completion or an error messagebox if
        ReportLab raises an exception. Delegates actual PDF construction to
        _write_pdf().

        Parameters
        ----------
        r : Report
            Statistics snapshot to export.
        """
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
        """
        Build and write the A4 PDF report using ReportLab.

        Imports ReportLab lazily (only when the user clicks "export pdf") so
        the rest of the application does not depend on it at startup. The PDF
        contains:
          - Title and course subtitle.
          - Three data tables (Completion Timing, Products, Bottleneck & Congestion).
          - A narrative bottleneck analysis paragraph.
          - Authors section.

        Parameters
        ----------
        path : str
            Destination file path (must end with .pdf).
        r : Report
            Statistics snapshot to write.
        """
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
        """
        Ask the user to confirm before discarding all simulation data.

        Shows a yes/no dialog; invokes _go_to_setup (MainController._full_reset)
        only if the user confirms.
        """
        if messagebox.askyesno(
            "Reset simulation",
            "This will clear all production data and return to setup.\nContinue?",
        ):
            self._go_to_setup()


# ── Canvas helper (mirrors _rounded_rect in simulation_view) ──────────────────

def _canvas_rounded_rect(
    canvas: tk.Canvas, x1, y1, x2, y2, r=8, **kw
) -> int:
    """
    Draw a filled rounded rectangle on a tk.Canvas and return its item ID.

    Used by both render_timeline_chart and _draw_histogram. Mirrors the
    _rounded_rect helper in simulation_view.py.

    Parameters
    ----------
    canvas : tk.Canvas
        Target canvas.
    x1, y1, x2, y2 : int | float
        Bounding box coordinates.
    r : int
        Corner radius in pixels.
    **kw
        Additional keyword arguments forwarded to canvas.create_polygon
        (e.g. fill, outline).

    Returns
    -------
    int
        Canvas item ID of the created polygon.
    """
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
    """
    Build a styled ReportLab Table for the PDF report.

    Applies a standard visual style:
      - Blue header row with white bold text.
      - Alternating light-grey / white data rows.
      - Subtle grid lines.

    Parameters
    ----------
    data : list[list[str]]
        Table data where data[0] is the header row and subsequent rows are
        data rows. Each inner list must have exactly 2 elements (label, value).

    Returns
    -------
    reportlab.platypus.Table
        Fully styled table ready to append to a ReportLab story.
    """
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