from __future__ import annotations
import customtkinter as ctk

from src.model.event_dispatcher import EventDispatcher
from src.model.production_line import ProductionLine
from src.model.simulation_engine import SimulationEngine
from src.view.setup_view import SetupView
from src.view.simulation_view import SimulationView
from src.view.report_view import ReportView
from .setup_controller import SetupController
from .simulation_controller import SimulationController


class MainController:
    def __init__(self, root: ctk.CTk) -> None:
        self.root               = root
        self.dispatcher         = EventDispatcher()
        self.production_line    = ProductionLine(self.dispatcher)
        self.engine             = SimulationEngine(self.production_line, self.dispatcher)

        self.setup_ctrl:        SetupController      | None = None
        self.simulation_ctrl:   SimulationController | None = None
        self.report_view:       ReportView           | None = None

    def start_setup(self) -> None:
        view = SetupView(self.root, on_confirm=self._on_setup_confirmed)
        self.setup_ctrl = SetupController(self.production_line, view)
        view.pack(fill="both", expand=True)

    def _on_setup_confirmed(self, n_products: int) -> None:
        sim_view = SimulationView(self.root, self.dispatcher)
        self.simulation_ctrl = SimulationController(
            engine=self.engine,
            view=sim_view,
            on_report=self.show_report,
            on_reset=self.on_reset,
        )
        sim_view.pack(fill="both", expand=True)
        self.simulation_ctrl.on_run(n_products)

    def show_report(self) -> None:
        report = self.engine.report_center.generate_report()
        self.report_view = ReportView(self.root, report)
        self.report_view.pack(fill="both", expand=True)

    def on_reset(self, soft: bool) -> None:
        if soft:
            self.engine.reset(soft=True)
        else:
            self.production_line = ProductionLine(self.dispatcher)
            self.engine = SimulationEngine(self.production_line, self.dispatcher)
            self.start_setup()