from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .product import Product

from .observer import Observer
from .simulation_event import SimulationEvent
from .simulation_event_type import SimulationEventType
from .report import Report


class ReportCenter(Observer):
    """
    Observes simulation events and accumulates all statistics.

    All internal accumulators are private; external code accesses results
    only through generate_report(). Public rec_* methods are exposed per the
    class diagram but should be called only from update().

    V-BUG-02 fix: PROCESS_FINISHED event.time is now the clock time, so
    duration is computed here as event.time - product.current_process_arrival_time.
    """

    def __init__(self) -> None:
        self._waiting_times_task:         list[int]            = []
        self._completed_times:            list[int]            = []
        self._max_waiting_time_task:      int                  = 0
        self._max_waiting_time_task_name: str                  = ""
        self._max_waiting_time_task_proc: str                  = ""
        self._max_process_time:           int                  = 0
        self._max_process_time_name:      str                  = ""
        self._first_p_completed_id:       int                  = -1
        self._last_p_completed_id:        int                  = -1
        self._process_duration_map:       dict[str, list[int]] = {}

    # ── Observer protocol ─────────────────────────────────────────────────────

    def update(self, event: SimulationEvent) -> None:
        if event.event_type == SimulationEventType.PRODUCT_COMPLETED:
            self.rec_product_completed(event.product, event.time)

        elif event.event_type == SimulationEventType.TASK_WAIT_RECORDED:
            self.rec_waiting_time_task(
                event.product,
                event.task_name or "",
                event.process_name or "",
                event.product.current_task_waiting_time,
            )

        elif event.event_type == SimulationEventType.PROCESS_FINISHED:
            duration = event.time - event.product.current_process_arrival_time
            self.rec_process_time(event.product, event.process_name or "", duration)

    # ── Public accumulator methods (per class diagram) ────────────────────────

    def rec_product_completed(self, product: "Product", time: int) -> None:
        self._completed_times.append(time)
        if self._first_p_completed_id == -1:
            self._first_p_completed_id = product.id
        self._last_p_completed_id = product.id

    def rec_waiting_time_task(
        self,
        product: "Product",
        task_name: str,
        process_name: str,
        wait_time: int,
    ) -> None:
        self._waiting_times_task.append(wait_time)
        if wait_time > self._max_waiting_time_task:
            self._max_waiting_time_task      = wait_time
            self._max_waiting_time_task_name = task_name
            self._max_waiting_time_task_proc = process_name

    def rec_process_time(self, product: "Product", process_name: str, duration: int) -> None:
        self._process_duration_map.setdefault(process_name, []).append(duration)
        if duration > self._max_process_time:
            self._max_process_time      = duration
            self._max_process_time_name = process_name

    # ── Analytics ─────────────────────────────────────────────────────────────

    def get_bottleneck(self) -> str:
        if not self._process_duration_map:
            return "N/A"
        return max(
            self._process_duration_map,
            key=lambda k: sum(self._process_duration_map[k]),
        )

    def calc_average_execution_time(self) -> float:
        if not self._completed_times:
            return 0.0
        return sum(self._completed_times) / len(self._completed_times)

    def generate_report(self) -> Report:
        avg_wait = (
            sum(self._waiting_times_task) / len(self._waiting_times_task)
            if self._waiting_times_task else 0.0
        )
        makespan        = self._completed_times[-1] if self._completed_times else 0
        n_completed     = len(self._completed_times)
        throughput_rate = n_completed / makespan if makespan > 0 else 0.0

        return Report(
            first_product_completed_time=        self._completed_times[0]  if self._completed_times else 0,
            last_product_completed_time=         self._completed_times[-1] if self._completed_times else 0,
            average_execution_time=              self.calc_average_execution_time(),
            total_processing_time=               makespan,
            completed_products=                  n_completed,
            throughput_rate=                     throughput_rate,
            bottleneck=                          self.get_bottleneck(),
            average_waiting_time_to_start_task=  avg_wait,
            max_waiting_time_task=               self._max_waiting_time_task,
            max_waiting_task_name=               self._max_waiting_time_task_name,
            max_waiting_task_process=            self._max_waiting_time_task_proc,
            max_waiting_time_process=            self._max_process_time,
        )
