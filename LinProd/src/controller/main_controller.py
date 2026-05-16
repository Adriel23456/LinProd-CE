"""
main_controller.py
------------------
Top-level application orchestrator; the first object instantiated by main.py.

MainController owns the three shared infrastructure objects that must outlive
any single phase of the application:
  - EventDispatcher  — shared event bus wired into every model object.
  - ProductionLine   — the pipeline structure being configured and simulated.
  - SimulationEngine — the clock and background thread.

It is solely responsible for phase transitions between the three application
screens:

    SetupView  ──(confirm)──▶  SimulationView  ──(report)──▶  ReportView
                                     ▲                              │
                                     └──────────(back to sim)───────┘
                                     ▲
                                     └──────────(full reset)────────▶  SetupView

Navigation callbacks are passed as closures into subordinate controllers and
views, so those layers never import MainController (no upward dependency).

Design notes:
  - Only one CTkFrame is visible at a time; _switch_to() destroys the previous
    view before showing the next one to free Tkinter widget resources.
  - The EventDispatcher is intentionally never replaced — its observer list
    persists across phase transitions so ReportCenter always receives events
    even if the SimulationView is swapped out.
  - A full reset (on_reset(soft=False) or "new setup") creates a fresh
    ProductionLine and SimulationEngine but reuses the same dispatcher and root.
"""

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
    Top-level orchestrator that bootstraps the application and manages all
    phase transitions between Setup, Simulation, and Report screens.

    Owns the shared infrastructure (EventDispatcher, ProductionLine,
    SimulationEngine) and composes the phase-specific controllers
    (SetupController, SimulationController) as the application progresses.

    Navigation flow:
      setup confirmed   → start_simulation()   (no auto-start; user presses PLAY)
      PLAY pressed      → SimulationController.on_run(n) via SimulationView
      report requested  → show_report()
      ◀ back to sim     → _go_back_to_sim()
      ⟳ new setup       → _full_reset()

    Relationships:
        - Created by: main.py immediately after the CTk root window
        - Owns: EventDispatcher, ProductionLine, SimulationEngine
        - Composes: SetupController, SimulationController
        - Hosts views inside: ctk.CTk root window (single-frame swap pattern)
    """

    def __init__(self, root: ctk.CTk) -> None:
        """
        Bootstrap all shared infrastructure and show the initial SetupView.

        Parameters
        ----------
        root : ctk.CTk
            The top-level CustomTkinter application window. All views are
            packed directly into this root and destroyed on phase transitions.
        """
        self._root:            ctk.CTk                    = root
        self._dispatcher:      EventDispatcher            = EventDispatcher()
        self._production_line: ProductionLine             = ProductionLine(self._dispatcher)
        self._engine:          SimulationEngine           = SimulationEngine(
            self._production_line, self._dispatcher
        )
        # Currently visible CTkFrame; replaced on every phase transition.
        self._active_view: ctk.CTkFrame | None = None

        # Phase-specific controller references (None until that phase is active).
        self._setup_ctrl:  SetupController      | None = None
        self._sim_ctrl:    SimulationController | None = None
        self._report_view: ReportView           | None = None

    # ── View switching ────────────────────────────────────────────────────────

    def _switch_to(self, view: ctk.CTkFrame) -> None:
        """
        Replace the currently visible view with a new one.

        Destroys the previous view (freeing Tkinter widget resources), then
        packs the new view so it fills the entire root window.

        Parameters
        ----------
        view : ctk.CTkFrame
            The new view to display. It must already be constructed before
            this method is called.
        """
        if self._active_view is not None and self._active_view.winfo_exists():
            self._active_view.pack_forget()
            self._active_view.destroy()
        self._active_view = view
        view.pack(fill="both", expand=True)

    # ── Phase transitions ─────────────────────────────────────────────────────

    def start_setup(self) -> None:
        """
        Transition to the configuration phase (SetupView).

        Creates a fresh SetupView and SetupController, wires the confirm
        callback, and makes the view visible. Called once on application
        startup and again after a full reset.
        """
        view = SetupView(self._root, on_confirm=self._on_setup_confirmed)
        self._setup_ctrl = SetupController(self._production_line, view)
        view.controller  = self._setup_ctrl
        self._switch_to(view)

    def _on_setup_confirmed(self) -> None:
        """
        Callback invoked by SetupView when the user presses "Confirm Setup".

        Delegates immediately to start_simulation() — exists as a named method
        so SetupView does not need a direct reference to MainController.
        """
        self.start_simulation()

    def start_simulation(self) -> None:
        """
        Transition to the simulation phase (SimulationView).

        Creates SimulationView and SimulationController and wires the report
        and reset callbacks. The engine is NOT started automatically — the
        user must press PLAY (V-CD-03 design requirement).

        Parameters
        ----------
        None — uses the existing shared engine and production line.
        """
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
        """
        Transition to the report phase (ReportView).

        Retrieves the current statistics snapshot from the engine and passes
        the immutable Report to a new ReportView. Navigation callbacks allow
        the user to return to simulation or start a completely new setup.
        """
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
        """
        Handle a reset request originating from SimulationController.

        Parameters
        ----------
        soft : bool
            True  → soft reset: engine.reset() clears in-flight state, keeps
                    structure. Stays on SimulationView.
            False → full reset: creates a new ProductionLine and SimulationEngine,
                    then navigates back to SetupView.
        """
        if soft:
            self._engine.reset()
        else:
            self._production_line = ProductionLine(self._dispatcher)
            self._engine          = SimulationEngine(self._production_line, self._dispatcher)
            self.start_setup()

    def _go_back_to_sim(self) -> None:
        """
        Return to SimulationView from ReportView without discarding engine state.

        Pauses the engine (in case it was still running), then constructs a
        fresh SimulationView in the "already started / paused" state. The view
        shows a RESUME button instead of PLAY so the user can continue from
        where they left off without re-injecting products.
        """
        self._engine.pause()
        sim_view = SimulationView(self._root, self._dispatcher)
        self._sim_ctrl = SimulationController(
            engine=self._engine,
            view=sim_view,
            on_report=self.show_report,
            on_reset=self.on_reset,
            already_started=True,   # tells controller that products are already in the line
        )
        sim_view.controller = self._sim_ctrl
        sim_view.set_paused_state()   # forces the play button to show "RESUME"
        self._switch_to(sim_view)

    def _full_reset(self) -> None:
        """
        Tear down the current simulation entirely and start fresh from SetupView.

        Replaces both the ProductionLine and SimulationEngine with new instances
        while reusing the same EventDispatcher and root window. Called when the
        user navigates "new setup" from the ReportView.
        """
        self._production_line = ProductionLine(self._dispatcher)
        self._engine          = SimulationEngine(self._production_line, self._dispatcher)
        self.start_setup()
