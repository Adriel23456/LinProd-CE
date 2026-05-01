from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .product import Product
    from .event_dispatcher import EventDispatcher

from .task import Task
from .simulation_event import SimulationEvent
from .simulation_event_type import SimulationEventType


class Process:
    def __init__(self, name: str, dispatcher: "EventDispatcher") -> None:
        self.name:               str                    = name
        self.tasks:              list[Task]             = []
        self.products_in_process:list["Product"]        = []
        self.event_dispatcher:   "EventDispatcher"      = dispatcher
        self.previous_process:   "Process | None"       = None

    def add_task(self, task: Task) -> None:
        self.tasks.append(task)

    def receive_product(self, product: "Product", current_time: int) -> None:
        product.current_process_arrival_time = current_time
        self.products_in_process.append(product)
        self.event_dispatcher.notify(SimulationEvent(
            event_type=SimulationEventType.PROCESS_STARTED,
            time=current_time,
            product=product,
            process_name=self.name,
        ))
        self.tasks[0].receive_product(product, current_time)

    def move_prod_to_next_task(self, product: "Product", task: Task, current_time: int) -> bool:
        """Returns True if product exited the process (finished last task)."""
        idx = self.tasks.index(task)
        if idx + 1 < len(self.tasks):
            self.tasks[idx + 1].receive_product(product, current_time)
            return False
        return True

    def advance(self, current_time: int) -> list["Product"]:
        completed: list["Product"] = []
        for task in self.tasks:
            finished = task.advance(current_time)
            if finished is not None:
                exited = self.move_prod_to_next_task(finished, task, current_time)
                if exited:
                    self.products_in_process.remove(finished)
                    self.event_dispatcher.notify(SimulationEvent(
                        event_type=SimulationEventType.PROCESS_FINISHED,
                        time=current_time,
                        product=finished,
                        process_name=self.name,
                    ))
                    completed.append(finished)
        return completed

    def __repr__(self) -> str:
        return f"Process(name={self.name}, tasks={len(self.tasks)})"