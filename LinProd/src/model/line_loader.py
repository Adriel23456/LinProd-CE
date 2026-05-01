from __future__ import annotations
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .event_dispatcher import EventDispatcher

from .production_line import ProductionLine
from .process import Process
from .task import Task


class LineLoader:
    """Builds a ProductionLine from a JSON config file."""

    @staticmethod
    def load(path: str | Path, dispatcher: "EventDispatcher") -> ProductionLine:
        config = LineLoader._read(path)
        line   = ProductionLine(dispatcher)

        raw_processes = config["production_line"]["processes"]

        # Sort by number to guarantee insertion order regardless of JSON order
        raw_processes = sorted(raw_processes, key=lambda p: p["number"])

        for raw_proc in raw_processes:
            proc = Process(raw_proc["name"], dispatcher)

            raw_tasks = sorted(raw_proc["tasks"], key=lambda t: t["number"])
            for raw_task in raw_tasks:
                task = Task(raw_task["name"], raw_task["processing_time"], dispatcher)
                proc.add_task(task)

            line.add_process(proc)

        # First and last are determined by insertion order
        line.first_process = line.processes[0]
        line.last_process  = line.processes[-1]

        LineLoader._print_loaded(line)
        return line

    @staticmethod
    def _read(path: str | Path) -> dict:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"[LineLoader] Config not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _print_loaded(line: ProductionLine) -> None:
        print("\n[LineLoader] Production line loaded successfully")
        print(f"  Processes : {len(line.processes)}")
        for proc in line.processes:
            print(f"  └─ {proc.name}  ({len(proc.tasks)} tasks)")
            for task in proc.tasks:
                print(f"       └─ {task.name}  [proc_time={task.processing_time}]")
        print(f"  First : {line.first_process.name}")
        print(f"  Last  : {line.last_process.name}\n")