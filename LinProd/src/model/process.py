"""
process.py
----------
Defines the Process model — a named stage of the production line containing
an ordered sequence of Tasks.

Products enter a Process via receive_product(), flow through its Tasks in
order, and exit when the last Task completes. The two-pass advance() design
ensures no product is advanced more than once per tick:

  Pass 1 — advance all tasks (decrement counters, collect finished products)
  Pass 2 — route each finished product to the next task or out of the process

This prevents a product finishing Task N from immediately starting Task N+1
within the same clock cycle (which would be physically impossible).
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .product import Product
    from .event_dispatcher import EventDispatcher

from .task import Task
from .simulation_event import SimulationEvent
from .simulation_event_type import SimulationEventType


class Process:
    """
    A stage of the production line containing an ordered list of Tasks.

    Products enter via receive_product() and flow through tasks in order.
    Internal collections (_tasks, _products_in_process) are encapsulated;
    use the provided factory and mutation methods instead of direct list access.

    Fix V-BUG-02: PROCESS_FINISHED event carries the actual clock time in
    event.time (not the duration). ReportCenter computes duration from
    event.time - product.current_process_arrival_time.

    Attributes
    ----------
    previous_process : Process | None
        Maintained by ProductionLine._rebuild_links(). Used for potential
        back-routing (currently informational only).
    """

    def __init__(self, name: str, dispatcher: "EventDispatcher") -> None:
        """
        Parameters
        ----------
        name : str
            Human-readable identifier shown in the UI (e.g. "Mixing", "Baking").
        dispatcher : EventDispatcher
            Shared event bus; forwarded to each Task created by this process.
        """
        self.name:             str              = name
        self._tasks:           list[Task]       = []
        # Products currently somewhere inside this process (any task or queue).
        self._products_in_process: list["Product"] = []
        self._event_dispatcher: "EventDispatcher" = dispatcher
        self.previous_process: "Process | None" = None

    # ── Public read-only views ────────────────────────────────────────────────

    @property
    def tasks(self) -> list[Task]:
        """Ordered list of Tasks. Use create_task/add_task/remove_task to mutate."""
        return self._tasks

    @property
    def products_in_process(self) -> list["Product"]:
        """All products currently inside this process (at any task or queue)."""
        return self._products_in_process

    # ── Task management ───────────────────────────────────────────────────────

    def create_task(self, name: str, processing_time: int) -> Task:
        """
        Factory: create and register a Task without exposing the dispatcher.

        Parameters
        ----------
        name : str
            Task identifier (e.g. "Mix", "Heat", "Package").
        processing_time : int
            Cycles required to process one product.

        Returns
        -------
        Task
            The newly created and registered Task.
        """
        task = Task(name, processing_time, self._event_dispatcher)
        self.add_task(task)
        return task

    def add_task(self, task: Task) -> None:
        """
        Register a pre-built Task and stamp it with this process's name.

        Setting task.process_name here avoids Task needing a back-reference
        to its parent Process while still allowing TASK_WAIT_RECORDED events
        to carry the process context.
        """
        task.process_name = self.name   # lets Task include process_name in wait events
        self._tasks.append(task)

    def remove_task(self, task_name: str) -> None:
        """Remove the task with the given name (no-op if not found)."""
        self._tasks = [t for t in self._tasks if t.name != task_name]

    def reorder_task(self, task_name: str, new_index: int) -> None:
        """Move a task to a new position in the ordered list."""
        task = next((t for t in self._tasks if t.name == task_name), None)
        if task:
            self._tasks.remove(task)
            self._tasks.insert(new_index, task)

    # ── Simulation interface ──────────────────────────────────────────────────

    def receive_product(self, product: "Product", current_time: int) -> None:
        """
        Accept a product into this process.

        Records the process-arrival time on the product, adds it to the
        in-process tracking list, fires PROCESS_STARTED, then hands the
        product to the first task.

        Parameters
        ----------
        product : Product
            The arriving product.
        current_time : int
            Current simulation clock cycle.
        """
        product.record_process_arrival(current_time)
        self._products_in_process.append(product)
        self._event_dispatcher.notify(SimulationEvent(
            event_type=SimulationEventType.PROCESS_STARTED,
            time=current_time,
            product=product,
            process_name=self.name,
        ))
        # Hand off to the first task immediately.
        self._tasks[0].receive_product(product, current_time)

    def move_prod_to_next_task(self, product: "Product", task: Task, current_time: int) -> bool:
        """
        Route product to the next task in the sequence.

        Called during the second pass of advance() to avoid advancing a
        product into the next task within the same tick it was just completed.

        Parameters
        ----------
        product : Product
            The product that just finished a task.
        task : Task
            The task that just finished processing the product.
        current_time : int
            Current simulation clock cycle.

        Returns
        -------
        bool
            True if the product has exited this process (finished the last task),
            False if it moved to another task within this process.
        """
        idx = self._tasks.index(task)
        if idx + 1 < len(self._tasks):
            # More tasks remain — route to the next one.
            self._tasks[idx + 1].receive_product(product, current_time)
            return False
        # Last task finished — product exits the process.
        return True

    def advance(self, current_time: int) -> list["Product"]:
        """
        Two-pass advance: all tasks tick first, then finished products are routed.

        Pass 1: advance() on every task — collects (task, product) pairs where
                processing completed this cycle.
        Pass 2: route each finished product to the next task or mark it as
                having exited this process.

        This two-pass approach prevents a product from being advanced in two
        different tasks within the same tick.

        Parameters
        ----------
        current_time : int
            Current simulation clock cycle.

        Returns
        -------
        list[Product]
            Products that have exited this process this tick (empty list if none).
        """
        # Pass 1 — tick all tasks and collect any that finished a product.
        finished_pairs: list[tuple[Task, "Product"]] = []
        for task in self._tasks:
            result = task.advance(current_time)
            if result is not None:
                finished_pairs.append((task, result))

        # Pass 2 — route finished products; collect those that exit the process.
        completed: list["Product"] = []
        for task, finished in finished_pairs:
            exited = self.move_prod_to_next_task(finished, task, current_time)
            if exited:
                self._products_in_process.remove(finished)
                # V-BUG-02: emit the actual clock time, NOT a pre-computed duration.
                # ReportCenter computes duration as event.time - product.current_process_arrival_time.
                self._event_dispatcher.notify(SimulationEvent(
                    event_type=SimulationEventType.PROCESS_FINISHED,
                    time=current_time,
                    product=finished,
                    process_name=self.name,
                ))
                completed.append(finished)

        return completed

    def reset_state(self) -> None:
        """
        Clear all in-flight product state without altering task structure.

        Called by SimulationEngine.reset() on a soft reset. The task list
        and process name are preserved; all queued / in-progress products
        are discarded.
        """
        self._products_in_process.clear()
        for task in self._tasks:
            task.reset_state()

    def __repr__(self) -> str:
        return f"Process(name={self.name}, tasks={len(self._tasks)})"
