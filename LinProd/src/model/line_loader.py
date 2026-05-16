"""
line_loader.py
--------------
Handles JSON serialization and deserialization of a ProductionLine configuration.

LineLoader is a pure static-method utility class (no instance state). It bridges
the gap between the on-disk JSON configuration format and the in-memory object
graph (ProductionLine → Process → Task).

Key design decisions:
  - load() uses the factory methods ProductionLine.create_process() and
    Process.create_task() rather than constructing objects directly. This ensures
    that every object is wired to the shared EventDispatcher and that
    Process.add_task() stamps each Task with its parent process name.
  - Processes and tasks are sorted by their "number" field before construction,
    guaranteeing a deterministic pipeline order regardless of JSON key order.
  - first_process and last_process are set to the first and last elements of the
    sorted process list — the JSON schema has no explicit "first"/"last" markers.

JSON schema (assets/production_line.json):
    {
      "production_line": {
        "processes": [
          {
            "number": <int>,   // 1-based ordering index
            "name":   <str>,
            "tasks":  [
              { "number": <int>, "name": <str>, "processing_time": <int> }
            ]
          }
        ]
      }
    }

Callers:
    - SetupController.load_from_json() uses load() then imports via
      ProductionLine.import_from() to update the live line in-place.
    - SetupController.save_to_json() delegates directly to save().
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .event_dispatcher import EventDispatcher

from .production_line import ProductionLine


class LineLoader:
    """
    Static utility for reading and writing ProductionLine configurations to JSON.

    All methods are static — LineLoader is never instantiated. It acts purely
    as a namespace for the two public operations (load / save) and one private
    helper (_read).

    Relationships:
        - Called by: SetupController (load_from_json, save_to_json)
        - Produces: ProductionLine (load) or writes file (save)
        - Uses factory methods on: ProductionLine, Process (never constructs directly)
    """

    @staticmethod
    def load(path: str | Path, dispatcher: "EventDispatcher") -> ProductionLine:
        """
        Deserialize a JSON config file into a fully wired ProductionLine object graph.

        Processes are sorted by their "number" field before construction to ensure
        deterministic ordering. The first and last elements of the sorted list are
        set as first_process and last_process on the returned line.

        Parameters
        ----------
        path : str | Path
            Absolute or relative path to the JSON configuration file.
        dispatcher : EventDispatcher
            Shared event bus injected into the new ProductionLine (and transitively
            into every Process and Task created by it).

        Returns
        -------
        ProductionLine
            Fully constructed pipeline with all processes and tasks linked.

        Raises
        ------
        FileNotFoundError
            If the file at path does not exist (raised by _read()).
        KeyError / json.JSONDecodeError
            If the JSON structure does not match the expected schema.
        """
        config = LineLoader._read(path)
        line   = ProductionLine(dispatcher)

        # Sort by "number" so pipeline order matches the authored sequence.
        raw_processes = sorted(config["production_line"]["processes"], key=lambda p: p["number"])
        for raw_proc in raw_processes:
            proc      = line.create_process(raw_proc["name"])
            raw_tasks = sorted(raw_proc["tasks"], key=lambda t: t["number"])
            for raw_task in raw_tasks:
                proc.create_task(raw_task["name"], raw_task["processing_time"])

        # The JSON schema has no explicit first/last markers — use list position.
        line.first_process = line.processes[0]
        line.last_process  = line.processes[-1]
        return line

    @staticmethod
    def save(path: str | Path, line: ProductionLine) -> None:
        """
        Serialize a ProductionLine to a JSON configuration file.

        Processes and tasks are written in their current ordered-list sequence,
        with 1-based "number" fields assigned at serialization time.

        Parameters
        ----------
        path : str | Path
            Destination file path. The file is created or overwritten.
        line : ProductionLine
            The pipeline to serialize. Only name and processing_time are written;
            runtime state (queued products, current_product, etc.) is not persisted.
        """
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
        """
        Read and parse a JSON file, raising a descriptive error if not found.

        Parameters
        ----------
        path : str | Path
            Path to the JSON file.

        Returns
        -------
        dict
            Parsed JSON content as a Python dictionary.

        Raises
        ------
        FileNotFoundError
            If the file does not exist at the given path.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"[LineLoader] Config not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
