from dataclasses import dataclass, field


@dataclass(frozen=True)
class Report:
    """Immutable summary produced by ReportCenter at the end of a simulation run."""
    # ── Timing ────────────────────────────────────────────────────────────────
    first_product_completed_time:       int
    last_product_completed_time:        int
    average_execution_time:             float
    total_processing_time:              int   # simulation makespan (last completion cycle)

    # ── Products ──────────────────────────────────────────────────────────────
    completed_products:                 int
    throughput_rate:                    float  # completed / max(1, makespan)

    # ── Bottleneck & waits ────────────────────────────────────────────────────
    bottleneck:                         str    # process with highest total load
    average_waiting_time_to_start_task: float
    max_waiting_time_task:              int    # longest single queue wait (cycles)
    max_waiting_task_name:              str    # which task caused it
    max_waiting_task_process:           str    # which process that task belongs to
    max_waiting_time_process:           int    # longest single product-in-process time
