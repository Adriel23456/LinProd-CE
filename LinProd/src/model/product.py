"""
product.py
----------
Defines the Product domain object — the item that flows through the production line.

A Product carries its own identity (id, color, size, created_time) and a set of
timing attributes that are updated as it moves through Tasks and Processes. All
timing writes are done through explicit setter methods to preserve encapsulation;
no external code should set private attributes directly.

Products do NOT accumulate history themselves — ReportCenter owns all statistics.
The timing attributes on Product are the "current" values used by ReportCenter
to compute wait durations at event time.
"""


class Product:
    """
    Represents an item moving through the production line.

    Identity attributes (id, color, size, created_time) are read-only after
    construction. Simulation-state attributes are updated exclusively through
    dedicated methods to enforce encapsulation.

    Relationships:
        - Created by SimulationController.on_run() or on_inject_product().
        - Injected into ProductionLine.add_product() at the start.
        - Its timing fields are written by Task._start_processing() and
          Process.receive_product() as it moves through the pipeline.
        - ReportCenter reads timing fields inside its accumulator methods.
    """

    def __init__(self, product_id: int, color: str, size: int, created_time: int) -> None:
        """
        Parameters
        ----------
        product_id : int
            Unique integer identifier (1-based, assigned by SimulationController).
        color : str
            Display colour for the simulation canvas (e.g. "red", "blue").
        size : int
            Abstract unit size (currently always 1; reserved for future use).
        created_time : int
            Simulation clock cycle when this product was injected into the line.
        """
        self._id:                           int = product_id
        self._color:                        str = color
        self._size:                         int = size
        self._created_time:                 int = created_time
        self._completed_time:               int = 0
        # Arrival time at the current task (reset each time a task is entered)
        self._current_task_arrival_time:    int = 0
        # Arrival time at the current process (reset each time a process is entered)
        self._current_process_arrival_time: int = 0
        # How long the product waited in the queue at the current task before processing
        self._current_task_waiting_time:    int = 0
        # Accumulated waiting time within the current process (reserved for future use)
        self._current_process_waiting_time: int = 0

    # ── Read-only identity ────────────────────────────────────────────────────

    @property
    def id(self) -> int:
        """Unique integer identifier assigned at construction."""
        return self._id

    @property
    def color(self) -> str:
        """Display colour string used by SimulationView canvas drawing."""
        return self._color

    @property
    def size(self) -> int:
        """Abstract unit size (always 1 in the current implementation)."""
        return self._size

    @property
    def created_time(self) -> int:
        """Simulation clock cycle when this product was injected."""
        return self._created_time

    # ── Simulation-state (read) ───────────────────────────────────────────────

    @property
    def completed_time(self) -> int:
        """Simulation cycle when this product exited the last process (0 if not done)."""
        return self._completed_time

    @property
    def current_task_arrival_time(self) -> int:
        """Cycle when the product entered the queue of the current task."""
        return self._current_task_arrival_time

    @property
    def current_process_arrival_time(self) -> int:
        """Cycle when the product entered the current process."""
        return self._current_process_arrival_time

    @property
    def current_task_waiting_time(self) -> int:
        """Cycles the product waited in the task queue before processing began."""
        return self._current_task_waiting_time

    @property
    def current_process_waiting_time(self) -> int:
        """Accumulated wait time within the current process (for future use)."""
        return self._current_process_waiting_time

    # ── Simulation-state (write) ─ called only by Task / Process / ProductionLine ──

    def record_task_arrival(self, time: int) -> None:
        """Record the cycle at which this product joined a task's queue."""
        self._current_task_arrival_time = time

    def record_process_arrival(self, time: int) -> None:
        """Record the cycle at which this product entered a process."""
        self._current_process_arrival_time = time

    def record_task_wait(self, wait: int) -> None:
        """
        Store the queue wait time for the task that just started processing.

        Called by Task._start_processing() immediately before TASK_WAIT_RECORDED
        is dispatched, so ReportCenter can read product.current_task_waiting_time
        from the event handler.
        """
        self._current_task_waiting_time = wait

    def accumulate_process_wait(self, wait: int) -> None:
        """Add to the running process-level wait accumulator (reserved for future stats)."""
        self._current_process_waiting_time += wait

    def mark_completed(self, time: int) -> None:
        """Called by ProductionLine when the product exits the last process."""
        self._completed_time = time

    def __repr__(self) -> str:
        return f"Product(id={self._id}, color={self._color})"
