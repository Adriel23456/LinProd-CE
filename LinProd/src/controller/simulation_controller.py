from __future__ import annotations
from typing import Callable
from src.model.simulation_engine import SimulationEngine
from src.model.product import Product
from src.view.simulation_view import SimulationView


class SimulationController:
    def __init__(
        self,
        engine:    SimulationEngine,
        view:      SimulationView,
        on_report: Callable,
        on_reset:  Callable[[bool], None],
    ) -> None:
        self.engine    = engine
        self.view      = view
        self._on_report = on_report
        self._on_reset  = on_reset

    def on_run(self, n_products: int) -> None:
        colors = ["red", "blue", "green", "orange", "purple", "cyan"]
        for i in range(n_products):
            p = Product(
                product_id=i + 1,
                color=colors[i % len(colors)],
                size=1,
                created_time=self.engine.current_time,
            )
            self.engine.production_line.add_product(p, self.engine.current_time)
        self.engine.run()

    def on_pause(self) -> None:
        self.engine.pause()
        self.view.show_pause_snapshot()

    def on_resume(self) -> None:
        self.engine.run()

    def on_reset(self, soft: bool) -> None:
        self._on_reset(soft)

    def on_speed_change(self, speed_ms: int) -> None:
        self.engine.set_simulation_speed(speed_ms)

    def on_request_report(self) -> None:
        self._on_report()