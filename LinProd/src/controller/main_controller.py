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
    """
    Top-level orchestrator. Owns the shared EventDispatcher, ProductionLine,
    and SimulationEngine. Manages transitions between Setup → Simulation → Report.

    Navigation flow:
      setup confirmed   → start_simulation()  (no auto-start; user must press PLAY)
      PLAY pressed      → SimulationController.on_run(n) via SimulationView
      report requested  → show_report()
      ◀ back to sim     → _go_back_to_sim()
      ⟳ new setup       → _full_reset()
    """

    def __init__(self, root: ctk.CTk) -> None:
        self._root:            ctk.CTk                    = root
        self._dispatcher:      EventDispatcher            = EventDispatcher()
        self._production_line: ProductionLine             = ProductionLine(self._dispatcher)
        self._engine:          SimulationEngine           = SimulationEngine(
            self._production_line, self._dispatcher
        )
        self._active_view: ctk.CTkFrame | None = None

        self._setup_ctrl:  SetupController      | None = None
        self._sim_ctrl:    SimulationController | None = None
        self._report_view: ReportView           | None = None

    # ── View switching ────────────────────────────────────────────────────────

    def _switch_to(self, view: ctk.CTkFrame) -> None:
        if self._active_view is not None and self._active_view.winfo_exists():
            self._active_view.pack_forget()
            self._active_view.destroy()
        self._active_view = view
        view.pack(fill="both", expand=True)

    # ── Phase transitions ─────────────────────────────────────────────────────

    def start_setup(self) -> None:
        view = SetupView(self._root, on_confirm=self._on_setup_confirmed)
        self._setup_ctrl = SetupController(self._production_line, view)
        view.controller  = self._setup_ctrl
        self._switch_to(view)

    def _on_setup_confirmed(self) -> None:
        self.start_simulation()

    def start_simulation(self) -> None:
        """V-CD-03: transition to SimulationView. Does NOT auto-start the engine."""
        sim_view = SimulationView(self._root, self._dispatcher)
        self._sim_ctrl = SimulationController(
            engine=self._engine,
            view=sim_view,
            on_report=self.show_report,
            on_reset=self.on_reset,
        )
        sim_view.controller = self._sim_ctrl
        self._switch_to(sim_view)

    def show_report(self) -> None:
        report = self._engine.generate_report()
        report_view = ReportView(
            self._root,
            report,
            on_go_to_simulation=self._go_back_to_sim,
            on_go_to_setup=self._full_reset,
        )
        self._report_view = report_view
        self._switch_to(report_view)

    def on_reset(self, soft: bool) -> None:
        if soft:
            self._engine.reset()
        else:
            self._production_line = ProductionLine(self._dispatcher)
            self._engine          = SimulationEngine(self._production_line, self._dispatcher)
            self.start_setup()

    def _go_back_to_sim(self) -> None:
        """Return to SimulationView without re-running (engine state preserved)."""
        self._engine.pause()
        sim_view = SimulationView(self._root, self._dispatcher)
        self._sim_ctrl = SimulationController(
            engine=self._engine,
            view=sim_view,
            on_report=self.show_report,
            on_reset=self.on_reset,
            already_started=True,
        )
        sim_view.controller = self._sim_ctrl
        sim_view.set_paused_state()
        self._switch_to(sim_view)

    def _full_reset(self) -> None:
        """Full teardown: new line + new engine → SetupView."""
        self._production_line = ProductionLine(self._dispatcher)
        self._engine          = SimulationEngine(self._production_line, self._dispatcher)
        self.start_setup()
