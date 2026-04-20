from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

import tkinter as tk
from tkinter import ttk

from railroad_sim.presentation.gui.tkinter.canvas.design_canvas import DesignCanvas
from railroad_sim.presentation.gui.tkinter.panels.inspector_panel import InspectorPanel


class RailroadStudioApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Railroad Studio")
        self.root.geometry("1600x960")
        self.root.minsize(1200, 760)

        self.status_var = tk.StringVar(value="Ready.")
        self.cursor_pos_var = tk.StringVar(value="X: - Y: -")

        # Toolbar visibility
        self.show_layout_tools_toolbar = tk.BooleanVar(value=True)
        self.show_trackwork_toolbar = tk.BooleanVar(value=True)
        self.show_view_controls_toolbar = tk.BooleanVar(value=True)

        # Trackwork state
        self.trackwork_element_var = tk.StringVar(value="Track")

        # View toggles
        self.show_grid_var = tk.BooleanVar(value=False)
        self.show_snap_var = tk.BooleanVar(value=True)
        self.show_labels_var = tk.BooleanVar(value=False)
        self.show_rulers_var = tk.BooleanVar(value=True)

        # status variables (live)
        self.grid_status_var = tk.StringVar(value="Grid: Off")
        self.snap_status_var = tk.StringVar(value="Snap: Off")
        self.rulers_status_var = tk.StringVar(value="Rulers: On")

        self._build_style()
        self._build_menu()
        self._build_layout()
        self.root.after(50, self._set_initial_main_pane_sash)

        self.show_grid_var.trace_add("write", lambda *_: self._sync_view_state())
        self.show_snap_var.trace_add("write", lambda *_: self._sync_view_state())
        self.show_rulers_var.trace_add("write", lambda *_: self._sync_view_state())

        self.trackwork_element_var.trace_add(
            "write",
            lambda *_: self._sync_trackwork_state(),
        )

        self._sync_view_state()
        self._sync_trackwork_state()

    # ------------------------------------------------------------------
    # Style
    # ------------------------------------------------------------------
    def _build_style(self) -> None:
        style = ttk.Style()
        style.configure("Studio.Toolbar.TFrame", padding=(4, 2))
        style.configure("Studio.Panel.TFrame", padding=6)
        style.configure("Studio.Section.TLabel", font=("Arial", 8, "bold"))
        style.configure("Studio.Toolbar.TButton", padding=(4, 1), font=("Arial", 8))
        style.configure(
            "Studio.Toolbar.TCheckbutton", padding=(2, 1), font=("Arial", 8)
        )
        style.configure("Studio.Toolbar.TLabel", font=("Arial", 8))

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------
    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)

        menubar.add_cascade(label="File", menu=tk.Menu(menubar, tearoff=0))
        menubar.add_cascade(label="Edit", menu=tk.Menu(menubar, tearoff=0))
        menubar.add_cascade(label="View", menu=tk.Menu(menubar, tearoff=0))
        menubar.add_cascade(label="Layout", menu=tk.Menu(menubar, tearoff=0))
        menubar.add_cascade(label="Operations", menu=tk.Menu(menubar, tearoff=0))

        window_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Window", menu=window_menu)

        menubar.add_cascade(label="Help", menu=tk.Menu(menubar, tearoff=0))

        self.root.config(menu=menubar)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        outer = ttk.Frame(self.root, padding=6)
        outer.pack(fill="both", expand=True)

        self._build_toolbar_host(outer)
        self._build_main_body(outer)
        self._build_status_bar(outer)

    # ------------------------------------------------------------------
    # Toolbars
    # ------------------------------------------------------------------

    def _build_toolbar_host(self, parent: ttk.Frame) -> None:
        self.toolbar_host = ttk.Frame(parent, style="Studio.Toolbar.TFrame")
        self.toolbar_host.pack(fill="x", expand=False, pady=(0, 6))

        self.main_toolbar_row = ttk.Frame(self.toolbar_host)
        self.main_toolbar_row.pack(fill="x", expand=False)

        self._build_layout_tools_group(self.main_toolbar_row)
        self._add_toolbar_separator(self.main_toolbar_row)

        self._build_trackwork_group(self.main_toolbar_row)
        self._add_toolbar_separator(self.main_toolbar_row)

        self._build_view_controls_group(self.main_toolbar_row)

    def _build_layout_tools_group(self, parent: ttk.Frame) -> None:
        group = ttk.Frame(parent)
        group.pack(side="left", padx=(0, 8))

        ttk.Label(
            group,
            text="Layout Tools",
            style="Studio.Section.TLabel",
        ).pack(side="left", padx=(0, 8))

        for label in ("Select", "Move", "Rotate", "Delete"):
            ttk.Button(
                group,
                text=label,
                style="Studio.Toolbar.TButton",
            ).pack(side="left", padx=(0, 3))

    def _build_trackwork_group(self, parent: ttk.Frame) -> None:
        group = ttk.Frame(parent)
        group.pack(side="left", padx=(0, 8))

        ttk.Label(
            group,
            text="Trackwork",
            style="Studio.Section.TLabel",
        ).pack(side="left", padx=(0, 8))

        ttk.Label(
            group,
            text="Element:",
            style="Studio.Toolbar.TLabel",
        ).pack(side="left", padx=(0, 4))

        ttk.Combobox(
            group,
            textvariable=self.trackwork_element_var,
            state="readonly",
            width=14,
            values=("Track", "Turnout", "Curve", "Wye", "Turntable", "Bumper"),
            font=("Arial", 8),
        ).pack(side="left", padx=(0, 4))

        for label in ("Add", "Delete", "Select All"):
            ttk.Button(
                group,
                text=label,
                style="Studio.Toolbar.TButton",
            ).pack(side="left", padx=(0, 3))

    def _build_view_controls_group(self, parent: ttk.Frame) -> None:
        group = ttk.Frame(parent)
        group.pack(side="left", padx=(0, 8))

        ttk.Label(
            group,
            text="View Controls",
            style="Studio.Section.TLabel",
        ).pack(side="left", padx=(0, 8))

        for label in ("Zoom In", "Zoom Out", "Reset"):
            ttk.Button(
                group,
                text=label,
                style="Studio.Toolbar.TButton",
            ).pack(side="left", padx=(0, 3))

        tk.Checkbutton(
            group,
            text="Grid",
            variable=self.show_grid_var,
            onvalue=True,
            offvalue=False,
            font=("Arial", 8),
            padx=2,
            pady=0,
            borderwidth=0,
            highlightthickness=0,
        ).pack(side="left", padx=(0, 4))

        tk.Checkbutton(
            group,
            text="Snap",
            variable=self.show_snap_var,
            onvalue=True,
            offvalue=False,
            font=("Arial", 8),
            padx=2,
            pady=0,
            borderwidth=0,
            highlightthickness=0,
        ).pack(side="left", padx=(0, 4))

        tk.Checkbutton(
            group,
            text="Labels",
            variable=self.show_labels_var,
            onvalue=True,
            offvalue=False,
            font=("Arial", 8),
            padx=2,
            pady=0,
            borderwidth=0,
            highlightthickness=0,
        ).pack(side="left", padx=(0, 4))

        tk.Checkbutton(
            group,
            text="Rulers",
            variable=self.show_rulers_var,
            onvalue=True,
            offvalue=False,
            font=("Arial", 8),
            padx=2,
            pady=0,
            borderwidth=0,
            highlightthickness=0,
        ).pack(side="left", padx=(0, 4))

    def _add_toolbar_separator(self, parent: ttk.Frame) -> None:
        separator = ttk.Separator(parent, orient="vertical")
        separator.pack(side="left", fill="y", padx=(0, 8), pady=2)

    # ------------------------------------------------------------------
    # Main Body
    # ------------------------------------------------------------------
    def _build_main_body(self, parent: ttk.Frame) -> None:
        self.main_pane = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        self.main_pane.pack(fill="both", expand=True)

        self.workspace_host = ttk.Frame(self.main_pane)
        self.panel_host = ttk.Frame(self.main_pane)

        # 2/3 vs 1/3 split
        self.main_pane.add(self.workspace_host, weight=2)
        self.main_pane.add(self.panel_host, weight=1)

        self._build_workspace(self.workspace_host)
        self._build_panel_tabs(self.panel_host)

    def _set_initial_main_pane_sash(self) -> None:
        """
        Force the initial horizontal split to open at roughly:
        - 2/3 workspace
        - 1/3 panels

        ttk.PanedWindow weights help with resize behavior, but they do not
        reliably control the initial sash position at startup.
        """
        try:
            self.root.update_idletasks()

            total_width = self.main_pane.winfo_width()
            if total_width <= 1:
                return

            sash_x = int(total_width * (2.0 / 3.0))
            self.main_pane.sashpos(0, sash_x)
        except tk.TclError:
            pass

    def _build_workspace(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Workspace", padding=8)
        frame.pack(fill="both", expand=True)

        self.design_canvas = DesignCanvas(
            frame,
            on_mouse_move=self._on_workspace_mouse_move,
            on_status_message=self._on_workspace_status_message,
        )
        self.design_canvas.pack(fill="both", expand=True)

    def _on_workspace_status_message(self, message: str) -> None:
        self.status_var.set(message)

    def _on_workspace_mouse_move(
        self,
        world_x: float | None,
        world_y: float | None,
    ) -> None:
        if world_x is None or world_y is None:
            self.cursor_pos_var.set("X: —  Y: —")
            return

        self.cursor_pos_var.set(f"X: {world_x:0.1f}  Y: {world_y:0.1f}")

    def _build_panel_tabs(self, parent: ttk.Frame) -> None:
        notebook = ttk.Notebook(parent)
        notebook.pack(fill="both", expand=True)

        # Inspector Tab
        inspector_tab = ttk.Frame(notebook)
        notebook.add(inspector_tab, text="Inspector")

        inspector = InspectorPanel(inspector_tab)
        inspector.pack(fill="both", expand=True)

        # Operations Tab
        operations_tab = ttk.Frame(notebook)
        notebook.add(operations_tab, text="Operations")

        ttk.Label(operations_tab, text="Operations panel placeholder").pack(pady=20)

    def _sync_view_state(self) -> None:
        # Update status text
        self.grid_status_var.set(
            "Grid: On" if self.show_grid_var.get() else "Grid: Off"
        )
        self.snap_status_var.set(
            "Snap: On" if self.show_snap_var.get() else "Snap: Off"
        )
        self.rulers_status_var.set(
            "Rulers: On" if self.show_rulers_var.get() else "Rulers: Off"
        )

        # Push state into canvas
        if hasattr(self, "design_canvas"):
            self.design_canvas.set_show_grid(self.show_grid_var.get())
            self.design_canvas.set_show_snap(self.show_snap_var.get())
            self.design_canvas.set_show_rulers(self.show_rulers_var.get())

    def _sync_trackwork_state(self) -> None:
        if hasattr(self, "design_canvas"):
            self.design_canvas.set_trackwork_element(self.trackwork_element_var.get())

    # ------------------------------------------------------------------
    # Status Bar
    # ------------------------------------------------------------------
    def _build_status_bar(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=(6, 0))

        ttk.Separator(frame).pack(fill="x", pady=(0, 4))

        row = ttk.Frame(frame)
        row.pack(fill="x")

        ttk.Label(row, textvariable=self.status_var).pack(
            side="left", fill="x", expand=True
        )

        ttk.Label(row, textvariable=self.cursor_pos_var).pack(side="right", padx=8)

        ttk.Label(row, text="Zoom: 100%").pack(side="right", padx=8)
        ttk.Label(row, textvariable=self.snap_status_var).pack(side="right", padx=8)
        ttk.Label(row, textvariable=self.grid_status_var).pack(side="right", padx=8)
        ttk.Label(row, textvariable=self.rulers_status_var).pack(side="right", padx=8)


def main() -> None:
    root = tk.Tk()
    RailroadStudioApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
