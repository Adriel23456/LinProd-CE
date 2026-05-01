from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .observer import Observer
    from .simulation_event import SimulationEvent


class EventDispatcher:
    def __init__(self) -> None:
        self._observers: list["Observer"] = []

    def subscribe(self, observer: "Observer") -> None:
        if observer not in self._observers:
            self._observers.append(observer)

    def unsubscribe(self, observer: "Observer") -> None:
        self._observers.remove(observer)

    def notify(self, event: "SimulationEvent") -> None:
        for observer in self._observers:
            observer.update(event)