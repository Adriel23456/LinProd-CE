from dataclasses import dataclass


@dataclass(frozen=True)
class Report:
    first_product_completed_time:      int
    last_product_completed_time:       int
    average_execution_time:            float
    bottleneck:                        str
    average_waiting_time_to_start_task:float
    max_waiting_time_task:             int
    max_processing_time_process:       int
    total_processing_time:             int
    completed_products:                int