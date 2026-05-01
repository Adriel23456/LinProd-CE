from __future__ import annotations
import customtkinter as ctk
from src.model.observer import Observer
from src.model.simulation_event import SimulationEvent
from src.model.event_dispatcher import EventDispatcher


class SimulationView(ctk.CTkFrame, Observer):
    def __init__(self, parent, dispatcher: EventDispatcher) -> None:
        super().__init__(parent)
        dispatcher.subscribe(self)
        self._build()

    def _build(self) -> None:
        ctk.CTkLabel(self, text="Simulation", font=("Arial", 20, "bold")).pack(pady=16)
        self.canvas = ctk.CTkCanvas(self, bg="#1a1a2e")
        self.canvas.pack(fill="both", expand=True)

    def update(self, event: SimulationEvent) -> None:
        self.after(0, self._handle_event, event)   # thread-safe Tk update

    def _handle_event(self, event: SimulationEvent) -> None:
        # TODO: route event_type to appropriate render method
        pass

    def render_product_move(self, product) -> None:
        pass  # TODO

    def render_queue_depth(self, task) -> None:
        pass  # TODO

    def render_task_status(self, task) -> None:
        pass  # TODO

    def show_pause_snapshot(self) -> None:
        pass  # TODO