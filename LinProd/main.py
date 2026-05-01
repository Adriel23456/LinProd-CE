import threading
import customtkinter as ctk

from src.model.event_dispatcher import EventDispatcher
from src.model.observer import Observer
from src.model.simulation_event import SimulationEvent
from src.model.simulation_event_type import SimulationEventType
from src.model.simulation_engine import SimulationEngine
from src.model.product import Product
from src.model.line_loader import LineLoader
from src.controller.main_controller import MainController


# ── Debug observer ────────────────────────────────────────────────────────────

class DebugObserver(Observer):
    def update(self, event: SimulationEvent) -> None:
        prod_tag = f"  product=P{event.product.id}" if event.product      else ""
        task_tag = f"  task={event.task_name}"       if event.task_name    else ""
        proc_tag = f"  process={event.process_name}" if event.process_name else ""
        label    = "duration" if event.event_type == SimulationEventType.PROCESS_FINISHED else "t"
        print(
            f"[{label}={event.time:>3}]  {event.event_type.name:<26}"
            f"{prod_tag}{task_tag}{proc_tag}"
        )


# ── Terminal simulation (runs in background thread) ───────────────────────────

def run_terminal_simulation(dispatcher: EventDispatcher, root: ctk.CTk) -> None:
    N_PRODUCTS = 3
    MAX_CYCLES = 300
    COLORS     = ["red", "blue", "green", "orange", "purple", "cyan"]

    production_line = LineLoader.load("assets/production_line.json", dispatcher)
    engine          = SimulationEngine(production_line, dispatcher)

    dispatcher.subscribe(DebugObserver())

    print(f"[main] Injecting {N_PRODUCTS} product(s)\n")
    for i in range(N_PRODUCTS):
        p = Product(i + 1, COLORS[i % len(COLORS)], 1, 0)
        production_line.add_product(p, current_time=0)

    print("[main] Starting simulation\n" + "-" * 60)

    total_expected = N_PRODUCTS
    completed      = 0

    for _ in range(MAX_CYCLES):
        finished = engine.tick()
        completed += len(finished)
        if completed >= total_expected:
            break
    else:
        print(f"\n[main] WARNING: hit MAX_CYCLES ({MAX_CYCLES})")

    print("-" * 60)
    print(f"\n[main] Simulation finished at cycle {engine.current_time}\n")

    r = engine.report_center.generate_report()
    print("=" * 60)
    print("  SIMULATION REPORT")
    print("=" * 60)
    print(f"  Completed products          : {r.completed_products}")
    print(f"  First product completed     : cycle {r.first_product_completed_time}")
    print(f"  Last product completed      : cycle {r.last_product_completed_time}")
    print(f"  Average execution time      : {r.average_execution_time:.2f} cycles")
    print(f"  Bottleneck process          : {r.bottleneck}")
    print(f"  Avg wait before task start  : {r.average_waiting_time_to_start_task:.2f} cycles")
    print(f"  Max wait at a single task   : {r.max_waiting_time_task} cycles")
    print(f"  Max time inside a process   : {r.max_processing_time_process} cycles")
    print(f"  Total simulation duration   : {r.total_processing_time} cycles")
    print("=" * 60)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("LinProd — Production Line Simulator")
    root.geometry("1280x720")

    shared_dispatcher = EventDispatcher()

    # Terminal simulation runs in a background thread so the GUI stays responsive
    sim_thread = threading.Thread(
        target=run_terminal_simulation,
        args=(shared_dispatcher, root),
        daemon=True,
    )
    sim_thread.start()

    app = MainController(root)
    app.start_setup()

    root.mainloop()