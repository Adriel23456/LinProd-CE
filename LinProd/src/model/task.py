from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .product import Product
    from .event_dispatcher import EventDispatcher

from .simulation_event import SimulationEvent
from .simulation_event_type import SimulationEventType


class Task:
    def __init__(self, name: str, processing_time: int, dispatcher: "EventDispatcher") -> None:
        self.name:                   str                  = name
        self.processing_time:        int                  = processing_time
        self.awaiting_products_fifo: list["Product"]      = []
        self.remaining_time:         int                  = 0
        self.current_product:        "Product | None"     = None
        self.event_dispatcher:       "EventDispatcher"    = dispatcher

    def is_busy(self) -> bool:
        return self.current_product is not None

    def receive_product(self, product: "Product", current_time: int) -> None:
        product.current_task_arrival_time = current_time
        if not self.is_busy():
            self._start_processing(product, current_time)
        else:
            self.awaiting_products_fifo.append(product)

    def _start_processing(self, product: "Product", current_time: int) -> None:
        self.current_product = product
        self.remaining_time  = self.processing_time
        self.event_dispatcher.notify(SimulationEvent(
            event_type=SimulationEventType.TASK_STARTED,
            time=current_time,
            product=product,
            task_name=self.name,
        ))

    def advance(self, current_time: int) -> "Product | None":
        if not self.is_busy():
            return None

        self.remaining_time -= 1

        if self.remaining_time == 0:
            finished          = self.current_product
            self.current_product = None
            self.event_dispatcher.notify(SimulationEvent(
                event_type=SimulationEventType.TASK_FINISHED,
                time=current_time,
                product=finished,
                task_name=self.name,
            ))
            if self.awaiting_products_fifo:
                next_product = self.awaiting_products_fifo.pop(0)
                self._start_processing(next_product, current_time)
            return finished

        return None

    def __repr__(self) -> str:
        return f"Task(name={self.name}, proc_time={self.processing_time})"