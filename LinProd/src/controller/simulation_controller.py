"""
simulation_controller.py
------------------------
Handles all user interactions during the active simulation phase.

SimulationController sits between SimulationView (button presses, sliders) and
SimulationEngine (clock, background thread). It translates UI events into engine
calls and maintains the small amount of simulation-phase state that does not
belong in the engine itself (product count, color cycling, step-mode flag).

Key behaviours:
  - on_run(n)        — batch-injects n products then starts the engine.
  - on_inject_product() — injects one additional product at runtime without
                           advancing the clock; updates the expected count so
                           auto-stop works correctly.
  - on_toggle_step_mode() — switches between continuous and manual-step modes.
                            In step mode the background thread is never started;
                            on_step(n) advances exactly n cycles synchronously.
  - on_reset(soft=True)  — delegates to MainController.on_reset(True), which
                            calls engine.reset() and fires SIMULATION_RESET.
  - on_reset(soft=False) — delegates to MainController.on_reset(False), which
                            tears down the engine and navigates to SetupView.

Product colour assignment cycles through _COLORS using the product ID modulo
the palette length, so the same colour repeats predictably on long runs.

The already_started parameter enables the "return from report" use-case:
MainController passes already_started=True when recreating SimulationController
after the user navigates back from ReportView, so the play button shows
"RESUME" instead of "PLAY" and no new products are injected on run.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Callable

from src.model.simulation_engine import SimulationEngine
from src.model.product import Product

if TYPE_CHECKING:
    from src.view.simulation_view import SimulationView


class SimulationController:
    """
    Mediates between SimulationView UI events and SimulationEngine.

    Maintains simulation-phase-specific state (product count, next ID, step
    mode) that is reset on each soft reset but would be inappropriate to store
    inside the engine.

    Relationships:
        - Created by: MainController.start_simulation() and _go_back_to_sim()
        - Drives: SimulationEngine (run / pause / reset / step / inject)
        - Drives: SimulationView (show_pause_snapshot, apply_engine_speed)
        - Receives callbacks from: MainController (on_report, on_reset)
    """

    # Fixed colour palette cycled by product ID for visual distinction on the canvas.
    _COLORS = ["red", "blue", "green", "orange", "purple", "cyan",
               "yellow", "pink", "magenta", "teal"]

    def __init__(
        self,
        engine:          SimulationEngine,
        view:            "SimulationView",
        on_report:       Callable,
        on_reset:        Callable[[bool], None],
        already_started: bool = False,
    ) -> None:
        """
        Parameters
        ----------
        engine : SimulationEngine
            The shared engine instance that owns the clock and background thread.
        view : SimulationView
            The simulation UI. Receives direct calls for snapshots and speed sync.
        on_report : Callable
            Zero-argument callback invoked when the user requests the report.
            Supplied by MainController — calls MainController.show_report().
        on_reset : Callable[[bool], None]
            Single-bool callback for reset delegation. True = soft reset;
            False = full reset back to SetupView.
        already_started : bool
            Pass True when re-entering simulation from the report screen so the
            controller knows products are already in the line and the play
            button should read "RESUME". Defaults to False for fresh runs.
        """
        self._engine:           SimulationEngine       = engine
        self._view:             "SimulationView"       = view
        self._on_report:        Callable               = on_report
        self._on_reset:         Callable[[bool], None] = on_reset

        self._n_products:         int  = 0      # total products currently expected by the engine
        self._step_mode:          bool = False   # True while manual-step mode is active
        self._next_product_id:    int  = 1       # auto-incrementing ID for the next injected product
        self._simulation_started: bool = already_started

        # Sync the speed slider in the view to match the engine's current speed setting.
        self._view.apply_engine_speed(self._engine.simulation_speed)

    # ── State ─────────────────────────────────────────────────────────────────

    @property
    def simulation_started(self) -> bool:
        """
        True once on_run() has been called at least once for the current run.

        Used by SimulationView._update_play_btn() to decide whether to show
        PLAY, RESUME, or PAUSE on the primary action button.
        """
        return self._simulation_started

    # ── Run / lifecycle ───────────────────────────────────────────────────────

    def on_run(self, n_products: int) -> None:
        """
        Inject n_products into the first process and start the engine.

        Products are created with sequential IDs starting at 1 and colours
        cycled from _COLORS. All products are injected at the current clock
        time (time = 0 on a fresh run) before the engine advances.

        In step mode the engine is NOT started automatically — the user must
        press the step button to advance the clock.

        Parameters
        ----------
        n_products : int
            Number of products to inject into the pipeline.
        """
        self._n_products        = n_products
        self._next_product_id   = 1
        self._simulation_started = True
        self._engine.set_expected_products(n_products)

        for i in range(n_products):
            p = Product(
                product_id=i + 1,
                color=self._COLORS[i % len(self._COLORS)],
                size=1,
                created_time=self._engine.current_time,
            )
            self._engine.production_line.add_product(p, self._engine.current_time)
            self._next_product_id = i + 2

        if not self._step_mode:
            self._engine.run()

    def on_pause(self) -> None:
        """
        Pause the simulation and display a full pipeline state snapshot in the log.

        Calls engine.pause() (which fires SIMULATION_PAUSED) then asks the view
        to print the current positions of all products in each task.
        """
        self._engine.pause()
        self._view.show_pause_snapshot()

    def on_resume(self) -> None:
        """
        Resume a paused simulation in continuous mode.

        No-op in step mode — the user must use the step button instead.
        """
        if not self._step_mode:
            self._engine.run()

    def on_reset(self, soft: bool = True) -> None:
        """
        Reset the simulation, delegating to MainController for the actual work.

        Always pauses the engine first to stop the background thread before
        any state is cleared.

        Parameters
        ----------
        soft : bool
            True  → soft reset: clears in-flight state, stays on SimulationView.
                    Resets internal product tracking (n_products, next_id, started).
            False → full reset: delegates to MainController which tears down the
                    engine and navigates to SetupView.
        """
        self._engine.pause()
        if soft:
            self._on_reset(True)          # triggers engine.reset() → SIMULATION_RESET event
            self._n_products         = 0
            self._next_product_id    = 1
            self._simulation_started = False
        else:
            self._on_reset(False)

    def on_speed_change(self, speed_ms: int) -> None:
        """
        Adjust the simulation tick interval.

        Parameters
        ----------
        speed_ms : int
            New delay between ticks in milliseconds. Takes effect on the next
            iteration of the background loop without requiring a restart.
        """
        self._engine.set_simulation_speed(speed_ms)

    def on_request_report(self) -> None:
        """
        Navigate to the report screen by invoking the MainController callback.

        Does not pause the engine — MainController.show_report() simply switches
        the active view; the engine state is preserved for the "back to sim" path.
        """
        self._on_report()

    # ── Step / inject controls ────────────────────────────────────────────────

    def on_toggle_step_mode(self) -> bool:
        """
        Toggle between continuous and manual-step modes.

        When enabling step mode, the engine is paused immediately. When
        disabling step mode the engine is NOT auto-resumed — the user must
        press PLAY/RESUME explicitly.

        Returns
        -------
        bool
            The new step-mode state (True = step mode active).
        """
        self._step_mode = not self._step_mode
        if self._step_mode:
            self._engine.pause()
        return self._step_mode

    def on_step(self, n: int = 1) -> None:
        """
        Advance the simulation by exactly n clock cycles synchronously.

        Only meaningful in step mode; calling this in continuous mode while
        the background thread is running would cause a race condition, so
        the view only enables the step button when step mode is active.

        Parameters
        ----------
        n : int
            Number of cycles to advance (default 1).
        """
        self._engine.step(n)

    def on_inject_product(self) -> None:
        """
        Inject one additional product into the running simulation without
        advancing the clock.

        Increments both the product counter and the engine's expected-products
        target so the auto-stop logic remains correct. The new product receives
        the next sequential ID and the corresponding cycled colour.
        """
        p = Product(
            product_id=self._next_product_id,
            color=self._COLORS[(self._next_product_id - 1) % len(self._COLORS)],
            size=1,
            created_time=self._engine.current_time,
        )
        self._engine.production_line.add_product(p, self._engine.current_time)
        self._next_product_id += 1
        self._n_products      += 1
        self._engine.set_expected_products(self._n_products)
