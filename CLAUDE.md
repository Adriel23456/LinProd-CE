# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**LinProd** — Production Line Simulator. A discrete-event, GUI-driven simulation of a manufacturing pipeline built in Python 3.10+ using CustomTkinter. Course project for CE-5507 Modelación Hardware/Software Orientado a Objetos (TEC, Semester 1, 2026).

## Setup & Running

All commands run from inside the `LinProd/` subdirectory with the virtualenv active.

```bash
cd LinProd
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS
pip install -r requirements.txt
python main.py
```

Dependencies: `customtkinter>=5.2.0`, `reportlab>=4.0.0`.

## No Formal Tests

There is no test suite. Manual validation uses:
- The `DebugObserver` in `main.py` that prints every simulation event to stdout.
- The terminal simulation in `main.py` that runs 3 products through `assets/production_line.json` for up to 300 ticks and prints a final statistical report — this is the primary smoke-test path.

## Architecture

The project is **MVC + Observer**, structured under `LinProd/src/`:

```
LinProd/
  main.py                        # entry point
  assets/production_line.json    # example 4-process cake line config
  src/
    model/       — simulation logic, state, event publishing
    controller/  — input handling, MVC coordination
    view/        — CustomTkinter GUI
```

### Model Layer (`src/model/`)

The core domain is a pipeline: `ProductionLine` → `Process` → `Task` → `Product`.

- **`Task`** — atomic processing unit (one machine). Holds a FIFO queue (`awaiting_products_fifo`), a `current_product`, and `remaining_time`. `advance()` decrements time; when it hits 0 the finished product is returned and the next product in the queue starts.
- **`Process`** — ordered list of tasks. Uses a **two-pass** design in `advance()`: advance all tasks first, then route finished products. This prevents a product from being processed twice in one tick.
- **`ProductionLine`** — ordered list of processes with explicit `first_process` / `last_process` markers. Same two-pass pattern. Routes products between processes; publishes `PRODUCT_COMPLETED` when a product exits the last process.
- **`SimulationEngine`** — owns the clock (`current_time`), a background thread (`threading`), and `simulation_speed` (ms between ticks). `reset(soft=True)` clears queues/state but keeps structure; `reset(soft=False)` rebuilds from scratch.
- **`LineLoader`** — static `load(path, dispatcher)` deserializes JSON into the full object graph.
- **`EventDispatcher`** — pub/sub event bus shared by all model objects. Observers implement `Observer.update(event: SimulationEvent)`.
- **`SimulationEvent`** / **`SimulationEventType`** — event data object + 11-value enum (`TASK_STARTED`, `TASK_FINISHED`, `TASK_WAIT_RECORDED`, `PROCESS_STARTED`, `PROCESS_FINISHED`, `PRODUCT_CREATED`, `PRODUCT_COMPLETED`, `SIMULATION_STARTED`, `SIMULATION_PAUSED`, `SIMULATION_RESET`, `SIMULATION_FINISHED`).
- **`ReportCenter`** — implements `Observer`; subscribes to all events, accumulates statistics, produces an immutable `Report` via `generate_report()`.
- **`Product`** — carries `id`, `color`, `size`, timing fields (`created_time`, `completed_time`, `current_task_arrival_time`, etc.). Does **not** store history; `ReportCenter` owns all stats.

### Controller Layer (`src/controller/`)

- **`MainController`** — first object instantiated; bootstraps the full app. Owns `EventDispatcher`, `ProductionLine`, `SimulationEngine` and composes `SetupController`, `SimulationController`, `ReportView`. Orchestrates phase transitions (setup → simulation → report).
- **`SetupController`** — configuration phase: add/remove processes and tasks, link, reorder, set first/last. `on_confirm_setup()` validates at least one process exists, first/last are set, no orphaned tasks.
- **`SimulationController`** — runtime phase: `on_run()` creates/injects products then starts the engine; `on_resume()` only restarts after pause (intentionally separate from `on_run()`).

### View Layer (`src/view/`)

- **`SetupView`** — process form, scrollable task list, canvas-based line preview.
- **`SimulationView`** — implements `Observer`; each `update(e)` triggers a targeted canvas redraw (no polling). Uses Tk's `after()` to marshal updates from the simulation thread. Canvas background `#1a1a2e`. `show_pause_snapshot()` prints full line state on pause.
- **`ReportView`** — owns the `Report` instance (composition). Renders metrics, bottleneck, timeline chart, wait histogram, and exports to PDF via ReportLab.

### Tick Flow (Critical Invariant)

```
SimulationEngine.tick()
  └─ ProductionLine.advance()        # two-pass: advance all processes, then route
       └─ Process.advance()          # two-pass: advance all tasks, then route
            └─ Task.advance()        # decrement remaining_time; return product if done
```

A product finishing a task moves to the next task immediately, but the next task's `processing_time` is consumed starting on the **next** tick — no free multi-stage traversal in one cycle.

## Git Branching

| Branch | Push directly? | PR target | Approval |
|---|---|---|---|
| `master` | No | — | — |
| `develop/**` | No | `master` | 1 required |
| `task/**` | Yes | `develop/**` | Not required |

Naming: lowercase, hyphen-separated (e.g., `task/fix-queue-routing`, `develop/report-view`).
