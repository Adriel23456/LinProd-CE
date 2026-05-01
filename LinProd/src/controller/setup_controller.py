from __future__ import annotations
from src.model.production_line import ProductionLine
from src.model.process import Process
from src.model.task import Task
from src.view.setup_view import SetupView


class SetupController:
    def __init__(self, production_line: ProductionLine, view: SetupView) -> None:
        self.production_line = production_line
        self.view            = view

    def on_add_process(self, name: str) -> None:
        proc = Process(name, self.production_line.event_dispatcher)
        self.production_line.add_process(proc)
        self.view.render_process_form()

    def on_remove_process(self, name: str) -> None:
        self.production_line.processes = [
            p for p in self.production_line.processes if p.name != name
        ]
        self.view.render_process_form()

    def on_add_task(self, proc_name: str, task_name: str, proc_time: int) -> None:
        proc = self._get_process(proc_name)
        if proc:
            proc.add_task(Task(task_name, proc_time, self.production_line.event_dispatcher))
            self.view.render_task_list(self.production_line.processes)

    def on_remove_task(self, proc_name: str, task_name: str) -> None:
        proc = self._get_process(proc_name)
        if proc:
            proc.tasks = [t for t in proc.tasks if t.name != task_name]
            self.view.render_task_list(self.production_line.processes)

    def on_set_first_process(self, name: str) -> None:
        self.production_line.first_process = self._get_process(name)

    def on_set_last_process(self, name: str) -> None:
        self.production_line.last_process = self._get_process(name)

    def on_reorder_task(self, proc_name: str, task_name: str, new_index: int) -> None:
        proc = self._get_process(proc_name)
        if proc:
            task = next((t for t in proc.tasks if t.name == task_name), None)
            if task:
                proc.tasks.remove(task)
                proc.tasks.insert(new_index, task)

    def on_reorder_process(self, proc_name: str, new_index: int) -> None:
        proc = self._get_process(proc_name)
        if proc:
            self.production_line.processes.remove(proc)
            self.production_line.processes.insert(new_index, proc)

    def on_confirm_setup(self) -> bool:
        pl = self.production_line
        if not pl.processes:
            self.view.show_validation_error("Add at least one process.")
            return False
        if pl.first_process is None or pl.last_process is None:
            self.view.show_validation_error("Set first and last processes.")
            return False
        if any(len(p.tasks) == 0 for p in pl.processes):
            self.view.show_validation_error("Every process must have at least one task.")
            return False
        return True

    def _get_process(self, name: str) -> Process | None:
        return next((p for p in self.production_line.processes if p.name == name), None)