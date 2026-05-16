"""
simulation_view.py
------------------
Live simulation screen shown after setup is confirmed.

SimulationView implements both CTkFrame (UI container) and Observer (event
receiver). It subscribes to the shared EventDispatcher at construction time
and translates every SimulationEvent into a targeted UI update — no polling.

Layout (dashboard style):
  ┌─────────────────────────────────────────┬──────────────────┐
  │  title          [  t = 0  ]  [set up] [report]            │  top bar
  ├─────────────────────────────────────────┤  step mode       │
  │                                         │  [ ] ── [step]   │
  │   canvas (scrollable, process boxes)    │  [+ inject]      │
  │                                         │  divider         │
  │                                         │  event log       │
  ├─────────────────────────────────────────┤  (scrollable)    │
  │  [play/pause]  [reset]   speed slider   │                  │
  └─────────────────────────────────────────┴──────────────────┘

Observer thread-safety:
  update() is called from the SimulationEngine background thread. All Tkinter
  widget operations are marshalled to the main thread via self.after(0, ...).
  The _log() and _handle_event() methods include winfo_exists() guards to
  prevent crashes if the view is destroyed while the engine is still ticking.

Key rendering optimisation:
  Canvas redraws are coalesced via _schedule_redraw() / after_idle(). Multiple
  events arriving in the same tick trigger only one canvas repaint.
  Log messages are buffered in _log_buffer and flushed at most once per 16 ms
  to prevent Tkinter text-widget thrashing on high-frequency runs.

Relationships:
    - Implements: Observer (subscribed in __init__)
    - Created by: MainController.start_simulation() and _go_back_to_sim()
    - Controller injected after creation: SimulationController
    - Reads engine state: via controller._engine (for canvas drawing and snapshot)
"""

from __future__ import annotations
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.font as tkfont
from typing import TYPE_CHECKING
import customtkinter as ctk

from src.model.observer import Observer
from src.model.simulation_event import SimulationEvent
from src.model.simulation_event_type import SimulationEventType
from src.model.event_dispatcher import EventDispatcher
from . import theme
from . import dialogs

if TYPE_CHECKING:
    from src.controller.simulation_controller import SimulationController


def _load_logo(parent, size: tuple[int, int] = (36, 36)) -> ctk.CTkLabel | None:
    """
    Create a CTkLabel containing the LOGO.png asset, or return None if unavailable.

    Parameters
    ----------
    parent : ctk.CTkWidget
        Parent widget for the returned label.
    size : tuple[int, int]
        Desired (width, height) in pixels.

    Returns
    -------
    ctk.CTkLabel | None
        Ready-to-pack label, or None if PIL is not installed or file not found.
    """
    if not theme.LOGO_PATH.exists():
        return None
    try:
        from PIL import Image
        img = ctk.CTkImage(
            light_image=Image.open(theme.LOGO_PATH),
            dark_image=Image.open(theme.LOGO_PATH),
            size=size,
        )
        lbl = ctk.CTkLabel(parent, image=img, text="")
        lbl._logo_img = img   # prevent GC of the CTkImage reference
        return lbl
    except Exception:
        return None


def _rounded_rect(canvas: tk.Canvas, x1, y1, x2, y2, r=12, **kw):
    """
    Draw a filled rounded rectangle on a tk.Canvas using a smooth polygon.

    Parameters
    ----------
    canvas : tk.Canvas
        Target canvas.
    x1, y1, x2, y2 : int | float
        Bounding box coordinates.
    r : int
        Corner radius in pixels.
    **kw
        Additional keyword arguments forwarded to canvas.create_polygon
        (e.g. fill, outline, width).
    """
    pts = [
        x1 + r, y1,
        x2 - r, y1,
        x2, y1,
        x2, y1 + r,
        x2, y2 - r,
        x2, y2,
        x2 - r, y2,
        x1 + r, y2,
        x1, y2,
        x1, y2 - r,
        x1, y1 + r,
        x1, y1,
        x1 + r, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kw)


class SimulationView(ctk.CTkFrame, Observer):
    """
    Live simulation screen that implements Observer to receive engine events.

    Subscribes to the shared EventDispatcher at construction time. Each
    SimulationEvent received in update() is marshalled to the main thread via
    after(0, _handle_event) and dispatched to the appropriate render or log method.

    Canvas drawing:
      _redraw_canvas() draws the complete pipeline state on every redraw:
      one rounded-rect process box per process, one task row per task, a
      coloured status dot (red=busy, amber=queued, grey=idle), and arrows
      between processes. Box widths are computed dynamically from font metrics
      and cached in _box_widths_cache until a reset clears them.

    Play-button state machine:
      "play"   → simulation not yet started (on_run will be called)
      "pause"  → simulation is running (on_pause will be called)
      "resume" → simulation started but currently paused (on_resume will be called)
      disabled → step mode is active (step button is used instead)

    Diagram attributes (V-CD-08):
        line_canvas  : tk.Canvas        — scrollable process diagram
        status_panel : ctk.CTkFrame     — reserved (diagram compliance)
        speed_slider : ctk.CTkSlider    — tick interval control

    Relationships:
        - Implements: Observer (subscribed in __init__)
        - Created by: MainController.start_simulation() and _go_back_to_sim()
        - Controller injected after creation: SimulationController
    """

    _SIDE_PAD = 36   # horizontal padding before the first process box
    _GAP      = 44   # horizontal gap between adjacent process boxes

    def __init__(self, parent, dispatcher: EventDispatcher) -> None:
        """
        Parameters
        ----------
        parent : ctk.CTk | ctk.CTkFrame
            Root window or parent frame.
        dispatcher : EventDispatcher
            Shared event bus; this view subscribes itself immediately.
        """
        ctk.CTkFrame.__init__(self, parent, fg_color=theme.BG_MAIN)
        self.controller: "SimulationController | None" = None

        # Diagram-specified widget attributes (set during _build)
        self.line_canvas:  tk.Canvas     | None = None
        self.status_panel: ctk.CTkFrame  | None = None
        self.speed_slider: ctk.CTkSlider | None = None

        # Internal UI state
        self._step_n_var:    ctk.StringVar  = ctk.StringVar(value="1")
        self._step_mode_var: ctk.BooleanVar = ctk.BooleanVar(value=False)
        self._play_paused:   bool           = False   # True when engine is paused mid-run
        self._play_btn:      ctk.CTkButton  | None = None
        self._step_btn:      ctk.CTkButton  | None = None
        self._inject_btn:    ctk.CTkButton  | None = None
        self._speed_lbl:     ctk.CTkLabel   | None = None
        self._time_label:    ctk.CTkLabel   | None = None
        self._log_text:      tk.Text        | None = None

        # Canvas redraw coalescing
        self._redraw_scheduled: bool = False
        # Cache of per-process box widths; invalidated on reset
        self._box_widths_cache: list[int] | None = None
        # Log message buffer flushed in batches every ~16 ms
        self._log_buffer: list[str] = []
        self._log_flush_scheduled: bool = False

        self._build()
        dispatcher.subscribe(self)

    # ── Deferred-render scheduling ────────────────────────────────────────────

    def _schedule_redraw(self) -> None:
        """
        Schedule a canvas redraw at the next idle moment.

        Coalesces multiple rapid event-driven redraw requests into a single
        repaint per event loop iteration. Safe to call from the main thread.
        """
        if self._redraw_scheduled:
            return
        self._redraw_scheduled = True
        self.after_idle(self._do_redraw)

    def _do_redraw(self) -> None:
        """Execute the deferred canvas redraw with a lifecycle safety check."""
        self._redraw_scheduled = False
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        self._redraw_canvas()

    def apply_engine_speed(self, speed_ms: int) -> None:
        """
        Synchronise the speed slider and label to the engine's current speed.

        Called by SimulationController.__init__() so that when the view is
        recreated (e.g. on return from report), the slider reflects the speed
        that was already set before the view was destroyed.

        Parameters
        ----------
        speed_ms : int
            Current engine tick interval in milliseconds.
        """
        if self.speed_slider is not None:
            self.speed_slider.set(speed_ms)
        if self._speed_lbl is not None:
            self._speed_lbl.configure(text=f"{speed_ms} ms")

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        """
        Construct the full simulation screen layout.

        Grid:
          row 0 (top bar)   — spans both columns; title, clock, nav buttons
          row 1 (body)      — col 0: canvas area; col 1: sidebar (rowspan 2)
          row 2 (bottom bar)— col 0: play/reset/speed
        """
        # Root: 2 rows (top bar + body), 2 cols (canvas area + sidebar)
        self.rowconfigure(0, weight=0)   # top bar
        self.rowconfigure(1, weight=1)   # body
        self.rowconfigure(2, weight=0)   # bottom bar
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)

        self._build_top_bar()
        self._build_canvas_area()
        self._build_bottom_bar()
        self._build_sidebar()

    # ── Top bar ───────────────────────────────────────────────────────────────

    def _build_top_bar(self) -> None:
        """
        Build the top bar containing the title label, clock pill, and nav buttons.

        The clock label (self._time_label) is updated on every tick event.
        Nav buttons ("set up", "report") trigger full-reset and report transitions.
        """
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, columnspan=2, sticky="ew",
                 padx=16, pady=(12, 6))
        bar.columnconfigure(1, weight=1)   # timer expands in the middle

        # Left: title
        title_lbl = ctk.CTkLabel(
            bar, text="simulation in progress",
            font=theme.font(40, family=theme.FONT_BOLD),
            text_color=theme._TEXT_MAIN,
        )
        title_lbl.grid(row=0, column=0, sticky="w", padx=(4, 12))

        # Center: large t = N pill
        timer_frame = ctk.CTkFrame(
            bar,
            fg_color=theme._PANEL_BG,
            corner_radius=20,
            border_width=1,
            border_color=theme._PANEL_BD,
        )
        timer_frame.grid(row=0, column=0, sticky="ew", padx=(600, 8))

        self._time_label = ctk.CTkLabel(
            timer_frame, text="t = 0",
            font=theme.font(27, family=theme.FONT_BOLD),
            text_color=theme._TEXT_MAIN,
        )
        self._time_label.pack(pady=10, padx=80)

        # Right: set up + report buttons
        btn_frame = ctk.CTkFrame(bar, fg_color="transparent")
        btn_frame.grid(row=0, column=2, sticky="e", padx=(12, 4))

        ctk.CTkButton(
            btn_frame, text="set up",
            width=100, height=38, corner_radius=10,
            fg_color=theme._BTN_ADD, hover_color=theme._BTN_ADD_H,
            text_color=theme._TEXT_MAIN,
            font=theme.font(13, family=theme.FONT_BOLD),
            command=self._go_to_setup,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btn_frame, text="report",
            width=100, height=38, corner_radius=10,
            fg_color=theme._BTN_ADD, hover_color=theme._BTN_ADD_H,
            text_color=theme._TEXT_MAIN,
            font=theme.font(13, family=theme.FONT_BOLD),
            command=self._go_to_report,
        ).pack(side="left")

    # ── Canvas area ───────────────────────────────────────────────────────────

    def _build_canvas_area(self) -> None:
        """
        Build the scrollable process-diagram canvas (row 1, col 0).

        The canvas is bound to <Configure> so _redraw_canvas() fires immediately
        when the widget receives its real pixel dimensions, preventing an empty
        canvas on first display. A horizontal scrollbar is provided for lines
        wider than the viewport.
        """

        wrap = ctk.CTkFrame(
            self,
            fg_color=theme._PANEL_BG,
            corner_radius=16,
            border_width=1,
            border_color=theme._PANEL_BD,
            height=365,
        )

        wrap.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=(16, 16),
            pady=(16, 16),
        )

        # IMPORTANTE
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        self.line_canvas = tk.Canvas(
            wrap,
            bg=theme._PANEL_BG,
            highlightthickness=0,
        )

        self.line_canvas.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=8,
            pady=8,
        )

        self.line_canvas.bind(
            "<Configure>",
            lambda _e: self._redraw_canvas(),
        )

        h_scroll = ttk.Scrollbar(
            wrap,
            orient="horizontal",
            style=theme.H_SCROLL,
            command=self.line_canvas.xview,
        )

        h_scroll.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=8,
            pady=(0, 6),
        )

        self.line_canvas.configure(
            xscrollcommand=h_scroll.set
        )

        # Status panel (diagram requirement — hidden inside canvas wrap)


    # ── Bottom bar (play / reset / speed) ────────────────────────────────────

    def _build_bottom_bar(self) -> None:
        """
        Build the bottom bar with play/pause, reset, and speed-slider controls.

        The play button text and colour changes based on simulation state
        (see _update_play_btn). The speed slider controls the tick interval
        in milliseconds (50–2000 ms, 39 steps).
        """
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew", padx=(16, 16), pady=(0, 12))
        bar.columnconfigure(2, weight=1)   # speed block expands

        # PLAY button
        self._play_btn = ctk.CTkButton(
            bar, text="play",
            width=200, height=52, corner_radius=12,
            fg_color=theme._BTN_ADD, hover_color=theme._BTN_ADD_H,
            text_color=theme._TEXT_MAIN,
            font=theme.font(20, family=theme.FONT_BOLD),
            command=self._on_play_pause,
        )
        self._play_btn.grid(row=0, column=0, padx=(0, 10))

        # RESET button
        ctk.CTkButton(
            bar, text="reset",
            width=200, height=52, corner_radius=12,
            fg_color=theme._BTN_ADD, hover_color=theme._BTN_ADD_H,
            text_color=theme._TEXT_MAIN,
            font=theme.font(20, family=theme.FONT_BOLD),
            command=self._reset,
        ).grid(row=0, column=1, padx=(0, 10))

        # Speed block
        speed_block = ctk.CTkFrame(
            bar,
            fg_color=theme._PANEL_BG,
            corner_radius=12,
            border_width=1,
            border_color=theme._PANEL_BD,
        )
        speed_block.grid(row=0, column=2, sticky="ew", ipady=4)
        speed_block.columnconfigure(0, weight=1)

        speed_hdr = ctk.CTkFrame(speed_block, fg_color="transparent")
        speed_hdr.pack(fill="x", padx=16, pady=(8, 0))

        ctk.CTkLabel(
            speed_hdr, text="speed",
            font=theme.font(12, family=theme.FONT_BOLD),
            text_color=theme._TEXT_DIM2,
        ).pack(side="left")

        self._speed_lbl = ctk.CTkLabel(
            speed_hdr, text="-- ms",
            font=theme.font(12, family=theme.FONT_BOLD),
            text_color=theme.NEON,
        )
        self._speed_lbl.pack(side="right")

        self.speed_slider = ctk.CTkSlider(
            speed_block, from_=50, to=2000, number_of_steps=39,
            button_color=theme.NEON,
            button_hover_color=theme._BTN_ADD_H,
            progress_color=theme.NEON,
            fg_color=theme._PANEL_BD,
            command=self._on_speed_change,
        )
        self.speed_slider.pack(fill="x", padx=16, pady=(4, 10))

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self) -> None:
        """
        Build the right sidebar containing step-mode controls, inject button,
        and the scrollable event log.

        Step mode row: a CTkSwitch toggles step mode; when active, the step
        button and inject button become enabled and the play button is disabled.
        The event log is a read-only tk.Text widget that receives one line per
        simulation event, scrolled to the latest entry automatically.
        """
        sidebar = ctk.CTkFrame(
            self,
            fg_color=theme._PANEL_BG,
            corner_radius=16,
            border_width=1,
            border_color=theme._PANEL_BD,
            width=260,
        )
        sidebar.grid(row=1, column=1, rowspan=2, sticky="nsew",
                     padx=(0, 16), pady=(16, 12))
        sidebar.pack_propagate(False)
        sidebar.rowconfigure(3, weight=1)   # log expands

        PAD = 16

        # ── Step mode toggle row ──────────────────────────────────────────────
        step_mode_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        step_mode_frame.pack(fill="x", padx=PAD, pady=(16, 8))

        self._step_switch = ctk.CTkSwitch(
            step_mode_frame,
            text="step mode",
            font=theme.font(13, family=theme.FONT_BOLD),
            text_color=theme._TEXT_MAIN,
            fg_color=theme._PANEL_BD,
            progress_color=theme.NEON,
            button_color=theme._TEXT_MAIN,
            button_hover_color=theme.NEON,
            variable=self._step_mode_var,
            command=self._toggle_step_mode,
        )
        self._step_switch.pack(side="left")

        # ── Step row: entry + step button ────────────────────────────────────
        step_row = ctk.CTkFrame(sidebar, fg_color="transparent")
        step_row.pack(fill="x", padx=PAD, pady=(0, 6))
        step_row.columnconfigure(1, weight=1)

        self._step_entry = ctk.CTkEntry(
            step_row,
            textvariable=self._step_n_var,
            width=52, height=38, corner_radius=10,
            fg_color=theme._PANEL_BD,
            border_color=theme._PANEL_BD,
            text_color=theme._TEXT_MAIN,
            font=theme.font(12, family=theme.FONT_BOLD),
            placeholder_text="N",
        )
        self._step_entry.grid(row=0, column=0, padx=(0, 6))

        self._step_btn = ctk.CTkButton(
            step_row, text="step",
            height=38, corner_radius=10,
            fg_color=theme._BTN_ADD, hover_color=theme._BTN_ADD_H,
            text_color=theme._TEXT_MAIN,
            font=theme.font(13, family=theme.FONT_BOLD),
            state="disabled",
            command=self._do_step,
        )
        self._step_btn.grid(row=0, column=1, sticky="ew")

        # ── Inject button ─────────────────────────────────────────────────────
        self._inject_btn = ctk.CTkButton(
            sidebar, text="+ inject",
            height=40, corner_radius=10,
            fg_color=theme._BTN_ADD,
            hover_color=theme._BTN_ADD_H,
            text_color=theme.BG_MAIN,
            font=theme.font(13, family=theme.FONT_BOLD),
            state="disabled",
            command=self._do_inject,
        )
        self._inject_btn.pack(fill="x", padx=PAD, pady=(0, 14))

        # Divider
        ctk.CTkFrame(
            sidebar, fg_color=theme._PANEL_BD, height=1,
        ).pack(fill="x", padx=PAD, pady=(0, 10))

        # ── Event log ─────────────────────────────────────────────────────────
        ctk.CTkLabel(
            sidebar, text="event log",
            font=theme.font(14, family=theme.FONT_BOLD),
            text_color=theme._TEXT_MAIN,
        ).pack(anchor="w", padx=PAD, pady=(0, 6))

        log_outer = ctk.CTkFrame(
            sidebar,
            fg_color=theme.BG_MAIN,
            corner_radius=10,
            border_width=1,
            border_color=theme._PANEL_BD,
        )
        log_outer.pack(fill="both", expand=True, padx=PAD, pady=(0, 16))

        inner = tk.Frame(log_outer, bg=theme.BG_MAIN)
        inner.pack(fill="both", expand=True, padx=4, pady=4)

        v_scroll = ttk.Scrollbar(
            inner, orient="vertical", style=theme.V_SCROLL,
        )
        v_scroll.pack(side="right", fill="y")

        self._log_text = tk.Text(
            inner, width=20, height=1,
            font=(theme.FONT_FAMILY, 8),
            bg=theme.BG_MAIN, fg=theme._TEXT_DIM2,
            state="disabled", wrap="char",
            highlightthickness=0, bd=0,
            insertbackground=theme.NEON,
            selectbackground=theme._PANEL_BD,
            yscrollcommand=v_scroll.set,
        )
        self._log_text.pack(side="left", fill="both", expand=True)
        v_scroll.configure(command=self._log_text.yview)

    # ── Observer protocol ─────────────────────────────────────────────────────

    def update(self, event: SimulationEvent | None = None) -> None:
        """
        Receive a simulation event and marshal it to the main thread.

        Called by EventDispatcher.notify() from the simulation background thread.
        The None branch delegates to CTkFrame.update() (Tk widget refresh) to
        satisfy both the Observer interface and the Tkinter widget protocol.

        Parameters
        ----------
        event : SimulationEvent | None
            The event to handle, or None if called as a Tk widget update.
        """
        if event is None:
            super().update()
        else:
            # Marshal to main thread — never touch Tk widgets from a background thread.
            self.after(0, self._handle_event, event)

    def _handle_event(self, event: SimulationEvent) -> None:
        """
        Dispatch a SimulationEvent to the appropriate render or log action.

        Always runs on the main thread (scheduled via after(0, ...)). Includes
        a winfo_exists() guard so it no-ops safely if the view was destroyed
        while an event was queued (e.g. during a rapid view switch).

        Parameters
        ----------
        event : SimulationEvent
            The event to handle.
        """
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        t   = event.time
        et  = event.event_type
        pid = f"P{event.product.id}" if event.product else ""

        if et == SimulationEventType.SIMULATION_FINISHED:
            self._show_completion()
            self._play_paused = True
            self._update_play_btn()
            return

        if et == SimulationEventType.PRODUCT_COMPLETED:
            self._log(f"✓ {pid} done  t={t}")
            self.render_product_move(event.product)

        elif et == SimulationEventType.TASK_STARTED:
            self._log(f"▶ {pid}→{event.task_name}  t={t}")
            self.render_task_status(event)

        elif et == SimulationEventType.TASK_FINISHED:
            self._log(f"✔ {pid} {event.task_name}  t={t}")
            self.render_task_status(event)

        elif et == SimulationEventType.TASK_WAIT_RECORDED:
            self._log(f"⏳ {pid} waited  t={t}")

        elif et == SimulationEventType.PROCESS_STARTED:
            self._log(f"→ {pid} in {event.process_name}")

        elif et == SimulationEventType.PROCESS_FINISHED:
            self._log(f"← {pid} out {event.process_name}")

        elif et == SimulationEventType.SIMULATION_STARTED:
            self._log("▶ STARTED")
            self._play_paused = False
            self._update_play_btn()

        elif et == SimulationEventType.SIMULATION_PAUSED:
            self._log(f"⏸ PAUSED  t={t}")
            self._play_paused = True
            self._update_play_btn()

        elif et == SimulationEventType.SIMULATION_RESET:
            self._log("↺ RESET")
            self._play_paused = False
            self._update_play_btn()
            self._box_widths_cache = None
            self._schedule_redraw()

        if self._time_label:
            self._time_label.configure(text=f"t = {t}")

    # ── Render methods ────────────────────────────────────────────────────────

    def render_product_move(self, product) -> None:
        """
        Schedule a canvas redraw after a product has moved to a new location.

        Parameters
        ----------
        product : Product
            The product that just moved (not used directly — full redraw reads
            engine state).
        """
        self._schedule_redraw()

    def render_queue_depth(self, task) -> None:
        """
        Schedule a canvas redraw after a task's queue depth changed.

        Parameters
        ----------
        task : Task
            The task whose queue changed (not used directly).
        """
        self._schedule_redraw()

    def render_task_status(self, event) -> None:
        """
        Schedule a canvas redraw after a task started or finished processing.

        Parameters
        ----------
        event : SimulationEvent
            The TASK_STARTED or TASK_FINISHED event (not used directly).
        """
        self._schedule_redraw()

    def show_pause_snapshot(self) -> None:
        """
        Write a full pipeline state snapshot to the event log on pause.

        Reads current product positions from the engine (via controller) and
        logs one line per task showing the current product ID (or "idle") and
        the queue depth.
        """
        if not self.controller:
            return
        engine = self.controller._engine
        lines  = [f"SNAPSHOT  t={engine.current_time}"]
        for proc in engine.production_line.processes:
            lines.append(f"[{proc.name}]")
            for task in proc.tasks:
                p = task.current_product
                q = len(task._awaiting_products_fifo)
                lines.append(
                    f"  {task.name}: {'P'+str(p.id) if p else 'idle'}  q={q}"
                )
        self._log("\n".join(lines))

    def clear_canvas(self) -> None:
        """Delete all items from the process-diagram canvas."""
        if self.line_canvas:
            self.line_canvas.delete("all")

    def set_paused_state(self) -> None:
        """
        Force the view into the "paused" state so the play button shows "resume".

        Called by MainController._go_back_to_sim() after recreating the view
        for the return-from-report path, ensuring the user sees RESUME instead
        of PLAY even though this is a fresh SimulationView instance.
        """
        self._play_paused = True
        self._update_play_btn()

    # ── Canvas drawing ────────────────────────────────────────────────────────

    def _get_box_width(self, proc) -> int:
        """
        Calculate a process box width that comfortably fits all text inside it.

        Measures the pixel width of the process name and all task names using
        the theme font, then returns the maximum plus padding (minimum 140 px).
        Results are cached in _box_widths_cache to avoid repeated font.measure()
        calls on every redraw.

        Parameters
        ----------
        proc : Process
            The process whose name and tasks determine the box width.

        Returns
        -------
        int
            Box width in pixels (>= 140).
        """

        try:
            font=theme.font(9, family=theme.FONT_BOLD)

            # Process title width
            proc_w = font.measure(proc.name)

            # Longest task width
            longest_task = 0
            for task in proc.tasks:
                w = font.measure(task.name)
                if w > longest_task:
                    longest_task = w

            # Extra padding inside boxes
            content_w = max(proc_w, longest_task)

            return max(140, content_w + 50)

        except Exception:
            return 160

    def _redraw_canvas(self) -> None:
        """
        Fully repaint the process-diagram canvas from the current engine state.

        Deletes all canvas items and redraws:
          - One rounded-rect process box per process (vertically centred).
          - Within each box: a header with the process name, then one task row
            per task showing a status dot, task name, current product ID, and
            queue depth.
          - Horizontal arrows connecting adjacent process boxes.

        The scrollregion is set to encompass the full content width so the
        horizontal scrollbar reflects the actual pipeline length.
        """
        if not self.controller or not self.line_canvas:
            return
        engine = self.controller._engine
        c = self.line_canvas
        c.delete("all")

        processes = engine.production_line.processes
        if not processes:
            return

        W = c.winfo_width()  or 600
        H = c.winfo_height() or 400
        n = len(processes)

        if self._box_widths_cache is None or len(self._box_widths_cache) != len(processes):
            self._box_widths_cache = [self._get_box_width(proc) for proc in processes]
        box_widths = self._box_widths_cache

        xs: list[int] = []
        x = self._SIDE_PAD
        for bw in box_widths:
            xs.append(x)
            x += bw + self._GAP

        total_draw_w = x - self._GAP + self._SIDE_PAD
        draw_w = max(W, total_draw_w)

        for pi, proc in enumerate(processes):
            bw    = box_widths[pi]
            cx    = xs[pi]
            tasks = proc.tasks
            nt    = len(tasks)

            # Process box height fits all tasks
            TASK_H     = 46
            TASK_GAP   = 8
            HDR_H      = 32
            PADDING    = 10
            proc_h     = HDR_H + PADDING + nt * TASK_H + max(0, nt - 1) * TASK_GAP + PADDING
            py_top     = max(10, (H - proc_h) // 2)

            # Process container — rounded rect
            _rounded_rect(
                c, cx, py_top, cx + bw, py_top + proc_h,
                r=12,
                fill=theme._BTN_ADD,
                outline=theme._PANEL_BD,
                width=1,
            )

            # Process name header
            c.create_text(
                cx + 12, py_top + HDR_H // 2,
                text=proc.name, anchor="w",
                fill=theme._TEXT_MAIN,
               font=theme.font(12, family=theme.FONT_BOLD),
            )

            # Task boxes
            for ti, task in enumerate(tasks):
                ty = py_top + HDR_H + PADDING + ti * (TASK_H + TASK_GAP)
                tx = cx + 6
                tw = bw - 12

                is_busy = task.is_busy()
                q_len   = len(task._awaiting_products_fifo)

                # Task background — slightly lighter panel
                _rounded_rect(
                    c, tx, ty, tx + tw, ty + TASK_H,
                    r=8,
                    fill=theme._PANEL_BG,
                    outline=theme._PANEL_BD,
                    width=1,
                )

                # Status dot color
                dot_color = (
                    theme.NEON_RED   if is_busy else
                    theme.NEON_AMBER if q_len > 0 else
                    theme._PANEL_BD
                )
                c.create_oval(
                    tx + 8, ty + TASK_H // 2 - 4,
                    tx + 16, ty + TASK_H // 2 + 4,
                    fill=dot_color, outline="",
                )

                # Task name
                c.create_text(
                    tx + 22, ty + 13,
                    text=task.name, anchor="w",
                    fill=theme._TEXT_MAIN,
                    font=theme.font(10, family=theme.FONT_BOLD),
                )

                # Status text
                pid_txt = f"P{task.current_product.id}" if task.current_product else "idle"
                c.create_text(
                    tx + 22, ty + 28,
                    text=f"{pid_txt}  q = {q_len}", anchor="w",
                    fill=theme._TEXT_DIM2,
                    font=theme.font(9, family=theme.FONT_BOLD),
                )

            # Arrow to next process
            if pi < n - 1:
                ax_start = cx + bw + 4
                ax_end   = xs[pi + 1] - 4
                mid_y    = py_top + proc_h // 2
                c.create_line(
                    ax_start, mid_y, ax_end, mid_y,
                    fill=theme._TEXT_DIM2, width=2, arrow="last",
                    arrowshape=(10, 12, 4),
                )

        c.configure(scrollregion=(0, 0, draw_w, H))

    # ── Button handlers ───────────────────────────────────────────────────────

    def _on_play_pause(self) -> None:
        """
        Handle the play/pause/resume button press.

        State machine:
          not started → opens product-count dialog → calls controller.on_run(n)
          paused       → calls controller.on_resume()
          running      → calls controller.on_pause()

        No-op in step mode (the step button is used instead).
        """
        if not self.controller:
            return
        if self._step_mode_var.get():
            return

        if not self.controller.simulation_started:
            n = dialogs.ask_product_count(self)
            if n is None:
                return
            self.controller.on_run(n)
            self._play_paused = False
            self._update_play_btn()
        elif self._play_paused:
            self.controller.on_resume()
            self._play_paused = False
            self._update_play_btn()
        else:
            self.controller.on_pause()

    def _update_play_btn(self) -> None:
        """
        Reconfigure the play button text and colours to match current state.

        States:
          step mode active  → disabled grey "play"
          not yet started   → normal "play"  (dark panel colour)
          paused mid-run    → normal "resume" (NEON green)
          running           → normal "pause"  (NEON_AMBER)
        """
        if self._play_btn is None:
            return
        if self._step_mode_var.get():
            self._play_btn.configure(
                text="play", state="disabled",
                fg_color=theme._PANEL_BD,
                text_color=theme._TEXT_DIM2,
            )
        elif not (self.controller and self.controller.simulation_started):
            self._play_btn.configure(
                text="play", state="normal",
                fg_color=theme._BTN_ADD,
                text_color=theme._TEXT_MAIN,
            )
        elif self._play_paused:
            self._play_btn.configure(
                text="resume", state="normal",
                fg_color=theme.NEON,
                text_color=theme.BG_MAIN,
            )
        else:
            self._play_btn.configure(
                text="pause", state="normal",
                fg_color=theme.NEON_AMBER,
                text_color=theme.BG_MAIN,
            )

    def _set_step_mode_ui(self, active: bool) -> None:
        """
        Enable or disable the step/inject buttons based on step-mode state.

        Parameters
        ----------
        active : bool
            True when step mode is being activated; False when deactivated.
        """
        if active:
            if self._step_btn:
                self._step_btn.configure(state="normal", fg_color=theme.NEON,
                                         text_color=theme.BG_MAIN)
            if self._inject_btn:
                self._inject_btn.configure(state="normal", fg_color=theme.NEON)
        else:
            if self._step_btn:
                self._step_btn.configure(state="disabled", fg_color=theme._BTN_ADD,
                                         text_color=theme._TEXT_MAIN)
            if self._inject_btn:
                self._inject_btn.configure(state="disabled", fg_color=theme._BTN_ADD)
        self._update_play_btn()

    def _reset(self) -> None:
        """
        Handle the reset button press.

        Clears _play_paused, delegates a soft reset to the controller (which
        calls engine.reset()), resets the box-widths cache, and schedules a
        canvas redraw so process boxes reappear immediately after reset.
        """
        if not self.controller:
            return
        self._play_paused = False
        self.controller.on_reset(soft=True)
        self._update_play_btn()
        self._box_widths_cache = None
        self._schedule_redraw()

    def _go_to_setup(self) -> None:
        """Handle the "set up" nav button — performs a full reset to SetupView."""
        if self.controller:
            self.controller.on_reset(soft=False)

    def _go_to_report(self) -> None:
        """Handle the "report" nav button — navigates to ReportView."""
        if self.controller:
            self.controller.on_request_report()

    def _toggle_step_mode(self) -> None:
        """
        Toggle step mode via the sidebar switch.

        Calls controller.on_toggle_step_mode() which returns the new state,
        logs a message, and updates the step/inject/play button enablement.
        """
        if not self.controller:
            return
        active = self.controller.on_toggle_step_mode()
        self._log("STEP MODE ON" if active else "STEP MODE OFF")
        self._set_step_mode_ui(active)

    def _do_step(self) -> None:
        """
        Advance the simulation by N cycles on manual step button press.

        Reads N from the step entry widget; resets to 1 if the value is
        invalid or out of the 1–99999 range.
        """
        if not self.controller:
            return
        try:
            n = int(self._step_n_var.get())
            if not (1 <= n <= 99999):
                raise ValueError
        except ValueError:
            self._step_n_var.set("1")
            n = 1
        self.controller.on_step(n)
        self._schedule_redraw()

    def _do_inject(self) -> None:
        """Handle the "+ inject" button — injects one product and redraws the canvas."""
        if self.controller:
            self.controller.on_inject_product()
            self._log("+ injected product")
            self._schedule_redraw()

    def _on_speed_change(self, value) -> None:
        """
        Handle speed slider movement.

        Updates the speed label and delegates to the controller which sets the
        engine's tick interval. The change takes effect on the next loop iteration.

        Parameters
        ----------
        value : float
            Raw slider value (cast to int for milliseconds).
        """
        speed = int(value)
        if self._speed_lbl:
            self._speed_lbl.configure(text=f"{speed} ms")
        if self.controller:
            self.controller.on_speed_change(speed)

    def _show_completion(self) -> None:
        """
        Display a blocking modal dialog announcing production completion.

        The dialog is a CTkToplevel with transient() set so it stays above the
        main window. grab_set() is deferred by 50 ms (after(50, ...)) to ensure
        the window is fully mapped before the grab is applied, preventing a
        Tkinter grab-before-map error on some platforms.
        """
        self._log("🏁 ALL DONE!")
        try:
            modal = ctk.CTkToplevel(self)
            modal.title("Production Complete")
            modal.geometry("420x220")
            modal.transient(self.winfo_toplevel())
            modal.resizable(False, False)
            modal.configure(fg_color=theme._PANEL_BG)

            ctk.CTkLabel(
                modal, text="PRODUCTION COMPLETE!",
                font=theme.font(18, family=theme.FONT_BOLD),
                text_color=theme.NEON,
            ).pack(pady=(36, 8))
            ctk.CTkLabel(
                modal, text="Press  report  to view results",
                font=theme.font(12, family=theme.FONT_BOLD),
                text_color=theme._TEXT_DIM2,
            ).pack(pady=(0, 24))
            ctk.CTkButton(
                modal, text="OK", width=120, corner_radius=10, height=36,
                fg_color=theme.NEON, text_color=theme.BG_MAIN,
                font=theme.font(13, family=theme.FONT_BOLD),
                command=modal.destroy,
            ).pack()
            modal.after(50, modal.grab_set)
        except Exception:
            pass

    # ── Event log ─────────────────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        """
        Append a message to the event log with batched flushing.

        Messages are accumulated in _log_buffer and flushed at most once per
        16 ms. This prevents Tkinter Text widget thrashing on high-frequency
        simulation events (e.g. many TASK_STARTED events per second at high speed).

        Parameters
        ----------
        msg : str
            The log line to append (no trailing newline needed).
        """
        if self._log_text is None:
            return
        self._log_buffer.append(msg)
        if self._log_flush_scheduled:
            return
        self._log_flush_scheduled = True
        self.after(16, self._flush_log)

    def _flush_log(self) -> None:
        """
        Write all buffered log messages to the Text widget in a single batch.

        Includes a winfo_exists() guard to prevent crashes if the widget was
        destroyed between the after() scheduling and the actual flush execution.
        """
        self._log_flush_scheduled = False
        if not self._log_buffer or self._log_text is None:
            return
        try:
            if not self._log_text.winfo_exists():
                return
        except Exception:
            return
        chunk = "\n".join(self._log_buffer) + "\n"
        self._log_buffer.clear()
        self._log_text.configure(state="normal")
        self._log_text.insert("end", chunk)
        self._log_text.see("end")
        self._log_text.configure(state="disabled")