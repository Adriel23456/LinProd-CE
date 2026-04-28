# LinProd — Production Line Simulator

> **CE-5507 Modelación Hardware/Software Orientado a Objetos**
> Instituto Tecnológico de Costa Rica

---

## Overview

LinProd is a fully object-oriented, GUI-driven production line simulator written in Python. It models a manufacturing pipeline composed of ordered **Processes**, each containing one or more ordered **Tasks**. **Products** are injected into the line and flow through every task and process according to strict FIFO queuing, configurable processing times, and discrete time-cycle control.

The system is built on a strict **MVC (Model-View-Controller)** architecture, an **Observer pattern** for decoupled event handling, and **CustomTkinter** for a modern graphical interface.

---

## Features

- Unlimited processes and tasks, all configured at runtime via GUI
- Ordered task execution within each process (order is enforced)
- Each task processes one product at a time with a FIFO waiting queue
- Discrete time-cycle simulation engine with configurable speed
- Pause at any cycle to get a full snapshot of the line state
- Soft reset (same line, new products) and hard reset (rebuild line from scratch)
- Real-time visual rendering of product movement and queue depth via Observer events
- Full statistical report with bottleneck identification, wait-time histograms, and PDF export

---

## Architecture

### MVC Layer Map

| Layer | Classes |
|---|---|
| **Model** | `Product`, `Task`, `Process`, `ProductionLine`, `SimulationEngine`, `ReportCenter`, `Report`, `EventDispatcher`, `SimulationEvent`, `SimulationEventType`, `Observer` |
| **Controller** | `MainController`, `SetupController`, `SimulationController` |
| **View** | `SetupView`, `SimulationView`, `ReportView` |

---

## Model Layer

### `Product`
Represents an item moving through the production line.

| Attribute | Type | Description |
|---|---|---|
| `id` | `int` | Unique product identifier |
| `color` | `string` | Visual identifier |
| `size` | `int` | Product size |
| `created_time` | `int` | Cycle when product was created |
| `completed_time` | `int` | Cycle when product exited the full line |
| `current_task_arrival_time` | `int` | Cycle when product arrived at current task |
| `current_process_arrival_time` | `int` | Cycle when product arrived at current process |
| `current_task_waiting_time` | `int` | Waiting time at current task |
| `current_process_waiting_time` | `int` | Accumulated waiting time inside current process |

Products do not store historical records — all statistics are accumulated by `ReportCenter`.

---

### `Task`
The atomic processing unit. Behaves like a machine inside a process.

| Attribute | Type | Description |
|---|---|---|
| `name` | `string` | Task name |
| `processing_time` | `int` | Cycles required to process one product |
| `awaiting_products_fifo` | `list[Product]` | FIFO queue of waiting products |
| `remaining_time` | `int` | Cycles left for the current product |
| `current_product` | `Product \| None` | Product being processed, or `None` if free |
| `event_dispatcher` | `EventDispatcher` | Shared event dispatcher |

**Key methods:**

```python
advance(currentTime: int) -> Product | None
receive_product(product: Product, currentTime: int)
is_busy() -> bool
```

`advance()` decrements `remaining_time`. When it reaches zero, it publishes `TASK_FINISHED` and returns the finished product. Otherwise returns `None`.

`receive_product()` records arrival time and either starts processing immediately (if free) or enqueues the product.

---

### `Process`
A stage of the production line containing an ordered list of tasks.

| Attribute | Type | Description |
|---|---|---|
| `name` | `string` | Process name |
| `tasks` | `list[Task]` | Ordered task list |
| `products_in_process` | `list[Product]` | Products currently inside this process |
| `event_dispatcher` | `EventDispatcher` | Shared event dispatcher |
| `previous_process` | `Process \| None` | Predecessor process, or `None` if first |

**Key methods:**

```python
advance(currentTime: int) -> list[Product]
move_prod_to_next_task(product: Product, task: Task)
add_task(task: Task)
receive_product(product: Product, currentTime: int)
```

`advance()` calls `advance()` on every task. Products finishing the last task are returned as a list (multiple products can complete in the same cycle).

`previous_process` satisfies the requirement that each process must be able to identify the process that feeds into it.

---

### `ProductionLine`
The full ordered pipeline.

| Attribute | Type | Description |
|---|---|---|
| `processes` | `list[Process]` | Ordered list of all processes |
| `first_process` | `Process` | Explicitly marked entry point |
| `last_process` | `Process` | Explicitly marked exit point |
| `event_dispatcher` | `EventDispatcher` | Shared event dispatcher |

**Key methods:**

```python
advance(currentTime: int) -> list[Product]
add_process(process: Process)
add_product(product: Product)
move_prod_to_next_process(product: Product, process: Process)
```

`advance()` iterates every process, routes products between processes, and publishes `PRODUCT_COMPLETED` when a product exits the last process.

---

### `SimulationEngine`
Controls the simulation lifecycle and time.

| Attribute | Type | Description |
|---|---|---|
| `current_time` | `int` | Current simulation cycle |
| `is_running` | `bool` | Whether the simulation is active |
| `production_line` | `ProductionLine` | The line being simulated |
| `report_center` | `ReportCenter` | Statistics collector |
| `simulation_speed` | `int` | Milliseconds between ticks (adjustable at runtime) |
| `event_dispatcher` | `EventDispatcher` | Shared event dispatcher |

**Key methods:**

```python
tick()
run()
pause()
reset(soft: bool)
set_simulation_speed(speed: int)
```

`tick()` is the central operation:

```
current_time += 1
completed_products = production_line.advance(current_time)
```

`run()` loops `tick()` while `is_running` is `True`, sleeping `simulation_speed` ms between calls.

**Reset behavior:**

| Mode | Behavior |
|---|---|
| **Soft reset** | Clears all product queues, timing counters, and `ReportCenter` stats. Line structure preserved. |
| **Hard reset** | Rebuilds the entire production line from scratch. Allows a completely different configuration. |

Both modes set `current_time = 0` and `is_running = False`.

---

### `EventDispatcher`
Stores observers and notifies them when events occur.

```python
subscribe(observer: Observer)
unsubscribe(observer: Observer)
notify(event: SimulationEvent)
```

---

### `SimulationEvent`
Data object representing something that happened during simulation.

| Attribute | Type |
|---|---|
| `event_type` | `SimulationEventType` |
| `product` | `Product \| None` |
| `task_name` | `string \| None` |
| `process_name` | `string \| None` |
| `time` | `int` |

---

### `SimulationEventType` (Enum)

```python
TASK_STARTED
TASK_FINISHED
TASK_WAIT_RECORDED
PROCESS_STARTED
PROCESS_FINISHED
PRODUCT_CREATED
PRODUCT_COMPLETED
SIMULATION_STARTED
SIMULATION_PAUSED
SIMULATION_RESET
SIMULATION_FINISHED
```

---

### `Observer` (Interface)

```python
update(event: SimulationEvent)
```

Implemented by `ReportCenter` and `SimulationView`.

---

### `ReportCenter`
Listens to simulation events and accumulates all statistics.

| Attribute | Type | Description |
|---|---|---|
| `waiting_times_task` | `list[int]` | One entry per product-task wait |
| `completed_times` | `list[int]` | Completion cycle of every finished product |
| `max_waiting_time_task` | `int` | Maximum individual task wait time |
| `max_waiting_time_task_name` | `string` | Name of task with max wait |
| `max_process_time` | `int` | Maximum total time spent inside any process |
| `max_process_time_name` | `string` | Name of that process |
| `first_p_completed_id` | `int` | ID of first completed product |
| `last_p_completed_id` | `int` | ID of last completed product |

**Key methods:**

```python
rec_product_completed(product: Product, time: int)
rec_waiting_time_task(product: Product, task_name: str, process_time: int)
rec_process_time(product: Product, process_name: str, process_time: int)
generate_report() -> Report
get_bottleneck()
calc_average_execution_time()
update(event: SimulationEvent)
```

---

### `Report`
Immutable data object holding the final simulation summary.

| Field | Description |
|---|---|
| `first_product_completed_time` | Cycle when the first product finished the full line |
| `last_product_completed_time` | Cycle when the last product finished the full line |
| `average_execution_time` | Mean completion cycle across all products |
| `bottleneck` | Process identified as the main congestion point |
| `average_waiting_time_to_start_task` | Mean wait time before starting any task |
| `max_waiting_time_task` | Maximum wait time recorded at a single task |
| `max_processing_time_process` | Maximum total time recorded for a process |
| `total_processing_time` | Total simulation duration |
| `completed_products` | Count of products that exited the full line |

`Report` is created by `ReportCenter.generate_report()`, handed to `MainController`, and passed to `ReportView`, which owns it for display and PDF export.

---

## Controller Layer

### `MainController`
Top-level orchestrator. First object instantiated. Bootstraps the full application.

```python
start_setup()
start_simulation(n_products: int)
show_report()
on_reset(soft: bool)
```

Owns (composition): `SetupController`, `SimulationController`, `ReportView`.

---

### `SetupController`
Handles all user actions during the configuration phase.

```python
on_add_process(name: str)
on_remove_process(name: str)
on_add_task(proc: str, name: str, proc_time: int)
on_remove_task(proc: str, task_name: str)
on_link_processes(src: str, dst: str)
on_set_first_process(name: str)
on_set_last_process(name: str)
on_reorder_task(proc: str, task_name: str, new_index: int)
on_reorder_process(proc_name: str, new_index: int)
on_confirm_setup() -> bool
```

`on_confirm_setup()` validates: at least one process exists, first and last processes are set, and no tasks are orphaned.

---

### `SimulationController`
Handles all user actions during the runtime phase.

```python
on_run(n_products: int)
on_pause()
on_resume()
on_reset(soft: bool)
on_speed_change(n: int)
on_request_report()
```

`on_run` creates and injects products then starts the engine. `on_resume` only restarts the engine after a pause — they are intentionally separate.

---

## View Layer

All views use **CustomTkinter** for a modern widget appearance.

### `SetupView`
Renders the production line configuration interface.

- `CTkFrame` process form
- `CTkScrollFrame` scrollable task list (unbounded task count)
- Canvas live preview of process linkage

```python
render_process_form()
render_task_list(procs)
render_line_preview(procs)
show_validation_error(msg)
```

---

### `SimulationView`
Renders the live simulation and implements `Observer`.

Subscribes to `EventDispatcher`. Each `update(e: SimulationEvent)` triggers a canvas redraw of only the affected element — no polling required.

```python
update(e: SimulationEvent)
render_product_move(p)
render_queue_depth(task)
render_task_status(task)
show_pause_snapshot()
clear_canvas()
```

`show_pause_snapshot()` prints a full state of all processes and tasks at the current cycle, satisfying the "photo of the line" requirement.

---

### `ReportView`
Owns the `Report` instance through composition. Renders all statistics and exports a PDF.

```python
render_metrics(r: Report)
render_bottleneck(r)
render_timeline_chart(r)
render_wait_histogram(r)
export_pdf(r: Report)
```

---

## Simulation Tick Flow

```
SimulationEngine.tick()
  current_time += 1
  completed_products = production_line.advance(current_time)

ProductionLine.advance(currentTime)
  for each process:
    products_done = process.advance(currentTime)
    route each to the next process
    if product completed the last process:
      publish PRODUCT_COMPLETED

Process.advance(currentTime)
  for each task:
    finished = task.advance(currentTime)
    if finished:
      move product to next task
      if no next task:
        return product as process-complete

Task.advance(currentTime)
  remaining_time -= 1
  if remaining_time == 0:
    publish TASK_FINISHED
    return product
  else:
    return None
```

A product finishing a task moves to the next task immediately, but the next task's processing time is consumed on subsequent ticks — no free multi-stage traversal within one cycle.

---

## Class Relationships Summary

| Relationship | Pairs |
|---|---|
| **Composition** ♦ | `ProductionLine`→`Process`, `Process`→`Task`, `MainController`→`SetupController/SimulationController/ReportView`, `ReportView`→`Report` |
| **Aggregation** ◇ | `SetupController`→`ProductionLine`, `SimulationController`→`SimulationEngine` |
| **Association** → | `SimulationEngine`→`ProductionLine/ReportCenter/EventDispatcher`, `Process`→`EventDispatcher/Product`, `Task`→`EventDispatcher/Product`, bidirectional controller↔view pairs |
| **Dependency** ⇢ | `ReportCenter`⇢`Report`, `EventDispatcher`⇢`SimulationEvent` |
| **Realization** | `ReportCenter` implements `Observer`, `SimulationView` implements `Observer` |

---

## Requirements Traceability

| Requirement | Satisfied by |
|---|---|
| Python OOP | All model classes |
| Unlimited processes and tasks | `ProductionLine`, `Process` — dynamic lists, no cap |
| Runtime configuration | `SetupController` + `SetupView` |
| Task order enforced | `Process.tasks` ordered list |
| Task inherits process characteristics | `Task` belongs to `Process`, `previous_process` link |
| First/last process identification | `ProductionLine.first_process`, `last_process` |
| Previous process reference | `Process.previous_process` |
| One product per task, FIFO queue | `Task.current_product`, `Task.awaiting_products_fifo` |
| Processing time per task | `Task.processing_time`, `Task.remaining_time` |
| Auto-advance on task completion | `Process.advance()` → `move_prod_to_next_task()` |
| Pause and snapshot | `SimulationEngine.pause()`, `SimulationView.show_pause_snapshot()` |
| Graphical effects | CustomTkinter canvas redraws via `SimulationView` |
| Reports | `ReportCenter`, `Report`, `ReportView.export_pdf()` |
| Re-run same line | Soft reset |
| Modify line and re-run | Hard reset |
| Time-cycle control | `SimulationEngine.tick()`, `simulation_speed` |

---

## Dependencies

```
python >= 3.10
customtkinter
```

---

## Authors

Adriel S. Chaves Salazar
Daniel Duarte Cordero
Ma. Paula Madrigal Sánchez
Andrés Molina Redondo

& Project Team
CE-5507 — Instituto Tecnológico de Costa Rica
Semester 1, 2026
