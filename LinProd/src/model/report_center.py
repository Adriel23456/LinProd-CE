from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .product import Product

from .observer import Observer
from .simulation_event import SimulationEvent
from .simulation_event_type import SimulationEventType
from .report import Report


class ReportCenter(Observer):
    def __init__(self) -> None:
        self.waiting_times_task:        list[int] = []
        self.completed_times:           list[int] = []
        self.max_waiting_time_task:     int       = 0
        self.max_waiting_time_task_name:str       = ""
        self.max_process_time:          int       = 0
        self.max_process_time_name:     str       = ""
        self.first_p_completed_id:      int       = -1
        self.last_p_completed_id:       int       = -1
        self._process_wait_map:         dict[str, list[int]] = {}

    def update(self, event: SimulationEvent) -> None:
        if event.event_type == SimulationEventType.PRODUCT_COMPLETED:
            self.rec_product_completed(event.product, event.time)
        elif event.event_type == SimulationEventType.TASK_WAIT_RECORDED:
            self.rec_waiting_time_task(event.product, event.task_name, event.time)
        elif event.event_type == SimulationEventType.PROCESS_FINISHED:
            self.rec_process_time(event.product, event.process_name, event.time)

    def rec_product_completed(self, product: "Product", time: int) -> None:
        self.completed_times.append(time)
        if self.first_p_completed_id == -1:
            self.first_p_completed_id = product.id
        self.last_p_completed_id = product.id

    def rec_waiting_time_task(self, product: "Product", task_name: str, wait_time: int) -> None:
        self.waiting_times_task.append(wait_time)
        if wait_time > self.max_waiting_time_task:
            self.max_waiting_time_task      = wait_time
            self.max_waiting_time_task_name = task_name

    def rec_process_time(self, product: "Product", process_name: str, process_time: int) -> None:
        self._process_wait_map.setdefault(process_name, []).append(process_time)
        if process_time > self.max_process_time:
            self.max_process_time      = process_time
            self.max_process_time_name = process_name

    def get_bottleneck(self) -> str:
        if not self._process_wait_map:
            return "N/A"
        return max(self._process_wait_map, key=lambda k: sum(self._process_wait_map[k]))

    def calc_average_execution_time(self) -> float:
        if not self.completed_times:
            return 0.0
        return sum(self.completed_times) / len(self.completed_times)

    def generate_report(self) -> Report:
        return Report(
            first_product_completed_time=       self.completed_times[0] if self.completed_times else 0,
            last_product_completed_time=        self.completed_times[-1] if self.completed_times else 0,
            average_execution_time=             self.calc_average_execution_time(),
            bottleneck=                         self.get_bottleneck(),
            average_waiting_time_to_start_task= (sum(self.waiting_times_task) / len(self.waiting_times_task)) if self.waiting_times_task else 0.0,
            max_waiting_time_task=              self.max_waiting_time_task,
            max_processing_time_process=        self.max_process_time,
            total_processing_time=              (self.completed_times[-1] if self.completed_times else 0),
            completed_products=                 len(self.completed_times),
        )