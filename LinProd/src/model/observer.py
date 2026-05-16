"""
observer.py
-----------
Defines the Observer abstract base class that all event consumers must implement.

Part of the Observer design pattern used throughout LinProd:
  EventDispatcher (Subject) → notifies → Observer implementors
    ├── SimulationView  (GUI updates)
    ├── ReportCenter    (statistics accumulation)
    └── (any future observer)

All observers receive a SimulationEvent and must handle it in update().
"""

from abc import ABC, abstractmethod
from .simulation_event import SimulationEvent


class Observer(ABC):
    """
    Abstract base class for all objects that subscribe to simulation events.

    Implementors receive a SimulationEvent each time the EventDispatcher
    fires notify(). The update() method MUST be thread-safe if the observer
    interacts with Tkinter widgets, because the simulation runs on a background
    thread — use widget.after(0, callback) to marshal calls to the main thread.
    """

    @abstractmethod
    def update(self, event: SimulationEvent) -> None:
        """
        Called by EventDispatcher.notify() when a simulation event occurs.

        Parameters
        ----------
        event : SimulationEvent
            Immutable value object describing what happened and when.
            See SimulationEventType for the full list of possible event types.
        """
        pass
