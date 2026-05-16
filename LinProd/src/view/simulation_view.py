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
        lbl._logo_img = img
        return lbl
    except Exception:
        return None


def _rounded_rect(canvas: tk.Canvas, x1, y1, x2, y2, r=12, **kw):
    """Draw a filled rounded rectangle on a tk.Canvas."""
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
    Live simulation view — layout matches the dashboard mockup:

      ┌─────────────────────────────────────────┬──────────────────┐
      │  title          [  t = 0  ]   [set up] [report]           │  ← top bar
      ├─────────────────────────────────────────┤  step mode       │
      │                                         │  [ ] ── [step]   │
      │   canvas (scrollable, process boxes)    │  [+ inject]      │
      │                                         │                  │
      │                                         │  event log       │
      │                                         │  ┌────────────┐  │
      ├─────────────────────────────────────────┤  │ log text   │  │
      │  [play]   [reset]   speed ─────── 50ms  │  └────────────┘  │
      └─────────────────────────────────────────┴──────────────────┘
    """

    _SIDE_PAD = 36
    _GAP      = 44

    def __init__(self, parent, dispatcher: EventDispatcher) -> None:
        ctk.CTkFrame.__init__(self, parent, fg_color=theme.BG_MAIN)
        self.controller: "SimulationController | None" = None

        # Diagram-specified widget attributes
        self.line_canvas:  tk.Canvas     | None = None
        self.status_panel: ctk.CTkFrame  | None = None
        self.speed_slider: ctk.CTkSlider | None = None

        # Internal UI state
        self._step_n_var:    ctk.StringVar  = ctk.StringVar(value="1")
        self._step_mode_var: ctk.BooleanVar = ctk.BooleanVar(value=False)
        self._play_paused:   bool           = False
        self._play_btn:      ctk.CTkButton  | None = None
        self._step_btn:      ctk.CTkButton  | None = None
        self._inject_btn:    ctk.CTkButton  | None = None
        self._speed_lbl:     ctk.CTkLabel   | None = None
        self._time_label:    ctk.CTkLabel   | None = None
        self._log_text:      tk.Text        | None = None

        self._build()
        dispatcher.subscribe(self)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self) -> None:
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
            speed_hdr, text="50 ms",
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
        self.speed_slider.set(50)
        self.speed_slider.pack(fill="x", padx=16, pady=(4, 10))

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self) -> None:
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
        if event is None:
            super().update()
        else:
            self.after(0, self._handle_event, event)

    def _handle_event(self, event: SimulationEvent) -> None:
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
            self._redraw_canvas()

        if self._time_label:
            self._time_label.configure(text=f"t = {t}")

    # ── Render methods ────────────────────────────────────────────────────────

    def render_product_move(self, product) -> None:
        self._redraw_canvas()

    def render_queue_depth(self, task) -> None:
        self._redraw_canvas()

    def render_task_status(self, event) -> None:
        self._redraw_canvas()

    def show_pause_snapshot(self) -> None:
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
        if self.line_canvas:
            self.line_canvas.delete("all")

    def set_paused_state(self) -> None:
        self._play_paused = True
        self._update_play_btn()

    # ── Canvas drawing ────────────────────────────────────────────────────────

    def _get_box_width(self, proc) -> int:
        """
        Calculate dynamic process width based on the
        longest task/process name.
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
        if not self.controller or not self.line_canvas:
            return
        engine = self.controller._engine
        c = self.line_canvas
        c.delete("all")
        c.update_idletasks()

        processes = engine.production_line.processes
        if not processes:
            return

        W = c.winfo_width()  or 600
        H = c.winfo_height() or 400
        n = len(processes)

        box_widths = [self._get_box_width(proc) for proc in processes]

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
                pid_txt = f"P{task.current_product.id}" if is_busy else "idle"
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
        if not self.controller:
            return
        self._play_paused = False
        self.controller.on_reset(soft=True)
        self._update_play_btn()
        self.after(50, self._redraw_canvas)

    def _go_to_setup(self) -> None:
        if self.controller:
            self.controller.on_reset(soft=False)

    def _go_to_report(self) -> None:
        if self.controller:
            self.controller.on_request_report()

    def _toggle_step_mode(self) -> None:
        if not self.controller:
            return
        active = self.controller.on_toggle_step_mode()
        self._log("STEP MODE ON" if active else "STEP MODE OFF")
        self._set_step_mode_ui(active)

    def _do_step(self) -> None:
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
        self._redraw_canvas()

    def _do_inject(self) -> None:
        if self.controller:
            self.controller.on_inject_product()
            self._log("+ injected product")
            self._redraw_canvas()

    def _on_speed_change(self, value) -> None:
        speed = int(value)
        if self._speed_lbl:
            self._speed_lbl.configure(text=f"{speed} ms")
        if self.controller:
            self.controller.on_speed_change(speed)

    def _show_completion(self) -> None:
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
        if self._log_text is None:
            return
        try:
            if not self._log_text.winfo_exists():
                return
        except Exception:
            return
        self._log_text.configure(state="normal")
        self._log_text.insert("end", msg + "\n")
        self._log_text.see("end")
        self._log_text.configure(state="disabled")