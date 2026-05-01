from enum import Enum, auto


class SimulationEventType(Enum):
    TASK_STARTED        = auto()
    TASK_FINISHED       = auto()
    TASK_WAIT_RECORDED  = auto()
    PROCESS_STARTED     = auto()
    PROCESS_FINISHED    = auto()
    PRODUCT_CREATED     = auto()
    PRODUCT_COMPLETED   = auto()
    SIMULATION_STARTED  = auto()
    SIMULATION_PAUSED   = auto()
    SIMULATION_RESET    = auto()
    SIMULATION_FINISHED = auto()