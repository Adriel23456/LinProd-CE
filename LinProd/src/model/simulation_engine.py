from __future__ import annotations
import time
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .event_dispatcher import EventDispatcher

from .production_line import ProductionLine
from .report_center import ReportCenter
from .simulation_event import SimulationEvent
from .simulation_event_type import SimulationEventType


class SimulationEngine:
    def __init__(self, production_line: ProductionLine, dispatcher: "EventDispatcher") -> None:
        self.current_time:     int               = 0
        self.is_running:       bool              = False
        self.production_line:  ProductionLine    = production_line
        self.report_center:    ReportCenter      = ReportCenter()
        self.simulation_speed: int               = 500
        self.event_dispatcher: "EventDispatcher" = dispatcher
        self._thread:          threading.Thread | None = None

        dispatcher.subscribe(self.report_center)

    def tick(self) -> list:
        self.current_time += 1
        completed = self.production_line.advance(self.current_time)
        return completed

    def run(self) -> None:
        self.is_running = True
        self.event_dispatcher.notify(SimulationEvent(
            event_type=SimulationEventType.SIMULATION_STARTED,
            time=self.current_time,
        ))
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while self.is_running:
            self.tick()
            time.sleep(self.simulation_speed / 1000)

    def pause(self) -> None:
        self.is_running = False
        self.event_dispatcher.notify(SimulationEvent(
            event_type=SimulationEventType.SIMULATION_PAUSED,
            time=self.current_time,
        ))

    def reset(self, soft: bool) -> None:
        self.is_running   = False
        self.current_time = 0
        self.report_center = ReportCenter()
        self.event_dispatcher.subscribe(self.report_center)

        if soft:
            # Clear all queues and in-flight state, keep structure
            for proc in self.production_line.processes:
                proc.products_in_process.clear()
                for task in proc.tasks:
                    task.awaiting_products_fifo.clear()
                    task.current_product  = None
                    task.remaining_time   = 0

        self.event_dispatcher.notify(SimulationEvent(
            event_type=SimulationEventType.SIMULATION_RESET,
            time=0,
        ))

    def set_simulation_speed(self, speed: int) -> None:
        self.simulation_speed = speed