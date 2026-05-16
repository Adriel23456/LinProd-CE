"""
report.py
---------
Defines the Report immutable value object that ReportCenter produces once a
simulation run ends (or at any point via SimulationEngine.generate_report()).

Report is a frozen dataclass — all fields are set at construction time and
cannot be mutated afterwards. This makes it safe to hand Report instances to
the GUI thread or pass them around without defensive copying.

Consumers:
    - ReportView reads every field to render on-screen statistics and PDF export.
    - SimulationEngine delegates generate_report() to ReportCenter, which returns
      one of these objects.

Field grouping (cosmetic only — frozen dataclasses require positional order):
    Timing   → when products finished, makespan, averages, throughput
    Products → count of fully completed products
    Bottleneck & waits → which process/task caused the most congestion
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Report:
    """
    Immutable statistical summary of one complete simulation run.

    Produced exclusively by ReportCenter.generate_report() and consumed by
    ReportView for on-screen display and PDF export. All time values are
    expressed in simulation clock cycles (ticks).

    Relationships:
        - Created by: ReportCenter.generate_report()
        - Consumed by: ReportView.render_metrics(), ReportView.export_pdf()
        - Returned through: SimulationEngine.generate_report()
    """

    # ── Timing ────────────────────────────────────────────────────────────────
    first_product_completed_time:       int
    """Clock cycle when the first product exited the last process."""

    last_product_completed_time:        int
    """Clock cycle when the final product exited the last process (= makespan)."""

    average_execution_time:             float
    """Mean completion time across all finished products (sum / count)."""

    total_processing_time:              int
    """Simulation makespan — the last completion cycle, i.e. last_product_completed_time."""

    # ── Products ──────────────────────────────────────────────────────────────
    completed_products:                 int
    """Number of products that successfully exited the entire production line."""

    throughput_rate:                    float
    """Products completed per simulation cycle (completed_products / makespan)."""

    # ── Bottleneck & waits ────────────────────────────────────────────────────
    bottleneck:                         str
    """Name of the process with the highest cumulative task-processing load."""

    average_waiting_time_to_start_task: float
    """Mean cycles a product spent queuing at a busy task before processing began."""

    max_waiting_time_task:              int
    """Longest single queue wait (in cycles) observed at any task across all products."""

    max_waiting_task_name:              str
    """Name of the task where the longest queue wait occurred."""

    max_waiting_task_process:           str
    """Name of the process that contains max_waiting_task_name."""

    max_waiting_time_process:           int
    """Longest single product-in-process duration (arrival → exit, in cycles)."""
