from __future__ import annotations
from typing import TYPE_CHECKING, Callable

from src.model.simulation_engine import SimulationEngine
from src.model.product import Product

if TYPE_CHECKING:
    from src.view.simulation_view import SimulationView


class SimulationController:
    """
    Handles all user actions during the simulation runtime phase.

    Step mode: when active, time advances only on explicit on_step() calls.
    Inject: on_inject_product() adds one product without advancing time.

    on_reset(soft=True)  → engine.reset() + re-inject same count (if ever run)
    on_reset(soft=False) → delegates to MainController → back to SetupView
    """

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
        self._engine:           SimulationEngine       = engine
        self._view:             "SimulationView"       = view
        self._on_report:        Callable               = on_report
        self._on_reset:         Callable[[bool], None] = on_reset

        self._n_products:       int  = 0
        self._step_mode:        bool = False
        self._next_product_id:  int  = 1
        self._simulation_started: bool = already_started

    # ── State ─────────────────────────────────────────────────────────────────

    @property
    def simulation_started(self) -> bool:
        return self._simulation_started

    # ── Run / lifecycle ───────────────────────────────────────────────────────

    def on_run(self, n_products: int) -> None:
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
        self._engine.pause()
        self._view.show_pause_snapshot()

    def on_resume(self) -> None:
        if not self._step_mode:
            self._engine.run()

    def on_reset(self, soft: bool = True) -> None:
        self._engine.pause()
        if soft:
            self._on_reset(True)          # engine.reset() → SIMULATION_RESET event
            self._n_products         = 0
            self._next_product_id    = 1
            self._simulation_started = False
        else:
            self._on_reset(False)

    def on_speed_change(self, speed_ms: int) -> None:
        self._engine.set_simulation_speed(speed_ms)

    def on_request_report(self) -> None:
        self._on_report()

    # ── Step / inject controls ────────────────────────────────────────────────

    def on_toggle_step_mode(self) -> bool:
        """Toggle step mode. Returns new state."""
        self._step_mode = not self._step_mode
        if self._step_mode:
            self._engine.pause()
        return self._step_mode

    def on_step(self, n: int = 1) -> None:
        """Advance n cycles manually (no auto-inject)."""
        self._engine.step(n)

    def on_inject_product(self) -> None:
        """Inject one new product into the line without advancing time."""
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
