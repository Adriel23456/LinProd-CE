"""
event_dispatcher.py
-------------------
Implements the Subject role in LinProd's Observer pattern.

A single EventDispatcher instance is created by MainController and shared
with every model object that needs to publish events (ProductionLine, Process,
Task, SimulationEngine). Observers subscribe once at construction time and
receive every event for the lifetime of the simulation session.

Thread safety note: notify() is called from the simulation background thread
(SimulationEngine._loop). Observers that touch Tkinter widgets must marshal
their updates to the main thread via widget.after(0, ...).
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .observer import Observer
    from .simulation_event import SimulationEvent


class EventDispatcher:
    """
    Central publish-subscribe event bus for the simulation.

    Maintains an ordered list of Observer objects and broadcasts every
    SimulationEvent to all of them in subscription order.

    Relationships:
        - Created once by MainController; injected into all model objects.
        - SimulationEngine, Process, Task, ProductionLine call notify().
        - SimulationView and ReportCenter implement Observer and subscribe().
    """

    def __init__(self) -> None:
        # Ordered list of active observers; order matters for deterministic testing.
        self._observers: list["Observer"] = []

    def subscribe(self, observer: "Observer") -> None:
        """
        Register an observer to receive future events.

        Duplicate registration is silently ignored, so callers do not need
        to track whether they have already subscribed.

        Parameters
        ----------
        observer : Observer
            The object to start receiving SimulationEvent notifications.
        """
        if observer not in self._observers:
            self._observers.append(observer)

    def unsubscribe(self, observer: "Observer") -> None:
        """
        Remove an observer so it no longer receives events.

        This is important after a soft reset: SimulationEngine replaces its
        ReportCenter and must unsubscribe the old instance before creating
        a new one, otherwise statistics will be double-counted.

        Parameters
        ----------
        observer : Observer
            The object to stop receiving notifications. Must be subscribed.

        Raises
        ------
        ValueError
            If the observer is not currently subscribed (list.remove behaviour).
        """
        self._observers.remove(observer)

    def notify(self, event: "SimulationEvent") -> None:
        """
        Broadcast event to all subscribed observers in subscription order.

        Parameters
        ----------
        event : SimulationEvent
            Immutable value object describing what just happened in the simulation.
        """
        for observer in self._observers:
            observer.update(event)
