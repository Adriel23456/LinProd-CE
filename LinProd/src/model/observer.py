from abc import ABC, abstractmethod
from .simulation_event import SimulationEvent


class Observer(ABC):
    @abstractmethod
    def update(self, event: SimulationEvent) -> None:
        pass