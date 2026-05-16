from __future__ import annotations
from typing import TYPE_CHECKING

from src.model.production_line import ProductionLine
from src.model.process import Process
from src.model.line_loader import LineLoader

if TYPE_CHECKING:
    from src.view.setup_view import SetupView


class SetupController:
    """
    Handles all user actions during the production-line configuration phase.

    Uses ProductionLine/Process factory methods so the EventDispatcher never
    leaks into this layer (V-SOLID-DIP-02 fix).
    """

    def __init__(self, production_line: ProductionLine, view: "SetupView") -> None:
        self._production_line: ProductionLine = production_line
        self._view:            "SetupView"    = view

    # ── Process actions ───────────────────────────────────────────────────────

    def on_add_process(self, name: str) -> None:
        self._production_line.create_process(name)
        self._view.render_process_form()

    def on_remove_process(self, name: str) -> None:
        self._production_line.remove_process(name)
        self._view.render_process_form()

    def on_link_processes(self, src: str, dst: str) -> None:
        src_proc = self._get_process(src)
        dst_proc = self._get_process(dst)
        if src_proc and dst_proc and src_proc is not dst_proc:
            self._production_line.link_processes(src_proc, dst_proc)
            self._view.render_line_preview(self._production_line.processes)

    def on_set_first_process(self, name: str) -> None:
        self._production_line.first_process = self._get_process(name)
        self._view.render_process_form()

    def on_set_last_process(self, name: str) -> None:
        self._production_line.last_process = self._get_process(name)
        self._view.render_process_form()

    def on_reorder_process(self, proc_name: str, new_index: int) -> None:
        self._production_line.reorder_process(proc_name, new_index)
        self._view.render_process_form()

    # ── Task actions ──────────────────────────────────────────────────────────

    def on_add_task(self, proc_name: str, task_name: str, proc_time: int) -> None:
        proc = self._get_process(proc_name)
        if proc:
            proc.create_task(task_name, proc_time)
            self._view.render_task_list(self._production_line.processes)
            self._view.render_process_form()

    def on_remove_task(self, proc_name: str, task_name: str) -> None:
        proc = self._get_process(proc_name)
        if proc:
            proc.remove_task(task_name)
            self._view.render_task_list(self._production_line.processes)
            self._view.render_process_form()

    def on_reorder_task(self, proc_name: str, task_name: str, new_index: int) -> None:
        proc = self._get_process(proc_name)
        if proc:
            proc.reorder_task(task_name, new_index)

    # ── Validation ────────────────────────────────────────────────────────────

    def on_confirm_setup(self) -> bool:
        pl = self._production_line
        if not pl.processes:
            self._view.show_validation_error("Add at least one process.")
            return False
        if any(len(p.tasks) == 0 for p in pl.processes):
            self._view.show_validation_error("Every process must have at least one task.")
            return False
        # Auto-assign first and last based on list order
        pl.first_process = pl.processes[0]
        pl.last_process  = pl.processes[-1]
        return True

    # ── JSON persistence ──────────────────────────────────────────────────────

    def load_from_json(self, path: str) -> None:
        """Replace the entire line with the contents of a JSON config file."""
        loaded = LineLoader.load(path, self._production_line.event_dispatcher)
        self._production_line.import_from(loaded)
        self._view.render_process_form()
        self._view.render_line_preview(self._production_line.processes)

    def save_to_json(self, path: str) -> None:
        LineLoader.save(path, self._production_line)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_process(self, name: str) -> Process | None:
        return next((p for p in self._production_line.processes if p.name == name), None)
