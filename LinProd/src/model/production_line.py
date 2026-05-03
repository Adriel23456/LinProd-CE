"""
production_line.py
------------------
Defines the ProductionLine model — the top-level container for the full pipeline.

ProductionLine owns the ordered list of Processes and coordinates the two-pass
advance() cycle at the line level (mirrors the same pattern used in Process):

  Pass 1 — advance all processes (each internally does its own two-pass advance)
  Pass 2 — route products that exited a process to the next process, or mark
            them as completed if they exited the last process

add_product() injects products into the first process and fires PRODUCT_CREATED.
When a product exits the last process, PRODUCT_COMPLETED is fired and the product
is marked with its completion time.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .product import Product
    from .event_dispatcher import EventDispatcher

from .process import Process
from .simulation_event import SimulationEvent
from .simulation_event_type import SimulationEventType


class ProductionLine:
    """
    The full ordered pipeline of Processes.

    Encapsulates the process list and routing logic. Callers interact through
    factory/mutation methods rather than direct list manipulation.
    _rebuild_links() keeps previous_process pointers consistent after every
    structural change (add / remove / reorder / link).

    Relationships:
        - Owned by MainController; shared with SimulationEngine and SetupController.
        - Each Process inside is created via create_process() or imported from JSON.
        - SimulationEngine calls advance() once per clock tick.
    """

    def __init__(self, dispatcher: "EventDispatcher") -> None:
        """
        Parameters
        ----------
        dispatcher : EventDispatcher
            Shared event bus; forwarded to each Process (and transitively to Tasks).
        """
        self._processes:        list[Process]      = []
        self._first_process:    Process | None      = None
        self._last_process:     Process | None      = None
        self._event_dispatcher: "EventDispatcher"  = dispatcher

    # ── Public read-only views ────────────────────────────────────────────────

    @property
    def processes(self) -> list[Process]:
        """Ordered list of all Processes on the line."""
        return self._processes

    @property
    def first_process(self) -> Process | None:
        """The entry process; products are injected here via add_product()."""
        return self._first_process

    @first_process.setter
    def first_process(self, process: Process | None) -> None:
        self._first_process = process

    @property
    def last_process(self) -> Process | None:
        """The exit process; products that leave here are marked PRODUCT_COMPLETED."""
        return self._last_process

    @last_process.setter
    def last_process(self, process: Process | None) -> None:
        self._last_process = process

    @property
    def event_dispatcher(self) -> "EventDispatcher":
        """Shared event bus — exposed so LineLoader can subscribe new observers."""
        return self._event_dispatcher

    # ── Process management ────────────────────────────────────────────────────

    def create_process(self, name: str) -> Process:
        """
        Factory: create, register, and return a new Process.

        Parameters
        ----------
        name : str
            Human-readable process name shown in the UI.

        Returns
        -------
        Process
            The newly created and registered Process.
        """
        proc = Process(name, self._event_dispatcher)
        self.add_process(proc)
        return proc

    def add_process(self, process: Process) -> None:
        """Append a process to the end of the line and rebuild previous_process links."""
        self._processes.append(process)
        self._rebuild_links()

    def remove_process(self, name: str) -> None:
        """Remove the process with the given name and rebuild links."""
        self._processes = [p for p in self._processes if p.name != name]
        self._rebuild_links()

    def reorder_process(self, proc_name: str, new_index: int) -> None:
        """
        Move a process to a new position in the ordered list.

        Parameters
        ----------
        proc_name : str
            Name of the process to move.
        new_index : int
            Target position (0-based).
        """
        proc = self._find_process(proc_name)
        if proc:
            self._processes.remove(proc)
            self._processes.insert(new_index, proc)
            self._rebuild_links()

    def link_processes(self, src: Process, dst: Process) -> None:
        """
        Move dst to immediately follow src in the ordered list.

        Used by SetupController when the user explicitly links two processes.
        """
        if src not in self._processes or dst not in self._processes:
            return
        self._processes.remove(dst)
        src_idx = self._processes.index(src)
        self._processes.insert(src_idx + 1, dst)
        self._rebuild_links()

    def set_first_process(self, name: str) -> None:
        """Set the first process by name (convenience wrapper)."""
        self._first_process = self._find_process(name)

    def set_last_process(self, name: str) -> None:
        """Set the last process by name (convenience wrapper)."""
        self._last_process = self._find_process(name)

    # ── Simulation interface ──────────────────────────────────────────────────

    def add_product(self, product: "Product", current_time: int) -> None:
        """
        Inject a product into the first process.

        Fires PRODUCT_CREATED before handing the product to first_process.
        Assumes first_process is set; will raise AttributeError if not.

        Parameters
        ----------
        product : Product
            The product to inject.
        current_time : int
            Current simulation clock cycle.
        """
        self._event_dispatcher.notify(SimulationEvent(
            event_type=SimulationEventType.PRODUCT_CREATED,
            time=current_time,
            product=product,
        ))
        self._first_process.receive_product(product, current_time)

    def move_prod_to_next_process(
        self, product: "Product", current_process: Process, current_time: int
    ) -> None:
        """
        Route a product from current_process to the immediately following process.

        Called during the second pass of advance() so routing happens after all
        processes have ticked (prevents double-advancement in one cycle).

        Parameters
        ----------
        product : Product
            The product that just exited current_process.
        current_process : Process
            The process the product just left.
        current_time : int
            Current simulation clock cycle.
        """
        idx = self._processes.index(current_process)
        if idx + 1 < len(self._processes):
            self._processes[idx + 1].receive_product(product, current_time)

    def advance(self, current_time: int) -> list["Product"]:
        """
        Two-pass advance at the line level.

        Pass 1: advance() every process (which internally also does two passes).
        Pass 2: for each product that exited a process this tick, either route
                it to the next process or — if it exited the last process — mark
                it completed and fire PRODUCT_COMPLETED.

        Parameters
        ----------
        current_time : int
            Current simulation clock cycle.

        Returns
        -------
        list[Product]
            Products that completed the entire line this tick.
        """
        # Pass 1 — tick all processes.
        finished_pairs: list[tuple[Process, list["Product"]]] = []
        for process in self._processes:
            exited = process.advance(current_time)
            if exited:
                finished_pairs.append((process, exited))

        # Pass 2 — route or complete each product that exited a process.
        fully_completed: list["Product"] = []
        for process, products in finished_pairs:
            for product in products:
                if process is self._last_process:
                    # Product has cleared the entire line — record completion.
                    product.mark_completed(current_time)
                    self._event_dispatcher.notify(SimulationEvent(
                        event_type=SimulationEventType.PRODUCT_COMPLETED,
                        time=current_time,
                        product=product,
                    ))
                    fully_completed.append(product)
                else:
                    # More processes remain — hand off to the next one.
                    self.move_prod_to_next_process(product, process, current_time)

        return fully_completed

    # ── Private helpers ───────────────────────────────────────────────────────

    def _find_process(self, name: str) -> Process | None:
        """Return the process with the given name, or None if not found."""
        return next((p for p in self._processes if p.name == name), None)

    def clear_all(self) -> None:
        """Remove all processes and reset first/last markers (used by JSON import)."""
        self._processes.clear()
        self._first_process = None
        self._last_process  = None

    def import_from(self, source: "ProductionLine") -> None:
        """
        Replace all content from another ProductionLine.

        Used by SetupController.load_from_json() to overwrite the live line
        with one reconstructed from a JSON file without breaking observer
        subscriptions on the existing dispatcher.
        """
        self.clear_all()
        self._processes     = list(source.processes)
        self._first_process = source.first_process
        self._last_process  = source.last_process
        self._rebuild_links()

    def _rebuild_links(self) -> None:
        """
        Rebuild previous_process pointers after any structural change.

        Ensures Process.previous_process is always consistent with the current
        order in self._processes. Called automatically by all mutation methods.
        """
        for i, proc in enumerate(self._processes):
            proc.previous_process = self._processes[i - 1] if i > 0 else None
