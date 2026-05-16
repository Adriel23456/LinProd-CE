"""
setup_controller.py
-------------------
Handles all user interactions during the production-line configuration phase.

SetupController sits between SetupView (user input) and the model layer
(ProductionLine, Process). It translates UI events into model mutations and
then instructs the view to refresh the relevant section of the UI.

Design principles observed here:
  - Uses only ProductionLine and Process factory / mutation methods — it never
    constructs model objects directly, so the shared EventDispatcher never needs
    to leak into this controller layer (V-SOLID-DIP-02 fix).
  - SetupController does not import or reference MainController; phase-transition
    is communicated back through the on_confirm callback injected by MainController
    into SetupView at construction time.
  - After every model mutation the affected view sections are explicitly
    refreshed (render_process_form, render_task_list, render_line_preview). The
    view is intentionally kept stateless — the controller is the single source
    of truth about what to display.

Responsibilities:
  - Add / remove / reorder / link processes.
  - Add / remove / reorder tasks within a process.
  - Validate the configuration before allowing transition to simulation.
  - Load / save the configuration as a JSON file via LineLoader.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from src.model.production_line import ProductionLine
from src.model.process import Process
from src.model.line_loader import LineLoader

if TYPE_CHECKING:
    from src.view.setup_view import SetupView


class SetupController:
    """
    Mediates between SetupView UI events and the ProductionLine model.

    All public methods follow the naming convention on_<action> to signal
    that they are event handlers invoked by the view in response to user input.
    Each handler mutates the model then triggers the minimal set of view
    refreshes needed to reflect the change.

    Relationships:
        - Created by: MainController.start_setup()
        - Holds reference to: ProductionLine (shared with SimulationEngine)
        - Drives: SetupView (calls render_* and show_validation_error)
        - Delegates persistence to: LineLoader (static utility)
    """

    def __init__(self, production_line: ProductionLine, view: "SetupView") -> None:
        """
        Parameters
        ----------
        production_line : ProductionLine
            The shared pipeline object that this controller will mutate.
            The same instance is later used by SimulationEngine.
        view : SetupView
            The configuration UI. Receives render calls after each mutation.
        """
        self._production_line: ProductionLine = production_line
        self._view:            "SetupView"    = view

    # ── Process actions ───────────────────────────────────────────────────────

    def on_add_process(self, name: str) -> None:
        """
        Create a new process with the given name and refresh the process tiles.

        Parameters
        ----------
        name : str
            Human-readable name for the new process (e.g. "Mixing").
        """
        self._production_line.create_process(name)
        self._view.render_process_form()

    def on_remove_process(self, name: str) -> None:
        """
        Remove the process with the given name and refresh the process tiles.

        Parameters
        ----------
        name : str
            Name of the process to delete. No-op if not found.
        """
        self._production_line.remove_process(name)
        self._view.render_process_form()

    def on_link_processes(self, src: str, dst: str) -> None:
        """
        Move dst to immediately follow src in the pipeline and refresh the preview.

        Silently does nothing if either name is not found, or if src and dst
        are the same process.

        Parameters
        ----------
        src : str
            Name of the process that dst should follow.
        dst : str
            Name of the process to reposition.
        """
        src_proc = self._get_process(src)
        dst_proc = self._get_process(dst)
        if src_proc and dst_proc and src_proc is not dst_proc:
            self._production_line.link_processes(src_proc, dst_proc)
            self._view.render_line_preview(self._production_line.processes)

    def on_set_first_process(self, name: str) -> None:
        """
        Mark the named process as the pipeline entry point and refresh the tiles.

        Parameters
        ----------
        name : str
            Name of the process that will become first_process.
        """
        self._production_line.first_process = self._get_process(name)
        self._view.render_process_form()

    def on_set_last_process(self, name: str) -> None:
        """
        Mark the named process as the pipeline exit point and refresh the tiles.

        Parameters
        ----------
        name : str
            Name of the process that will become last_process.
        """
        self._production_line.last_process = self._get_process(name)
        self._view.render_process_form()

    def on_reorder_process(self, proc_name: str, new_index: int) -> None:
        """
        Move a process to a new position in the ordered list and refresh the tiles.

        Parameters
        ----------
        proc_name : str
            Name of the process to move.
        new_index : int
            Target 0-based position in the process list.
        """
        self._production_line.reorder_process(proc_name, new_index)
        self._view.render_process_form()

    # ── Task actions ──────────────────────────────────────────────────────────

    def on_add_task(self, proc_name: str, task_name: str, proc_time: int) -> None:
        """
        Add a new task to the specified process and refresh both the task list
        and the process tiles (so the task count on the tile updates).

        Parameters
        ----------
        proc_name : str
            Name of the parent process.
        task_name : str
            Human-readable name for the new task (e.g. "Mix").
        proc_time : int
            Number of simulation cycles required to process one product.
        """
        proc = self._get_process(proc_name)
        if proc:
            proc.create_task(task_name, proc_time)
            self._view.render_task_list(self._production_line.processes)
            self._view.render_process_form()

    def on_remove_task(self, proc_name: str, task_name: str) -> None:
        """
        Remove a task from the specified process and refresh both the task list
        and the process tiles (so the task count on the tile updates).

        Parameters
        ----------
        proc_name : str
            Name of the parent process.
        task_name : str
            Name of the task to remove. No-op if not found.
        """
        proc = self._get_process(proc_name)
        if proc:
            proc.remove_task(task_name)
            self._view.render_task_list(self._production_line.processes)
            self._view.render_process_form()

    def on_reorder_task(self, proc_name: str, task_name: str, new_index: int) -> None:
        """
        Move a task to a new position within its process.

        Parameters
        ----------
        proc_name : str
            Name of the parent process.
        task_name : str
            Name of the task to reorder.
        new_index : int
            Target 0-based position within the process's task list.
        """
        proc = self._get_process(proc_name)
        if proc:
            proc.reorder_task(task_name, new_index)

    # ── Validation ────────────────────────────────────────────────────────────

    def on_confirm_setup(self) -> bool:
        """
        Validate the current configuration before transitioning to simulation.

        Checks that:
          1. At least one process exists.
          2. Every process has at least one task.

        If validation passes, first_process and last_process are auto-assigned
        to the first and last elements of the ordered process list.

        Returns
        -------
        bool
            True if the configuration is valid and the transition may proceed;
            False if a validation error was found (view is notified via
            show_validation_error()).
        """
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
        """
        Replace the entire production line with the configuration read from a
        JSON file, then refresh the full setup UI.

        Uses LineLoader.load() to build a temporary ProductionLine, then calls
        ProductionLine.import_from() to overwrite the live line in-place. This
        preserves any existing EventDispatcher observer subscriptions.

        Parameters
        ----------
        path : str
            Absolute or relative path to the JSON configuration file.
        """
        loaded = LineLoader.load(path, self._production_line.event_dispatcher)
        self._production_line.import_from(loaded)
        self._view.render_process_form()
        self._view.render_line_preview(self._production_line.processes)

    def save_to_json(self, path: str) -> None:
        """
        Serialize the current production line configuration to a JSON file.

        Parameters
        ----------
        path : str
            Destination file path. The file is created or overwritten.
        """
        LineLoader.save(path, self._production_line)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_process(self, name: str) -> Process | None:
        """
        Look up a process by name in the current production line.

        Parameters
        ----------
        name : str
            Name of the process to find.

        Returns
        -------
        Process | None
            The matching Process, or None if no process with that name exists.
        """
        return next((p for p in self._production_line.processes if p.name == name), None)
