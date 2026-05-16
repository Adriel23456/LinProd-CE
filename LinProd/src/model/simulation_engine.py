"""
simulation_engine.py
--------------------
Owns and drives the discrete-event simulation clock.

SimulationEngine is the central coordinator for runtime simulation state. It
is responsible for:
  - Maintaining the monotonic clock (current_time, incremented each tick).
  - Running the background thread that calls tick() on a configurable interval.
  - Detecting when all expected products have completed and firing SIMULATION_FINISHED.
  - Performing soft resets (clear product state, keep line structure, replace ReportCenter).
  - Delegating report generation to ReportCenter (Dependency Inversion — V-SOLID-DIP-03).

Design notes:
  - Continuous mode: run() spawns a daemon thread that calls tick() in a loop.
  - Step mode:       step(n) advances n cycles synchronously on the calling thread.
  - The engine does NOT own the ProductionLine structure — it receives it from
    MainController and delegates all advance logic to ProductionLine.advance().

V-BUG-01 fix: reset() unsubscribes the old ReportCenter before replacing it.
  Without this, stale statistics from previous runs accumulate into new ones
  because the old observer remains registered on the shared EventDispatcher.

Thread safety:
  _loop() runs on a daemon thread. tick() and pause() both write _is_running.
  In CPython the GIL makes these individual bool writes effectively atomic.
  No explicit locks are used; the daemon thread exits cleanly when _is_running
  is set to False by pause() or auto-stop.
"""

from __future__ import annotations
import time
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .event_dispatcher import EventDispatcher

from .production_line import ProductionLine
from .product import Product
from .report_center import ReportCenter
from .report import Report
from .simulation_event import SimulationEvent
from .simulation_event_type import SimulationEventType


class SimulationEngine:
    """
    Central coordinator for simulation lifecycle and discrete time advancement.

    Owns the clock, a background simulation thread (continuous mode), and the
    ReportCenter statistics accumulator. External callers interact through the
    public lifecycle methods (run, pause, reset, step, tick) and the report
    delegation method (generate_report).

    Relationships:
        - Created by: MainController
        - Shares: EventDispatcher (injected; not owned)
        - Owns: ProductionLine (shared reference), ReportCenter (replaced on reset)
        - Subscribed observer: ReportCenter (subscribes itself in __init__)
        - Used by: SimulationController (calls run/pause/reset/step/tick)

    V-BUG-01 fix: reset() unsubscribes the old ReportCenter before replacing it,
    preventing statistics from bleeding across runs.
    """

    def __init__(self, production_line: ProductionLine, dispatcher: "EventDispatcher") -> None:
        """
        Parameters
        ----------
        production_line : ProductionLine
            The pipeline to advance each tick. Shared with SetupController and
            the broader application — SimulationEngine does not own its structure.
        dispatcher : EventDispatcher
            Shared event bus. ReportCenter is subscribed here at construction time.
        """
        self._current_time:        int                    = 0
        self._is_running:          bool                   = False
        self._production_line:     ProductionLine         = production_line
        self._report_center:       ReportCenter           = ReportCenter()
        self._simulation_speed:    int                    = 500   # ms between ticks
        self._event_dispatcher:    "EventDispatcher"      = dispatcher
        self._thread:              threading.Thread | None = None
        self._expected_products:   int                    = 0
        self._completed_products:  int                    = 0

        # Subscribe the fresh ReportCenter so it starts recording immediately.
        dispatcher.subscribe(self._report_center)

    # ── Public read-only state ────────────────────────────────────────────────

    @property
    def current_time(self) -> int:
        """Current simulation clock cycle (incremented by tick())."""
        return self._current_time

    @property
    def is_running(self) -> bool:
        """True while the background loop is active; False when paused or stopped."""
        return self._is_running

    @property
    def production_line(self) -> ProductionLine:
        """The production line being simulated (read-only reference)."""
        return self._production_line

    @property
    def simulation_speed(self) -> int:
        """Milliseconds between consecutive ticks in continuous mode."""
        return self._simulation_speed

    # ── Setup ─────────────────────────────────────────────────────────────────

    def set_expected_products(self, n: int) -> None:
        """
        Configure the engine to auto-stop once n products have completed.

        Also resets the internal completed-products counter so previous runs
        do not count toward the new target.

        Parameters
        ----------
        n : int
            Number of products that must exit the last process before
            SIMULATION_FINISHED is fired and the loop halts.
        """
        self._expected_products  = n
        self._completed_products = 0

    # ── Simulation control ────────────────────────────────────────────────────

    def tick(self) -> list[Product]:
        """
        Advance the simulation by exactly one clock cycle.

        Increments current_time, delegates the two-pass advance to
        ProductionLine, and tracks how many products have completed. If the
        expected-products target is reached this cycle, sets _is_running = False
        and fires SIMULATION_FINISHED before returning.

        Returns
        -------
        list[Product]
            Products that completed the entire line this cycle (may be empty).
        """
        self._current_time += 1
        completed = self._production_line.advance(self._current_time)

        if self._expected_products > 0:
            self._completed_products += len(completed)
            if self._completed_products >= self._expected_products:
                self._is_running = False
                self._event_dispatcher.notify(SimulationEvent(
                    event_type=SimulationEventType.SIMULATION_FINISHED,
                    time=self._current_time,
                ))

        return completed

    def step(self, n: int = 1) -> list[Product]:
        """
        Advance exactly n clock cycles synchronously (step mode).

        Called from the main thread when the user clicks the step button.
        Does NOT use the background thread — each cycle is executed inline.
        Stops early if the expected-products target is reached mid-sequence.

        Parameters
        ----------
        n : int
            Number of cycles to advance (default 1).

        Returns
        -------
        list[Product]
            All products that completed across all n cycles.
        """
        result: list[Product] = []
        for _ in range(n):
            result.extend(self.tick())
            # Stop early if all expected products have completed
            if (self._expected_products > 0
                    and self._completed_products >= self._expected_products):
                break
        return result

    def run(self) -> None:
        """
        Start continuous background-thread simulation.

        Sets _is_running = True, fires SIMULATION_STARTED, then spawns a
        daemon thread that calls tick() repeatedly until _is_running is cleared
        by pause(), auto-stop (SIMULATION_FINISHED), or reset().
        """
        self._is_running = True
        self._event_dispatcher.notify(SimulationEvent(
            event_type=SimulationEventType.SIMULATION_STARTED,
            time=self._current_time,
        ))
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def pause(self) -> None:
        """
        Halt the background simulation loop and fire SIMULATION_PAUSED.

        Sets _is_running = False so the daemon thread exits at its next
        loop iteration. The clock and all product state are preserved, allowing
        the simulation to resume from this point via run().
        """
        self._is_running = False
        self._event_dispatcher.notify(SimulationEvent(
            event_type=SimulationEventType.SIMULATION_PAUSED,
            time=self._current_time,
        ))

    def reset(self) -> None:
        """
        Soft reset: clear all in-flight product state while keeping the line structure.

        Sequence:
          1. Stop the background loop (_is_running = False).
          2. Reset clock and completion counter.
          3. Unsubscribe the old ReportCenter and subscribe a fresh one (V-BUG-01 fix).
          4. Call reset_state() on every Process (discards queued products).
          5. Fire SIMULATION_RESET so observers (e.g. SimulationView) can refresh.
        """
        self._is_running         = False
        self._current_time       = 0
        self._completed_products = 0

        # Unsubscribe old instance first to prevent double-counting (V-BUG-01 fix).
        self._event_dispatcher.unsubscribe(self._report_center)
        self._report_center = ReportCenter()
        self._event_dispatcher.subscribe(self._report_center)

        for proc in self._production_line.processes:
            proc.reset_state()

        self._event_dispatcher.notify(SimulationEvent(
            event_type=SimulationEventType.SIMULATION_RESET,
            time=0,
        ))

    def set_simulation_speed(self, speed: int) -> None:
        """
        Adjust the delay between ticks in continuous mode.

        The change takes effect on the next iteration of _loop() — there is no
        need to pause and restart. Already-sleeping calls will wake on the old
        interval once, then immediately use the new value.

        Parameters
        ----------
        speed : int
            Milliseconds to sleep between consecutive tick() calls.
        """
        self._simulation_speed = speed

    # ── Report delegation (V-SOLID-DIP-03) ───────────────────────────────────

    def generate_report(self) -> Report:
        """
        Delegate report generation to the internal ReportCenter.

        Callers never access ReportCenter directly — this is the only path
        to obtain statistics, enforcing the Dependency Inversion principle.

        Returns
        -------
        Report
            Immutable snapshot of all statistics accumulated so far.
        """
        return self._report_center.generate_report()

    # ── Private ──────────────────────────────────────────────────────────────

    def _loop(self) -> None:
        """
        Background thread body for continuous simulation mode.

        Calls tick() then sleeps for simulation_speed milliseconds in a loop.
        Exits when _is_running is set to False (by pause(), auto-stop, or reset()).
        The thread is a daemon so it is forcibly terminated if the main process exits.
        """
        while self._is_running:
            self.tick()
            time.sleep(self._simulation_speed / 1000)
