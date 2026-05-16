"""
report_center.py
----------------
Implements the statistics-accumulation Observer for the simulation.

ReportCenter subscribes to every SimulationEvent on the shared EventDispatcher
and updates internal accumulators as the simulation runs. At any point (typically
after SIMULATION_FINISHED), callers may invoke generate_report() to obtain a
frozen Report snapshot of everything collected so far.

ReportCenter is replaced on every soft reset: SimulationEngine.reset() calls
EventDispatcher.unsubscribe() on the old instance and subscribe() on a fresh one,
so accumulated statistics never bleed across runs (V-BUG-01 fix).

Events consumed:
    PRODUCT_COMPLETED     → records completion time, updates first/last product IDs
    TASK_WAIT_RECORDED    → records task queue wait, updates max-wait accumulators
    PROCESS_FINISHED      → records product-in-process duration, updates max-time
    TASK_FINISHED         → accumulates pure processing load per process (bottleneck)
"""

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
    Stateful statistics accumulator that implements the Observer interface.

    All internal accumulators are private; external code accesses results
    only through generate_report(). The public rec_* methods are part of the
    class diagram interface but should be called exclusively from update() —
    direct calls from outside would bypass the event-driven accumulation model.

    V-BUG-02 fix: PROCESS_FINISHED carries the actual clock time in event.time
    (not a pre-computed duration). Duration is computed here as:
        event.time - product.current_process_arrival_time

    Relationships:
        - Implements: Observer
        - Created by: SimulationEngine.__init__() and SimulationEngine.reset()
        - Subscribed to: EventDispatcher (same instance shared across all model objects)
        - Produces: Report (via generate_report())
        - Read by: SimulationEngine.generate_report() → ReportView
    """

    def __init__(self) -> None:
        """
        Initialise all accumulators to their zero / empty state.

        Called fresh on every soft reset by SimulationEngine so that statistics
        from previous runs never carry over.
        """
        # All queue-wait durations seen across all products and tasks (cycles).
        self._waiting_times_task:         list[int]            = []
        # Completion cycle for every product that cleared the entire line.
        self._completed_times:            list[int]            = []
        # Running maximum of task queue-wait; updated whenever a new record is set.
        self._max_waiting_time_task:      int                  = 0
        # Name of the task responsible for the current max queue-wait record.
        self._max_waiting_time_task_name: str                  = ""
        # Name of the process that contains the max-wait task.
        self._max_waiting_time_task_proc: str                  = ""
        # Running maximum of product-in-process duration (arrival → exit, cycles).
        self._max_process_time:           int                  = 0
        # Name of the process responsible for the current max in-process duration.
        self._max_process_time_name:      str                  = ""
        # IDs of the first and last products to complete (for future display use).
        self._first_p_completed_id:       int                  = -1
        self._last_p_completed_id:        int                  = -1
        # Per-process list of individual product-in-process durations (for averages).
        self._process_duration_map:       dict[str, list[int]] = {}
        # Per-process cumulative processing load (sum of task processing_time × count).
        # Used exclusively for bottleneck detection via get_bottleneck().
        self._process_pure_load_map:      dict[str, int]       = {}

    # ── Observer protocol ─────────────────────────────────────────────────────

    def update(self, event: SimulationEvent) -> None:
        """
        Dispatch an incoming simulation event to the appropriate accumulator.

        Called by EventDispatcher.notify() from the simulation background thread.
        All accumulation is purely in-memory (no I/O), so thread-safety is not
        a concern here — no Tkinter widget access occurs.

        Parameters
        ----------
        event : SimulationEvent
            The event that just occurred. Only the four types listed in the
            module docstring are handled; all others are silently ignored.
        """
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
            # V-BUG-02: event.time is the clock cycle, not a pre-computed duration.
            duration = event.time - event.product.current_process_arrival_time
            self.rec_process_time(event.product, event.process_name or "", duration)

        elif event.event_type == SimulationEventType.TASK_FINISHED:  # NEW
            if event.process_name:
                self._process_pure_load_map[event.process_name] = (
                    self._process_pure_load_map.get(event.process_name, 0)
                    + event.task_processing_time
                )

    # ── Public accumulator methods (per class diagram) ────────────────────────

    def rec_product_completed(self, product: "Product", time: int) -> None:
        """
        Record that a product has exited the entire production line.

        Appends the completion cycle to the sorted completion-times list and
        updates the first/last completed product IDs.

        Parameters
        ----------
        product : Product
            The product that just completed (used to capture its ID).
        time : int
            The simulation clock cycle at which the product completed.
        """
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
        """
        Record a task queue-wait observation and update the max-wait record.

        Called only when wait_time > 0 (Task._start_processing suppresses the
        event for products that go straight to an idle machine).

        Parameters
        ----------
        product : Product
            The product that waited (not stored, kept for future extensibility).
        task_name : str
            Name of the task where the wait occurred.
        process_name : str
            Name of the process that contains task_name.
        wait_time : int
            Cycles the product spent queuing before processing began.
        """
        self._waiting_times_task.append(wait_time)
        if wait_time > self._max_waiting_time_task:
            self._max_waiting_time_task      = wait_time
            self._max_waiting_time_task_name = task_name
            self._max_waiting_time_task_proc = process_name

    def rec_process_time(self, product: "Product", process_name: str, duration: int) -> None:
        """
        Record the end-to-end duration a product spent inside one process.

        Duration = PROCESS_FINISHED.time − product.current_process_arrival_time.
        Updates the running maximum and appends to the per-process duration list.

        Parameters
        ----------
        product : Product
            The product that just exited the process (not stored directly).
        process_name : str
            Name of the process that was just exited.
        duration : int
            Cycles elapsed from process entry to process exit.
        """
        self._process_duration_map.setdefault(process_name, []).append(duration)
        if duration > self._max_process_time:
            self._max_process_time      = duration
            self._max_process_time_name = process_name

    # ── Analytics ─────────────────────────────────────────────────────────────

    def get_bottleneck(self) -> str:
        """
        Return the name of the process with the highest cumulative processing load.

        Load is measured as the sum of task_processing_time across all TASK_FINISHED
        events attributed to each process. The process that spent the most total
        cycles actively processing (ignoring queue waits) is the bottleneck.

        Returns
        -------
        str
            Process name, or "N/A" if no TASK_FINISHED events were recorded.
        """
        if not self._process_pure_load_map:
            return "N/A"
        return max(self._process_pure_load_map, key=lambda k: self._process_pure_load_map[k])

    def calc_average_execution_time(self) -> float:
        """
        Compute the mean completion time across all finished products.

        Returns
        -------
        float
            Mean of all recorded completion cycles, or 0.0 if none.
        """
        if not self._completed_times:
            return 0.0
        return sum(self._completed_times) / len(self._completed_times)

    def generate_report(self) -> Report:
        """
        Build and return a frozen Report from the current accumulator state.

        Can be called at any point during or after the simulation. Fields that
        depend on at least one completed product default to 0 / 0.0 / "" if
        no products have finished yet.

        Returns
        -------
        Report
            Immutable snapshot of all accumulated statistics.
        """
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
