from __future__ import annotations
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .event_dispatcher import EventDispatcher

from .production_line import ProductionLine


class LineLoader:
    """
    Serializes / deserializes a ProductionLine to / from JSON.

    Uses ProductionLine.create_process() and Process.create_task() factory
    methods so the loader never touches EventDispatcher directly (DIP fix).

    JSON schema:
        { "production_line": { "processes": [
            { "number": int, "name": str, "tasks": [
                { "number": int, "name": str, "processing_time": int }
            ]}
        ]}}
    """

    @staticmethod
    def load(path: str | Path, dispatcher: "EventDispatcher") -> ProductionLine:
        config = LineLoader._read(path)
        line   = ProductionLine(dispatcher)

        raw_processes = sorted(config["production_line"]["processes"], key=lambda p: p["number"])
        for raw_proc in raw_processes:
            proc      = line.create_process(raw_proc["name"])
            raw_tasks = sorted(raw_proc["tasks"], key=lambda t: t["number"])
            for raw_task in raw_tasks:
                proc.create_task(raw_task["name"], raw_task["processing_time"])

        line.first_process = line.processes[0]
        line.last_process  = line.processes[-1]
        return line

    @staticmethod
    def save(path: str | Path, line: ProductionLine) -> None:
        processes_data = []
        for i, proc in enumerate(line.processes, 1):
            tasks_data = [
                {"number": j, "name": t.name, "processing_time": t.processing_time}
                for j, t in enumerate(proc.tasks, 1)
            ]
            processes_data.append({"number": i, "name": proc.name, "tasks": tasks_data})

        data = {"production_line": {"processes": processes_data}}
        with open(Path(path), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _read(path: str | Path) -> dict:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"[LineLoader] Config not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
