"""
simulation_event_type.py
------------------------
Enumerates every discrete event type that the simulation can publish.

These values are used as the event_type field of SimulationEvent objects.
Observers switch on these values inside their update() methods to decide
how to react.

Lifecycle sequence (typical run):
    SIMULATION_STARTED
    PRODUCT_CREATED           (one per product added to the line)
    PROCESS_STARTED           (product enters a process)
    TASK_STARTED              (product begins being processed by a task)
    TASK_WAIT_RECORDED        (product had to queue before a task started)
    TASK_FINISHED             (task processing complete)
    PROCESS_FINISHED          (product exits the last task of a process)
    PRODUCT_COMPLETED         (product exits the last process on the line)
    SIMULATION_PAUSED         (user or auto-stop paused the engine)
    SIMULATION_FINISHED       (all expected products completed)
    SIMULATION_RESET          (soft reset — state cleared, structure kept)
"""

from enum import Enum, auto


class SimulationEventType(Enum):
    """All possible simulation event types, in approximate lifecycle order."""

    # Task-level events
    TASK_STARTED        = auto()   # a product started being processed by a task
    TASK_FINISHED       = auto()   # a task finished processing a product
    TASK_WAIT_RECORDED  = auto()   # a product queued at a busy task (wait > 0)

    # Process-level events
    PROCESS_STARTED     = auto()   # a product entered a process (its first task)
    PROCESS_FINISHED    = auto()   # a product exited a process (its last task)

    # Product lifecycle events
    PRODUCT_CREATED     = auto()   # a product was injected into the line
    PRODUCT_COMPLETED   = auto()   # a product cleared the last process on the line

    # Engine lifecycle events
    SIMULATION_STARTED  = auto()   # engine started (or resumed) its background loop
    SIMULATION_PAUSED   = auto()   # engine was paused (user action or auto-stop)
    SIMULATION_RESET    = auto()   # soft reset — all product state cleared
    SIMULATION_FINISHED = auto()   # all expected products have completed
