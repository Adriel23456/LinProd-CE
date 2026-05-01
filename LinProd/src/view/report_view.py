from __future__ import annotations
import customtkinter as ctk
from src.model.report import Report


class ReportView(ctk.CTkFrame):
    def __init__(self, parent, report: Report) -> None:
        super().__init__(parent)
        self.report = report
        self._build()

    def _build(self) -> None:
        ctk.CTkLabel(self, text="Simulation Report", font=("Arial", 20, "bold")).pack(pady=16)
        self.render_metrics(self.report)

    def render_metrics(self, r: Report) -> None:
        pass  # TODO

    def render_bottleneck(self, r: Report) -> None:
        pass  # TODO

    def render_timeline_chart(self, r: Report) -> None:
        pass  # TODO

    def render_wait_histogram(self, r: Report) -> None:
        pass  # TODO

    def export_pdf(self, r: Report) -> None:
        pass  # TODO