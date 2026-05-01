from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .product import Product
    from .simulation_event_type import SimulationEventType


@dataclass
class SimulationEvent:
    event_type:   "SimulationEventType"
    time:         int
    product:      "Product | None"  = field(default=None)
    task_name:    str | None        = field(default=None)
    process_name: str | None        = field(default=None)