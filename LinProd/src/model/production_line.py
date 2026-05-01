from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .product import Product
    from .event_dispatcher import EventDispatcher

from .process import Process
from .simulation_event import SimulationEvent
from .simulation_event_type import SimulationEventType


class ProductionLine:
    def __init__(self, dispatcher: "EventDispatcher") -> None:
        self.processes:        list[Process]        = []
        self.first_process:    Process | None       = None
        self.last_process:     Process | None       = None
        self.event_dispatcher: "EventDispatcher"    = dispatcher

    def add_process(self, process: Process) -> None:
        if self.processes:
            process.previous_process = self.processes[-1]
        self.processes.append(process)

    def add_product(self, product: "Product", current_time: int) -> None:
        self.event_dispatcher.notify(SimulationEvent(
            event_type=SimulationEventType.PRODUCT_CREATED,
            time=current_time,
            product=product,
        ))
        self.first_process.receive_product(product, current_time)

    def move_prod_to_next_process(self, product: "Product", current_process: Process, current_time: int) -> None:
        idx = self.processes.index(current_process)
        if idx + 1 < len(self.processes):
            self.processes[idx + 1].receive_product(product, current_time)

    def advance(self, current_time: int) -> list["Product"]:
        # Step 1: advance ALL processes first, collect results
        # Same reason as process.py — prevents a product exiting process N
        # from being injected into process N+1 and advanced in the same cycle.
        finished_pairs: list[tuple[Process, list["Product"]]] = []
        for process in self.processes:
            exited = process.advance(current_time)
            if exited:
                finished_pairs.append((process, exited))

        # Step 2: route finished products AFTER all processes have been advanced
        fully_completed: list["Product"] = []
        for process, products in finished_pairs:
            for product in products:
                if process is self.last_process:
                    product.completed_time = current_time
                    self.event_dispatcher.notify(SimulationEvent(
                        event_type=SimulationEventType.PRODUCT_COMPLETED,
                        time=current_time,
                        product=product,
                    ))
                    fully_completed.append(product)
                else:
                    self.move_prod_to_next_process(product, process, current_time)

        return fully_completed