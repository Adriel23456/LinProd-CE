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
    """Return a CTkLabel bearing the logo image, or None if unavailable."""
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
        lbl._logo_img = img  # prevent GC
        return lbl
    except Exception:
        return None


class SimulationView(ctk.CTkFrame, Observer):
    """
    Live simulation canvas + controls.

    Observer: update(event) is called from the simulation thread and
    marshalled to the Tk main thread via after(0, ...).

    V-SOLID-LSP-01: update(event=None) delegates to CTkFrame.update() so
    Tkinter's internal widget refresh still works.

    Diagram attributes (V-CD-08, V-CD-09):
        line_canvas  : tk.Canvas
        status_panel : CTkFrame
        speed_slider : CTkSlider
    """

    _SIDE_PAD = 36   # left/right padding inside the scroll canvas
    _GAP      = 44   # horizontal gap between process boxes

    def __init__(self, parent, dispatcher: EventDispatcher) -> None:
        ctk.CTkFrame.__init__(self, parent, fg_color=theme.BG_MAIN)
        self.controller: "SimulationController | None" = None

        # Diagram-specified widget attributes
        self.line_canvas:  tk.Canvas        | None = None
        self.status_panel: ctk.CTkFrame     | None = None
        self.speed_slider: ctk.CTkSlider    | None = None

        # Internal UI state
        self._step_n_var:    ctk.StringVar  = ctk.StringVar(value="1")
        self._step_mode_var: ctk.BooleanVar = ctk.BooleanVar(value=False)
        self._play_paused:   bool           = False
        self._play_btn:      ctk.CTkButton  | None = None
        self._step_btn:      ctk.CTkButton  | None = None
        self._inject_btn:    ctk.CTkButton  | None = None
        self._speed_lbl:     ctk.CTkLabel   | None = None

        # Log (tk.Text widget with scrollbar)
        self._log_text: tk.Text | None = None

        self._build()
        dispatcher.subscribe(self)

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build(self) -> None:
        self._build_top_bar()
        self._build_center()

    def _build_top_bar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=theme.BG_PANEL, corner_radius=0,
                           border_width=1, border_color=theme.BORDER)
        bar.pack(fill="x")

        # Logo
        logo_lbl = _load_logo(bar, size=(32, 32))
        if logo_lbl:
            logo_lbl.pack(side="left", padx=(10, 0), pady=8)

        ctk.CTkLabel(
            bar, text="LinProd  —  Simulation",
            font=theme.font(18, bold=True), text_color=theme.NEON,
        ).pack(side="left", padx=12, pady=10)

        ctk.CTkButton(
            bar, text="◀ SETUP", width=100, corner_radius=0, height=32,
            fg_color="transparent", text_color=theme.TEXT_DIM,
            border_width=1, border_color=theme.BORDER,
            hover_color=theme.BG_PANEL, font=theme.font(11, bold=True),
            command=self._go_to_setup,
        ).pack(side="right", padx=6, pady=8)

        ctk.CTkButton(
            bar, text="REPORT ▶", width=100, corner_radius=0, height=32,
            fg_color=theme.NEON_BLUE, text_color=theme.BG_MAIN,
            hover_color="#009fcc", font=theme.font(11, bold=True),
            command=self._go_to_report,
        ).pack(side="right", padx=2, pady=8)

    def _build_center(self) -> None:
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.pack(fill="both", expand=True)
        center.columnconfigure(0, weight=3)
        center.columnconfigure(1, weight=0)
        center.rowconfigure(0, weight=1)

        # Canvas area with horizontal scrollbar
        canvas_wrap = ctk.CTkFrame(center, fg_color="transparent")
        canvas_wrap.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        canvas_wrap.rowconfigure(0, weight=1)
        canvas_wrap.columnconfigure(0, weight=1)

        self.line_canvas = tk.Canvas(
            canvas_wrap, bg=theme.BG_MAIN, highlightthickness=1,
            highlightbackground=theme.BORDER,
        )
        self.line_canvas.grid(row=0, column=0, sticky="nsew")
        # Draw immediately when canvas receives its real size on first layout
        self.line_canvas.bind("<Configure>", lambda _e: self._redraw_canvas())

        h_scroll = ttk.Scrollbar(
            canvas_wrap, orient="horizontal", style=theme.H_SCROLL,
            command=self.line_canvas.xview,
        )
        h_scroll.grid(row=1, column=0, sticky="ew")
        self.line_canvas.configure(xscrollcommand=h_scroll.set)

        # Sidebar
        sidebar = ctk.CTkFrame(center, fg_color=theme.BG_PANEL, corner_radius=0,
                                border_width=1, border_color=theme.BORDER,
                                width=240)
        sidebar.grid(row=0, column=1, sticky="nsew", padx=(0, 8), pady=8)
        sidebar.pack_propagate(False)
        self._build_sidebar(sidebar)

    def _build_sidebar(self, parent: ctk.CTkFrame) -> None:
        PAD = 14  # horizontal padding for sidebar items

        def sep():
            ctk.CTkLabel(parent, text="─" * 24,
                         text_color=theme.BORDER_LIT,
                         font=theme.font(8)).pack(pady=2)

        ctk.CTkLabel(
            parent, text="CONTROLS",
            font=theme.font(14, bold=True), text_color=theme.NEON,
        ).pack(pady=(14, 6), padx=PAD)

        # PLAY / PAUSE
        self._play_btn = ctk.CTkButton(
            parent, text="▶  PLAY", corner_radius=0, height=36,
            fg_color=theme.NEON, text_color=theme.BG_MAIN,
            hover_color="#00cc7a", font=theme.font(14, bold=True),
            command=self._on_play_pause,
        )
        self._play_btn.pack(fill="x", padx=PAD, pady=3)

        # Reset
        ctk.CTkButton(
            parent, text="↺  RESET", corner_radius=0, height=32,
            fg_color="transparent", text_color=theme.NEON_AMBER,
            border_width=1, border_color=theme.NEON_AMBER,
            hover_color=theme.BG_PANEL, font=theme.font(12, bold=True),
            command=self._reset,
        ).pack(fill="x", padx=PAD, pady=3)

        sep()

        # Step mode checkbox
        ctk.CTkCheckBox(
            parent, text="STEP MODE",
            font=theme.font(12, bold=True), text_color=theme.TEXT,
            fg_color=theme.NEON, hover_color="#00cc7a",
            checkmark_color=theme.BG_MAIN,
            variable=self._step_mode_var,
            command=self._toggle_step_mode,
        ).pack(anchor="w", padx=PAD, pady=4)

        # Step count + step button
        step_row = ctk.CTkFrame(parent, fg_color="transparent")
        step_row.pack(fill="x", padx=PAD, pady=2)
        ctk.CTkEntry(
            step_row, textvariable=self._step_n_var,
            width=50, height=30, corner_radius=0,
            fg_color=theme.BG_INPUT, border_color=theme.BORDER,
            text_color=theme.TEXT, font=theme.font(12),
            placeholder_text="N",
        ).pack(side="left")
        self._step_btn = ctk.CTkButton(
            step_row, text="STEP ▶", corner_radius=0, height=30,
            fg_color=theme.BG_PANEL, text_color=theme.TEXT_DIM,
            border_width=1, border_color=theme.BORDER,
            hover_color=theme.BORDER, font=theme.font(11, bold=True),
            state="disabled",
            command=self._do_step,
        )
        self._step_btn.pack(side="left", padx=4, fill="x", expand=True)

        # Inject button (initially disabled)
        self._inject_btn = ctk.CTkButton(
            parent, text="+ INJECT", corner_radius=0, height=30,
            fg_color="transparent", text_color=theme.TEXT_DIM,
            border_width=1, border_color=theme.BORDER,
            hover_color=theme.BG_PANEL, font=theme.font(11, bold=True),
            state="disabled",
            command=self._do_inject,
        )
        self._inject_btn.pack(fill="x", padx=PAD, pady=2)

        sep()

        # Speed slider + label
        speed_hdr = ctk.CTkFrame(parent, fg_color="transparent")
        speed_hdr.pack(fill="x", padx=PAD, pady=(2, 0))
        ctk.CTkLabel(
            speed_hdr, text="SPEED",
            font=theme.font(10, bold=True), text_color=theme.TEXT_DIM,
        ).pack(side="left")
        self._speed_lbl = ctk.CTkLabel(
            speed_hdr, text="500 ms",
            font=theme.font(10, bold=True), text_color=theme.NEON_AMBER,
        )
        self._speed_lbl.pack(side="right")

        self.speed_slider = ctk.CTkSlider(
            parent, from_=50, to=2000, number_of_steps=39,
            button_color=theme.NEON, button_hover_color="#00cc7a",
            progress_color=theme.NEON, fg_color=theme.BORDER,
            command=self._on_speed_change,
        )
        self.speed_slider.set(500)
        self.speed_slider.pack(fill="x", padx=PAD, pady=(0, 6))

        sep()

        # Event log — font intentionally kept at 8 (excluded from size bump)
        ctk.CTkLabel(
            parent, text="EVENT LOG",
            font=theme.font(10, bold=True), text_color=theme.TEXT_DIM,
        ).pack(anchor="w", padx=PAD)

        log_outer = tk.Frame(parent, bg=theme.BG_PANEL)
        log_outer.pack(fill="both", expand=True, padx=PAD, pady=(2, 4))

        self._log_text = tk.Text(
            log_outer, width=20, height=1,
            font=(theme.FONT_FAMILY, 8),
            bg=theme.BG_INPUT, fg=theme.TEXT,
            state="disabled", wrap="char",
            highlightthickness=0, bd=0,
            insertbackground=theme.NEON,
            selectbackground=theme.BORDER_LIT,
        )
        v_scroll = ttk.Scrollbar(
            log_outer, orient="vertical", style=theme.V_SCROLL,
            command=self._log_text.yview,
        )
        v_scroll.pack(side="right", fill="y")
        self._log_text.pack(side="left", fill="both", expand=True)
        self._log_text.configure(yscrollcommand=v_scroll.set)

        # Status panel (required by diagram)
        self.status_panel = ctk.CTkFrame(
            parent, fg_color=theme.BG_MAIN, corner_radius=0,
            border_width=1, border_color=theme.BORDER,
        )
        self.status_panel.pack(fill="x", padx=PAD, pady=6)
        self._time_label = ctk.CTkLabel(
            self.status_panel, text="t = 0",
            font=theme.font(14, bold=True), text_color=theme.NEON_AMBER,
        )
        self._time_label.pack(pady=6)

    # ── Observer protocol (V-SOLID-LSP-01) ───────────────────────────────────

    def update(self, event: SimulationEvent | None = None) -> None:
        if event is None:
            super().update()
        else:
            self.after(0, self._handle_event, event)

    def _handle_event(self, event: SimulationEvent) -> None:
        # Guard: widget may have been destroyed if user switched views
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
            # Redraw boxes immediately so they remain visible after reset
            self._redraw_canvas()

        if hasattr(self, "_time_label"):
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
                lines.append(f"  {task.name}: {'P'+str(p.id) if p else 'idle'}  q={q}")
        self._log("\n".join(lines))

    def clear_canvas(self) -> None:
        if self.line_canvas:
            self.line_canvas.delete("all")

    def set_paused_state(self) -> None:
        """Mark simulation as paused/resumable (called when returning from report)."""
        self._play_paused = True
        self._update_play_btn()

    # ── Canvas drawing ────────────────────────────────────────────────────────

    def _get_box_width(self, proc) -> int:
        """Compute minimum box width to fit the full process name and all task names."""
        try:
            f = tkfont.Font(family=theme.FONT_FAMILY, size=8, weight="bold")
            name_w = f.measure(proc.name) + 28
            task_w = max((f.measure(t.name) + 28 for t in proc.tasks), default=90)
            return max(90, name_w, task_w)
        except Exception:
            return max(90, len(proc.name) * 9 + 28)

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
            bw     = box_widths[pi]
            cx     = xs[pi]
            tasks  = proc.tasks
            nt     = len(tasks)
            proc_h = nt * 54 + 30
            py_top = max(10, (H - proc_h) // 2)

            c.create_rectangle(
                cx, py_top, cx + bw, py_top + proc_h,
                fill=theme.BG_PANEL, outline=theme.NEON_BLUE, width=2,
            )
            c.create_text(
                cx + bw // 2, py_top + 13, text=proc.name,
                fill=theme.NEON_BLUE, font=(theme.FONT_FAMILY, 8, "bold"),
            )

            for ti, task in enumerate(tasks):
                ty      = py_top + 28 + ti * 54
                is_busy = task.is_busy()
                q_len   = len(task._awaiting_products_fifo)
                color   = (theme.NEON_RED   if is_busy else
                           theme.NEON_AMBER if q_len > 0 else
                           theme.NEON)

                task_bw = bw - 8
                tx      = cx + 4

                c.create_rectangle(
                    tx, ty, tx + task_bw, ty + 40,
                    fill=color, outline=theme.BORDER, width=1,
                )
                c.create_text(
                    tx + task_bw // 2, ty + 13, text=task.name,
                    fill=theme.BG_MAIN, font=(theme.FONT_FAMILY, 8, "bold"),
                )
                pid_txt = f"P{task.current_product.id}" if is_busy else "idle"
                c.create_text(
                    tx + task_bw // 2, ty + 28, text=f"{pid_txt}  q={q_len}",
                    fill=theme.BG_MAIN, font=(theme.FONT_FAMILY, 7),
                )

            if pi < n - 1:
                ax_start = cx + bw
                ax_end   = xs[pi + 1]
                mid_y    = H // 2
                c.create_line(
                    ax_start, mid_y, ax_end, mid_y,
                    fill=theme.NEON_BLUE, width=2, arrow="last",
                )

        c.configure(scrollregion=(0, 0, draw_w, H))

    # ── Button / event handlers ───────────────────────────────────────────────

    def _on_play_pause(self) -> None:
        if not self.controller:
            return
        if self._step_mode_var.get():
            return  # PLAY is disabled in step mode

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
                text="▶  PLAY", state="disabled",
                fg_color=theme.BORDER, text_color=theme.TEXT_DIM,
            )
        elif not (self.controller and self.controller.simulation_started):
            # Not started yet → PLAY
            self._play_btn.configure(
                text="▶  PLAY", state="normal",
                fg_color=theme.NEON, text_color=theme.BG_MAIN,
            )
        elif self._play_paused:
            # Started but paused → RESUME
            self._play_btn.configure(
                text="▶  RESUME", state="normal",
                fg_color=theme.NEON, text_color=theme.BG_MAIN,
            )
        else:
            # Running → PAUSE
            self._play_btn.configure(
                text="⏸  PAUSE", state="normal",
                fg_color=theme.NEON_AMBER, text_color=theme.BG_MAIN,
            )

    def _set_step_mode_ui(self, active: bool) -> None:
        """Enable/disable step/inject buttons based on step mode; update PLAY."""
        if active:
            if self._step_btn:
                self._step_btn.configure(
                    state="normal",
                    text_color=theme.NEON_BLUE,
                    border_color=theme.NEON_BLUE,
                )
            if self._inject_btn:
                self._inject_btn.configure(
                    state="normal",
                    text_color=theme.NEON_AMBER,
                    border_color=theme.NEON_AMBER,
                )
        else:
            if self._step_btn:
                self._step_btn.configure(
                    state="disabled",
                    text_color=theme.TEXT_DIM,
                    border_color=theme.BORDER,
                )
            if self._inject_btn:
                self._inject_btn.configure(
                    state="disabled",
                    text_color=theme.TEXT_DIM,
                    border_color=theme.BORDER,
                )
        self._update_play_btn()

    def _reset(self) -> None:
        """Reset to initial state: stopped, waiting for PLAY press."""
        if not self.controller:
            return
        self._play_paused = False
        self.controller.on_reset(soft=True)
        self._update_play_btn()
        # Ensure process boxes are immediately visible after reset
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
        """Show production-complete as a blocking modal popup."""
        self._log("🏁 ALL DONE!")
        try:
            modal = ctk.CTkToplevel(self)
            modal.title("Production Complete")
            modal.geometry("420x220")
            modal.transient(self.winfo_toplevel())
            modal.resizable(False, False)
            modal.configure(fg_color=theme.BG_PANEL)

            ctk.CTkLabel(
                modal, text="PRODUCTION COMPLETE!",
                font=theme.font(18, bold=True), text_color=theme.NEON,
            ).pack(pady=(36, 8))
            ctk.CTkLabel(
                modal, text="Press  REPORT ▶  to view results",
                font=theme.font(12), text_color=theme.TEXT_DIM,
            ).pack(pady=(0, 24))
            ctk.CTkButton(
                modal, text="OK", width=120, corner_radius=0, height=36,
                fg_color=theme.NEON, text_color=theme.BG_MAIN,
                hover_color="#00cc7a", font=theme.font(13, bold=True),
                command=modal.destroy,
            ).pack()
            modal.after(50, modal.grab_set)
        except Exception:
            pass

    # ── Event log ─────────────────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        if self._log_text is None:
            return
        # Guard: widget may be gone after a view switch
        try:
            if not self._log_text.winfo_exists():
                return
        except Exception:
            return
        self._log_text.configure(state="normal")
        self._log_text.insert("end", msg + "\n")
        self._log_text.see("end")
        self._log_text.configure(state="disabled")
