"""
simulation_event.py
-------------------
Defines the SimulationEvent value object that carries all information about
a discrete occurrence in the simulation.

SimulationEvent is immutable (frozen dataclass) so that observers cannot
accidentally mutate the event while processing it. Optional fields (product,
task_name, process_name) are None when not applicable to the event type.

Usage pattern:
    dispatcher.notify(SimulationEvent(
        event_type=SimulationEventType.TASK_STARTED,
        time=engine.current_time,
        product=the_product,
        task_name="Mix",
        process_name="Baking",
    ))
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .product import Product
    from .simulation_event_type import SimulationEventType


@dataclass(frozen=True)
class SimulationEvent:
    """
    Immutable value object representing a discrete simulation occurrence.

    Attributes
    ----------
    event_type : SimulationEventType
        Categorises the event; observers switch on this.
    time : int
        The simulation clock cycle at which the event occurred.
    product : Product | None
        The product involved, or None for engine-level events
        (SIMULATION_STARTED, SIMULATION_PAUSED, etc.).
    task_name : str | None
        Name of the relevant Task, or None when not applicable.
    process_name : str | None
        Name of the relevant Process, or None when not applicable.
        For TASK_WAIT_RECORDED events, process_name matches the process
        that contains the waiting task (set via Task.process_name).
    """

    event_type:   "SimulationEventType"
    time:         int
    product:      "Product | None"  = field(default=None)
    task_name:    str | None        = field(default=None)
    process_name: str | None        = field(default=None)
