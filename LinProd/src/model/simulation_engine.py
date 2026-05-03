from __future__ import annotations
import time
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .event_dispatcher import EventDispatcher

from .production_line import ProductionLine
from .product import Product
from .report_center import ReportCenter
from .report import Report
from .simulation_event import SimulationEvent
from .simulation_event_type import SimulationEventType


class SimulationEngine:
    """
    Controls simulation lifecycle and discrete time.

    Owns the clock, a background thread (continuous mode), and ReportCenter.
    Exposed only through generate_report() per DIP (V-SOLID-DIP-03).

    V-BUG-01 fix: reset() unsubscribes the old ReportCenter before replacing it.
    """

    def __init__(self, production_line: ProductionLine, dispatcher: "EventDispatcher") -> None:
        self._current_time:        int                    = 0
        self._is_running:          bool                   = False
        self._production_line:     ProductionLine         = production_line
        self._report_center:       ReportCenter           = ReportCenter()
        self._simulation_speed:    int                    = 500
        self._event_dispatcher:    "EventDispatcher"      = dispatcher
        self._thread:              threading.Thread | None = None
        self._expected_products:   int                    = 0
        self._completed_products:  int                    = 0

        dispatcher.subscribe(self._report_center)

    # ── Public read-only state ────────────────────────────────────────────────

    @property
    def current_time(self) -> int:
        return self._current_time

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def production_line(self) -> ProductionLine:
        return self._production_line

    @property
    def simulation_speed(self) -> int:
        return self._simulation_speed

    # ── Setup ─────────────────────────────────────────────────────────────────

    def set_expected_products(self, n: int) -> None:
        """Tell the engine how many products to wait for before auto-stopping."""
        self._expected_products  = n
        self._completed_products = 0

    # ── Simulation control ────────────────────────────────────────────────────

    def tick(self) -> list[Product]:
        """Advance one cycle. Fires SIMULATION_FINISHED when all products complete."""
        self._current_time += 1
        completed = self._production_line.advance(self._current_time)

        if self._expected_products > 0:
            self._completed_products += len(completed)
            if self._completed_products >= self._expected_products:
                self._is_running = False
                self._event_dispatcher.notify(SimulationEvent(
                    event_type=SimulationEventType.SIMULATION_FINISHED,
                    time=self._current_time,
                ))

        return completed

    def step(self, n: int = 1) -> list[Product]:
        """Advance exactly n cycles manually (step mode; no background thread)."""
        result: list[Product] = []
        for _ in range(n):
            result.extend(self.tick())
            # Stop early if all expected products have completed
            if (self._expected_products > 0
                    and self._completed_products >= self._expected_products):
                break
        return result

    def run(self) -> None:
        """Start continuous background-thread simulation."""
        self._is_running = True
        self._event_dispatcher.notify(SimulationEvent(
            event_type=SimulationEventType.SIMULATION_STARTED,
            time=self._current_time,
        ))
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def pause(self) -> None:
        self._is_running = False
        self._event_dispatcher.notify(SimulationEvent(
            event_type=SimulationEventType.SIMULATION_PAUSED,
            time=self._current_time,
        ))

    def reset(self) -> None:
        """Soft reset: clear in-flight state, keep line structure."""
        self._is_running         = False
        self._current_time       = 0
        self._completed_products = 0

        # Unsubscribe old instance first (V-BUG-01 fix)
        self._event_dispatcher.unsubscribe(self._report_center)
        self._report_center = ReportCenter()
        self._event_dispatcher.subscribe(self._report_center)

        for proc in self._production_line.processes:
            proc.reset_state()

        self._event_dispatcher.notify(SimulationEvent(
            event_type=SimulationEventType.SIMULATION_RESET,
            time=0,
        ))

    def set_simulation_speed(self, speed: int) -> None:
        self._simulation_speed = speed

    # ── Report delegation (V-SOLID-DIP-03) ───────────────────────────────────

    def generate_report(self) -> Report:
        return self._report_center.generate_report()

    # ── Private ──────────────────────────────────────────────────────────────

    def _loop(self) -> None:
        while self._is_running:
            self.tick()
            time.sleep(self._simulation_speed / 1000)
