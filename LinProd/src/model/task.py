"""
task.py
-------
Defines the Task model — the atomic processing unit inside a Process.

Each Task represents a single machine or workstation. It maintains its own
FIFO queue, tracks which product is currently being processed, and counts
down the remaining processing cycles. When processing completes, the finished
product is returned to Process.advance() for routing to the next task (or out
of the process entirely).

Critical timing invariant
--------------------------
Task.advance() is called once per tick from Process.advance() during the
first pass. Products finished in that pass are routed in the second pass
(also inside Process.advance()). This two-pass design prevents a product
from advancing through multiple tasks in a single tick.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .product import Product
    from .event_dispatcher import EventDispatcher

from .simulation_event import SimulationEvent
from .simulation_event_type import SimulationEventType


class Task:
    """
    Atomic processing unit — behaves like a single machine inside a Process.

    Public interface: name, processing_time, is_busy(), receive_product(), advance().
    Internal state (_awaiting_products_fifo, _remaining_time, _current_product)
    is managed exclusively by this class.

    Attributes
    ----------
    process_name : str
        Set by Process.add_task() so that TASK_WAIT_RECORDED events carry the
        parent process name without Task needing a back-reference to Process.
    """

    def __init__(self, name: str, processing_time: int, dispatcher: "EventDispatcher") -> None:
        """
        Parameters
        ----------
        name : str
            Human-readable identifier (e.g. "Mix", "Bake", "Pack").
        processing_time : int
            Number of simulation cycles needed to process one product.
        dispatcher : EventDispatcher
            Shared event bus; used to fire TASK_STARTED, TASK_FINISHED, and
            TASK_WAIT_RECORDED events.
        """
        self.name:             str = name
        self.processing_time:  int = processing_time
        # Injected by Process.add_task() so TASK_WAIT_RECORDED events know the parent process.
        self.process_name:     str = ""
        self._awaiting_products_fifo: list["Product"]   = []
        self._remaining_time:         int               = 0
        self._current_product:        "Product | None"  = None
        self._event_dispatcher:       "EventDispatcher" = dispatcher

    # ── Public read-only state ────────────────────────────────────────────────

    @property
    def current_product(self) -> "Product | None":
        """The product currently being processed, or None if idle."""
        return self._current_product

    def is_busy(self) -> bool:
        """Return True if a product is currently being processed."""
        return self._current_product is not None

    # ── Public interface ──────────────────────────────────────────────────────

    def receive_product(self, product: "Product", current_time: int) -> None:
        """
        Accept a product that just arrived at this task.

        If the task is idle, processing starts immediately. Otherwise the
        product is appended to the FIFO queue and will start when the machine
        becomes free.

        Parameters
        ----------
        product : Product
            The arriving product. Its task-arrival time is recorded immediately.
        current_time : int
            Current simulation clock cycle.
        """
        # Record arrival time so that wait duration can be computed when processing starts.
        product.record_task_arrival(current_time)
        if not self.is_busy():
            self._start_processing(product, current_time)
        else:
            self._awaiting_products_fifo.append(product)

    def advance(self, current_time: int) -> "Product | None":
        """
        Decrement the remaining processing time by one cycle.

        Called once per tick from Process.advance() (first pass).

        Returns
        -------
        Product | None
            The product that just finished (remaining_time hit 0), or None if
            still processing (or idle). When a finished product is returned,
            the next queued product (if any) automatically starts.
        """
        if not self.is_busy():
            return None

        self._remaining_time -= 1

        if self._remaining_time == 0:
            # Processing complete — release the product.
            finished              = self._current_product
            self._current_product = None

            self._event_dispatcher.notify(SimulationEvent(
                event_type=SimulationEventType.TASK_FINISHED,
                time=current_time,
                product=finished,
                task_name=self.name,
            ))

            # Immediately pull the next waiting product off the queue.
            if self._awaiting_products_fifo:
                next_product = self._awaiting_products_fifo.pop(0)
                self._start_processing(next_product, current_time)

            return finished

        return None

    def reset_state(self) -> None:
        """Clear all in-flight state without changing structure (soft reset).

        Called by Process.reset_state() on a soft reset. The task name and
        processing_time are preserved; only the queued products and current
        product are discarded.
        """
        self._awaiting_products_fifo.clear()
        self._current_product = None
        self._remaining_time  = 0

    # ── Private helpers ───────────────────────────────────────────────────────

    def _start_processing(self, product: "Product", current_time: int) -> None:
        """
        Begin processing a product.

        Computes how long the product waited in the queue, records that wait
        on the product object (so ReportCenter can read it from the event),
        then fires TASK_WAIT_RECORDED (only when wait > 0) and TASK_STARTED.

        Parameters
        ----------
        product : Product
            The product that is about to start being processed.
        current_time : int
            Current simulation clock cycle.
        """
        # Queue wait = time now minus the cycle the product arrived at this task.
        wait_time = current_time - product.current_task_arrival_time
        product.record_task_wait(wait_time)

        self._current_product = product
        self._remaining_time  = self.processing_time

        if wait_time > 0:
            # Only emit when there was actual queueing — eliminates noise for
            # products that went straight to an idle machine.
            self._event_dispatcher.notify(SimulationEvent(
                event_type=SimulationEventType.TASK_WAIT_RECORDED,
                time=current_time,
                product=product,
                task_name=self.name,
                process_name=self.process_name,   # set by Process.add_task()
            ))

        self._event_dispatcher.notify(SimulationEvent(
            event_type=SimulationEventType.TASK_STARTED,
            time=current_time,
            product=product,
            task_name=self.name,
        ))

    def __repr__(self) -> str:
        return f"Task(name={self.name}, proc_time={self.processing_time})"
