from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
import datetime
import math
import time
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import Misc, messagebox, simpledialog, ttk
from typing import Optional
from uuid import uuid4

from railroad_sim.domain.enums import TrackTrafficRule, TrackType

# -----------------------------------------------------------------------------
# Designer-side models
# -----------------------------------------------------------------------------


@dataclass(slots=True)
class EndpointState:
    x: float
    y: float
    connected_to_track_id: str | None = None
    connected_to_endpoint_name: str | None = None


@dataclass(slots=True)
class StraightTrackElement:
    """Designer-side straight track segment.

    This remains intentionally editor-focused. It is not a replacement for the
    existing domain Track object. It stores the geometry needed to author and
    render a track segment, while the inspector exposes the infrastructure data
    the future layout/session pipeline will care about.
    """

    track_id: str
    name: str
    track_type: TrackType
    x1: float
    y1: float
    x2: float
    y2: float
    length_ft: float = 100.0
    traffic_rule: TrackTrafficRule = TrackTrafficRule.BIDIRECTIONAL
    condition: str = "clear"
    elevation_start_ft: float = 0.0
    elevation_end_ft: float = 0.0
    endpoint_a: EndpointState = field(init=False)
    endpoint_b: EndpointState = field(init=False)

    def __post_init__(self) -> None:
        self.endpoint_a = EndpointState(self.x1, self.y1)
        self.endpoint_b = EndpointState(self.x2, self.y2)

    def sync_endpoints_from_geometry(self) -> None:
        self.endpoint_a.x = self.x1
        self.endpoint_a.y = self.y1
        self.endpoint_b.x = self.x2
        self.endpoint_b.y = self.y2

    @property
    def pixel_length(self) -> float:
        return math.hypot(self.x2 - self.x1, self.y2 - self.y1)

    @property
    def angle_deg(self) -> float:
        return math.degrees(math.atan2(self.y2 - self.y1, self.x2 - self.x1))

    @property
    def midpoint(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)

    @property
    def grade_percent(self) -> float:
        if self.length_ft <= 0:
            return 0.0
        return (
            (self.elevation_end_ft - self.elevation_start_ft) / self.length_ft
        ) * 100.0

    def endpoint(self, name: str) -> EndpointState:
        if name == "A":
            return self.endpoint_a
        if name == "B":
            return self.endpoint_b
        raise ValueError(f"Unknown endpoint name: {name}")

    def set_endpoint(self, name: str, x: float, y: float) -> None:
        if name == "A":
            self.x1 = x
            self.y1 = y
        elif name == "B":
            self.x2 = x
            self.y2 = y
        else:
            raise ValueError(f"Unknown endpoint name: {name}")

        self.sync_endpoints_from_geometry()
        self.sync_length_from_geometry()

    def sync_length_from_geometry(self) -> None:
        self.length_ft = self.pixel_length * (100.0 / 140.0)

    def move_by(self, dx: float, dy: float) -> None:
        self.x1 += dx
        self.y1 += dy
        self.x2 += dx
        self.y2 += dy
        self.sync_endpoints_from_geometry()


@dataclass
class TurnoutEndpoint:
    """
    Represents one connection point on a turnout
    Roles:
        trunk:      - entry/exit of the main route
        straight    - continuation of the trunk
        diverging   - branch route
    """

    role: str  # "trunk" | "straight" | "diverging"
    x: float
    y: float

    connected_to_track_id: Optional[str] = None
    connected_to_endpoint_name: Optional[str] = None


@dataclass
class TurnoutTrackElement:
    """
    UI/presentation-layer turnout element

    This is not a domain turnout yet.
    It exists only for layout authoring.
    """

    name: str
    hand: str  # "left" | "right"
    clearance_length_ft: float

    # Anchor position
    x: float
    y: float

    # Base direction of the turnout
    angle_deg: float

    # Geometry parameters
    common_len: float = 28.0
    straight_len: float = 100.0
    diverge_len: float = 84.0
    diverge_angle_deg: float = 14.0

    track_id: str = field(default_factory=lambda: str(uuid4()))

    trunk: TurnoutEndpoint = field(init=False)
    straight: TurnoutEndpoint = field(init=False)
    diverging: TurnoutEndpoint = field(init=False)

    split_x: float = field(init=False)
    split_y: float = field(init=False)

    def __post_init__(self) -> None:
        self.trunk = TurnoutEndpoint(
            role="trunk",
            x=self.x,
            y=self.y,
        )
        self.straight = TurnoutEndpoint(
            role="straight",
            x=self.x,
            y=self.y,
        )
        self.diverging = TurnoutEndpoint(
            role="diverging",
            x=self.x,
            y=self.y,
        )
        self.recalculate_geometry_from_parameters()

    def recalculate_geometry_from_parameters(self) -> None:
        signed_diverge_angle = (
            abs(self.diverge_angle_deg)
            if self.hand == "right"
            else -abs(self.diverge_angle_deg)
        )

        self.trunk.x = self.x
        self.trunk.y = self.y

        heading_rad = math.radians(self.angle_deg)

        self.split_x = self.x + self.common_len * math.cos(heading_rad)
        self.split_y = self.y + self.common_len * math.sin(heading_rad)

        self.straight.x = self.x + self.straight_len * math.cos(heading_rad)
        self.straight.y = self.y + self.straight_len * math.sin(heading_rad)

        diverge_heading_rad = math.radians(self.angle_deg + signed_diverge_angle)
        self.diverging.x = self.split_x + self.diverge_len * math.cos(
            diverge_heading_rad
        )
        self.diverging.y = self.split_y + self.diverge_len * math.sin(
            diverge_heading_rad
        )

    def endpoints(self) -> dict[str, TurnoutEndpoint]:
        return {
            "trunk": self.trunk,
            "straight": self.straight,
            "diverging": self.diverging,
        }


# -----------------------------------------------------------------------------
# Tooltip helper
# -----------------------------------------------------------------------------


class Tooltip:
    def __init__(self, widget: Misc) -> None:
        self.widget = widget
        self.tipwindow: tk.Toplevel | None = None

    def show(self, x: int, y: int, text: str) -> None:
        self.hide()
        self.tipwindow = tk.Toplevel(self.widget)
        self.tipwindow.wm_overrideredirect(True)
        self.tipwindow.wm_geometry(f"+{x + 14}+{y + 14}")

        frame = ttk.Frame(self.tipwindow, padding=6, relief="solid", borderwidth=1)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=text, justify="left", wraplength=280).pack(
            fill="both", expand=True
        )

    def hide(self) -> None:
        if self.tipwindow is not None:
            self.tipwindow.destroy()
            self.tipwindow = None


# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------


class LayoutDesignerApp:
    DEBUG_SNAP = False
    GRID_SPACING = 20
    ZOOM_MIN = 0.35
    ZOOM_MAX = 3.0
    ZOOM_STEP = 1.1

    TRACK_GAUGE_PX = 8.0
    RAIL_WIDTH_PX = 2.0
    ENDPOINT_BOX_SIZE_PX = 8.0
    ENDPOINT_HIT_RADIUS_PX = 10.0
    SNAP_PREVIEW_RADIUS_PX = 12.0
    SNAP_COMMIT_RADIUS_PX = 8.0
    SNAP_DWELL_SECONDS = 0.18
    ANGLE_COMPATIBILITY_DEG = 30.0

    TURNOUT_ROTATE_HANDLE_OFFSET_PX = 26.0
    TURNOUT_ROTATE_HANDLE_RADIUS_PX = 8.0

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Layout Designer")
        self.root.geometry("1500x960")
        self.root.minsize(1180, 760)
        self.name_entry_var = tk.StringVar(value="")
        self.track_type_var = tk.StringVar(value=TrackType.MAINLINE.value)
        self.traffic_rule_var = tk.StringVar(value=TrackTrafficRule.BIDIRECTIONAL.value)
        self._turnout_hand_var = tk.StringVar(value="right")
        self._turnout_clearance_var = tk.StringVar(value="150.0")
        self._turnout_diverge_angle_var = tk.StringVar(value="14.0")
        self._turnout_straight_len_var = tk.StringVar(value="100.0")

        self.selected_tool = tk.StringVar(value="select")
        self.selected_tool.trace_add("write", self._on_tool_changed)
        self.show_grid = tk.BooleanVar(value=True)
        self.snap_to_grid = tk.BooleanVar(value=True)
        self.show_endpoints = tk.BooleanVar(value=True)
        self.show_topology_overlay = tk.BooleanVar(value=False)
        self.show_labels = tk.BooleanVar(value=True)

        self.zoom_scale = 1.0

        self.tracks: dict[str, StraightTrackElement] = {}
        self.track_order: list[str] = []
        self.turnouts: dict[str, TurnoutTrackElement] = {}  # what objects exist?
        self.turnout_order: list[
            str
        ] = []  # what is the draw and interaction order is for the canvas?

        self.selected_track_id: str | None = None
        self.selected_turnout_id: str | None = None
        self.selected_track_ids: set[str] = set()
        self.selected_turnout_ids: set[str] = set()

        self._marquee_start_world: tuple[float, float] | None = None
        self._marquee_end_world: tuple[float, float] | None = None

        self._group_drag_track_ids: set[str] = set()
        self._group_drag_turnout_ids: set[str] = set()
        self._group_smart_move_active = False

        self._group_snap_candidate: tuple[str, str] | None = None
        self._group_snap_preview_point: tuple[float, float] | None = None
        self._group_snap_active_endpoint: tuple[str, str] | None = None

        self.tooltip = Tooltip(root)
        self._tooltip_after_id: str | None = None

        self._drag_mode: str | None = None
        self._drag_track_id: str | None = None
        self._drag_endpoint_name: str | None = None
        self._drag_last_world: tuple[float, float] | None = None
        self._create_track_id: str | None = None
        self._create_anchor_endpoint_name = "A"

        self._hover_track_id: str | None = None
        self._hover_endpoint_name: str | None = None
        self._rotate_turnout_id: str | None = None
        self._rotate_pivot_world: tuple[float, float] | None = None
        self._rotate_start_mouse_angle_deg: float | None = None
        self._rotate_start_turnout_angle_deg: float | None = None

        self._snap_candidate: tuple[str, str] | None = None
        self._snap_candidate_since: float | None = None
        self._snap_locked: tuple[str, str] | None = None
        self._snap_preview_point: tuple[float, float] | None = None

        # ----------------------------------------------------------
        # Group rotation state (Step 4.5 - state only)
        # ----------------------------------------------------------
        self._group_rotate_active: bool = False
        self._group_rotate_pivot: tuple[float, float] | None = None

        # Frozen geometry at rotation start
        self._group_rotate_track_snapshot: dict[
            str, tuple[float, float, float, float]
        ] = {}
        self._group_rotate_turnout_snapshot: dict[
            str, tuple[float, float, float, float, float]
        ] = {}

        debug_dir = Path(__file__).resolve().parent / "debug_output"
        debug_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._debug_log_path = debug_dir / f"layout_debug_{timestamp}.txt"

        self._build_style()
        self._build_menu()
        self._build_ui()
        self._build_canvas_context_menu()

        self._bind_keys()
        self._refresh_canvas()

        # temporary inspector smoke test
        if self.DEBUG_SNAP:
            demo_turnout = TurnoutTrackElement(
                name="Turnout 1",
                hand="right",
                clearance_length_ft=150.0,
                x=200.0,
                y=200.0,
                angle_deg=0.0,
            )
            self._update_turnout_inspector(demo_turnout)

        self._set_status("Ready. Select Track and drag to place a new segment.")

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------
    def _build_style(self) -> None:
        style = ttk.Style()
        style.configure("InspectorHeader.TLabel", font=("Arial", 10, "bold"))
        style.configure("Palette.TRadiobutton", padding=(5, 3))

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New Layout", command=self._new_layout)
        file_menu.add_command(label="Open Layout...", command=self._not_implemented)
        file_menu.add_command(label="Save Layout", command=self._not_implemented)
        file_menu.add_command(
            label="Import Layout Module...", command=self._not_implemented
        )
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.destroy)
        menubar.add_cascade(label="File", menu=file_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_checkbutton(
            label="Show Grid", variable=self.show_grid, command=self._refresh_canvas
        )
        view_menu.add_checkbutton(
            label="Show Endpoints",
            variable=self.show_endpoints,
            command=self._refresh_canvas,
        )
        view_menu.add_checkbutton(
            label="Show Labels",
            variable=self.show_labels,
            command=self._refresh_canvas,
        )
        view_menu.add_checkbutton(
            label="Show Topology Overlay",
            variable=self.show_topology_overlay,
            command=self._refresh_canvas,
        )
        view_menu.add_checkbutton(label="Snap to Grid", variable=self.snap_to_grid)
        view_menu.add_separator()
        view_menu.add_command(
            label="Zoom In",
            command=lambda: self._zoom_at_canvas_center(1.0 / self.ZOOM_STEP),
        )
        view_menu.add_command(
            label="Zoom Out",
            command=lambda: self._zoom_at_canvas_center(self.ZOOM_STEP),
        )
        view_menu.add_command(label="Reset Zoom", command=self._reset_zoom)
        menubar.add_cascade(label="View", menu=view_menu)

        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_radiobutton(
            label="Select", variable=self.selected_tool, value="select"
        )
        tools_menu.add_radiobutton(
            label="Track", variable=self.selected_tool, value="track"
        )
        tools_menu.add_radiobutton(
            label="Turnout", variable=self.selected_tool, value="turnout"
        )

        tools_menu.add_separator()
        tools_menu.add_command(label="Validate Layout", command=self._validate_layout)
        menubar.add_cascade(label="Tools", menu=tools_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Delete Selected", command=self._delete_selected)
        menubar.add_cascade(label="Edit", menu=edit_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    def _build_canvas_context_menu(self) -> None:
        self.canvas_context_menu = tk.Menu(self.root, tearoff=0)

        # ----------------------------------------------------------
        # Rotate submenu
        # ----------------------------------------------------------
        self.rotate_submenu = tk.Menu(self.canvas_context_menu, tearoff=0)

        for deg in (15, 30, 45, 90, 180, 270):
            self.rotate_submenu.add_command(
                label=f"Rotate +{deg}°",
                command=lambda d=deg: self._on_rotate_command(d),
            )

        self.rotate_submenu.add_separator()

        self.rotate_submenu.add_command(
            label="Specify degree...",
            command=self._on_rotate_specify,
        )

        self.canvas_context_menu.add_cascade(
            label="Rotate",
            menu=self.rotate_submenu,
        )

        self.canvas_context_menu.add_separator()

        self.canvas_context_menu.add_command(
            label="Validate",
            command=self._validate_layout,
        )

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=6)
        outer.pack(fill="both", expand=True)

        self._build_palette(outer)

        self.main_pane = ttk.PanedWindow(outer, orient=tk.HORIZONTAL)
        self.main_pane.pack(fill="both", expand=True)

        left = ttk.Frame(self.main_pane, padding=(0, 6, 6, 6))
        right = ttk.Frame(self.main_pane, padding=(6, 6, 0, 6), width=340)
        self.main_pane.add(left, weight=5)
        self.main_pane.add(right, weight=2)

        self._build_canvas_panel(left)
        self._build_inspector(right)
        self._build_status_bar(outer)

    def _build_palette(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Tool Palette", padding=6)
        frame.pack(fill="x", expand=False)

        tools = (("Select", "select"), ("Track", "track"), ("Turnout", "turnout"))
        for idx, (label, value) in enumerate(tools):
            ttk.Radiobutton(
                frame,
                text=label,
                variable=self.selected_tool,
                value=value,
                style="Palette.TRadiobutton",
            ).grid(row=0, column=idx, padx=(0, 10), sticky="w")

        ttk.Checkbutton(
            frame, text="Grid", variable=self.show_grid, command=self._refresh_canvas
        ).grid(row=0, column=3, padx=(18, 8), sticky="w")
        ttk.Checkbutton(
            frame,
            text="Endpoints",
            variable=self.show_endpoints,
            command=self._refresh_canvas,
        ).grid(row=0, column=4, padx=(0, 8), sticky="w")
        ttk.Checkbutton(
            frame,
            text="Labels",
            variable=self.show_labels,
            command=self._refresh_canvas,
        ).grid(row=0, column=5, padx=(0, 8), sticky="w")

        ttk.Checkbutton(
            frame,
            text="Topology",
            variable=self.show_topology_overlay,
            command=self._refresh_canvas,
        ).grid(row=0, column=6, padx=(0, 8), sticky="w")
        ttk.Checkbutton(frame, text="Snap Grid", variable=self.snap_to_grid).grid(
            row=0, column=7, padx=(0, 8), sticky="w"
        )

        ttk.Label(
            frame,
            text="Place: select Track, press-drag-release. Edit: drag body to move, Ctrl+drag endpoint to reshape.",
        ).grid(row=1, column=0, columnspan=8, sticky="w", pady=(8, 0))

    def _build_canvas_panel(self, parent: ttk.Frame) -> None:
        container = ttk.LabelFrame(parent, text="Design Board", padding=4)
        container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(
            container,
            background="white",
            highlightthickness=1,
            highlightbackground="#b8b8b8",
            scrollregion=(0, 0, 4000, 2600),
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        h_scroll = ttk.Scrollbar(
            container, orient="horizontal", command=self.canvas.xview
        )
        v_scroll = ttk.Scrollbar(
            container, orient="vertical", command=self.canvas.yview
        )
        self.canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)

        h_scroll.grid(row=1, column=0, sticky="ew")
        v_scroll.grid(row=0, column=1, sticky="ns")

        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        self.canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<Motion>", self._on_canvas_motion)
        self.canvas.bind("<Leave>", self._on_canvas_leave)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel_zoom)
        self.canvas.bind("<Button-3>", self._on_canvas_right_click)

    def _build_inspector(self, parent: ttk.Frame) -> None:
        panel = ttk.LabelFrame(parent, text="Inspector", padding=10)
        panel.pack(fill="both", expand=True)

        self.inspector_header = ttk.Label(
            panel, text="No Selection", style="InspectorHeader.TLabel"
        )
        self.inspector_header.pack(anchor="w", pady=(0, 10))

        self.track_fields_frame = ttk.Frame(panel)
        self.track_fields_frame.pack(fill="x", expand=False)

        self.turnout_field_frame = ttk.Frame(panel)
        self.turnout_field_frame.pack(fill="x", expand=False)
        self.turnout_field_frame.pack_forget()

        # Name
        name_row = ttk.Frame(self.track_fields_frame)
        name_row.pack(fill="x", expand=False, pady=(0, 10))
        ttk.Label(name_row, text="Name:").pack(side="left")
        self.name_entry = ttk.Entry(
            name_row,
            textvariable=self.name_entry_var,
            width=28,
        )
        self.name_entry.pack(side="left", fill="x", expand=True, padx=(6, 6))
        self.name_entry.bind("<Return>", self._on_name_entry_return)
        ttk.Button(
            name_row,
            text="Apply",
            command=self._apply_track_name,
        ).pack(side="left")

        # Track Type
        type_row = ttk.Frame(self.track_fields_frame)
        type_row.pack(fill="x", expand=False, pady=(0, 10))
        ttk.Label(type_row, text="Track Type:").pack(side="left")
        self.track_type_combo = ttk.Combobox(
            type_row,
            textvariable=self.track_type_var,
            state="readonly",
            width=18,
            values=[t.value for t in TrackType],
        )
        self.track_type_combo.pack(side="left", fill="x", expand=True, padx=(6, 6))
        self.track_type_combo.bind("<<ComboboxSelected>>", self._on_track_type_selected)
        ttk.Button(
            type_row,
            text="Apply",
            command=self._apply_track_type,
        ).pack(side="left")

        # Traffic Rule
        rule_row = ttk.Frame(self.track_fields_frame)
        rule_row.pack(fill="x", expand=False, pady=(0, 10))
        ttk.Label(rule_row, text="Traffic Rule:").pack(side="left")
        self.traffic_rule_combo = ttk.Combobox(
            rule_row,
            textvariable=self.traffic_rule_var,
            state="readonly",
            width=18,
            values=[rule.value for rule in TrackTrafficRule],
        )
        self.traffic_rule_combo.pack(side="left", fill="x", expand=True, padx=(6, 6))
        self.traffic_rule_combo.bind(
            "<<ComboboxSelected>>",
            self._on_traffic_rule_selected,
        )
        ttk.Button(
            rule_row,
            text="Apply",
            command=self._apply_traffic_rule,
        ).pack(side="left")

        # Turnout Hand
        turnout_hand_row = ttk.Frame(self.turnout_field_frame)
        turnout_hand_row.pack(fill="x", expand=False, pady=(0, 10))
        ttk.Label(turnout_hand_row, text="Turnout Hand:").pack(side="left")
        self.turnout_hand_combo = ttk.Combobox(
            turnout_hand_row,
            textvariable=self._turnout_hand_var,
            state="readonly",
            width=18,
            values=["left", "right"],
        )
        self.turnout_hand_combo.pack(side="left", fill="x", expand=True, padx=(6, 6))
        ttk.Button(
            turnout_hand_row,
            text="Apply",
            command=self._apply_turnout_hand,
        ).pack(side="left")

        ###############################################################
        # TURNOUT MANIPULATION
        ###############################################################

        # Turnout Clearance
        turnout_clearance_row = ttk.Frame(self.turnout_field_frame)
        turnout_clearance_row.pack(fill="x", expand=False, pady=(0, 10))
        ttk.Label(turnout_clearance_row, text="Clearance (ft):").pack(side="left")
        self.turnout_clearance_entry = ttk.Entry(
            turnout_clearance_row,
            textvariable=self._turnout_clearance_var,
            width=18,
        )
        self.turnout_clearance_entry.pack(
            side="left", fill="x", expand=True, padx=(6, 6)
        )
        ttk.Button(
            turnout_clearance_row,
            text="Apply",
            command=self._apply_turnout_clearance,
        ).pack(side="left")

        # Turnout Diverge Angle
        turnout_diverge_angle_row = ttk.Frame(self.turnout_field_frame)
        turnout_diverge_angle_row.pack(fill="x", expand=False, pady=(0, 10))
        ttk.Label(turnout_diverge_angle_row, text="Diverge Angle (deg):").pack(
            side="left"
        )
        self.turnout_diverge_angle_entry = ttk.Entry(
            turnout_diverge_angle_row,
            textvariable=self._turnout_diverge_angle_var,
            width=18,
        )
        self.turnout_diverge_angle_entry.pack(
            side="left", fill="x", expand=True, padx=(6, 6)
        )
        ttk.Button(
            turnout_diverge_angle_row,
            text="Apply",
            command=self._apply_turnout_diverge_angle,
        ).pack(side="left")

        # Turnout Straight Length
        turnout_straight_len_row = ttk.Frame(self.turnout_field_frame)
        turnout_straight_len_row.pack(fill="x", expand=False, pady=(0, 10))
        ttk.Label(turnout_straight_len_row, text="Straight Length (ft):").pack(
            side="left"
        )
        self.turnout_straight_len_entry = ttk.Entry(
            turnout_straight_len_row,
            textvariable=self._turnout_straight_len_var,
            width=18,
        )
        self.turnout_straight_len_entry.pack(
            side="left", fill="x", expand=True, padx=(6, 6)
        )
        ttk.Button(
            turnout_straight_len_row,
            text="Apply",
            command=self._apply_turnout_straight_len,
        ).pack(side="left")

        self.inspector_body = tk.Text(
            panel,
            width=42,
            height=28,
            wrap="word",
            state="disabled",
            font=("Arial", 10),
        )
        self.inspector_body.pack(fill="both", expand=True)

        ttk.Label(
            panel,
            text=(
                "Track V2 notes:\n"
                "• Drag body to move a track.\n"
                "• Ctrl+drag an endpoint box to reshape it.\n"
                "• Endpoints show outline when open, filled when connected.\n"
                "• Snap preview appears near a valid endpoint target."
            ),
            justify="left",
        ).pack(anchor="w", pady=(10, 0))

    def _on_tool_changed(self, *_) -> None:
        tool = self.selected_tool.get()

        if tool == "turnout":
            self._update_turnout_inspector(None)
        else:
            self._update_inspector(None)

    def _apply_track_name(self) -> None:
        if self.selected_track_id is None:
            return

        new_name = self.name_entry_var.get().strip()
        if not new_name:
            self._set_status("Track name must not be blank.")
            return

        track = self.tracks[self.selected_track_id]
        track.name = new_name
        self._update_inspector(track)
        self._refresh_canvas()
        self._set_status(f"Renamed track to {track.name}")

    def _apply_track_type(self) -> None:
        if self.selected_track_id is None:
            return

        new_type = self.track_type_var.get().strip()
        if not new_type:
            self._set_status("Track type must not be blank.")
            return

        track = self.tracks[self.selected_track_id]
        track.track_type = TrackType(new_type)
        self._update_inspector(track)
        self._refresh_canvas()
        self._set_status(f"Updated track type to: {track.track_type.value}.")

    def _apply_traffic_rule(self) -> None:
        if self.selected_track_id is None:
            return

        new_rule = self.traffic_rule_var.get().strip()
        if not new_rule:
            self._set_status("Traffic rule must not be blank.")
            return

        track = self.tracks[self.selected_track_id]
        track.traffic_rule = TrackTrafficRule(new_rule)
        self._update_inspector(track)
        self._refresh_canvas()
        self._set_status(f"Updated traffic rule to: {track.traffic_rule.value}.")

    def _apply_turnout_hand(self) -> None:
        if self.selected_turnout_id is None:
            return

        turnout = self.turnouts[self.selected_turnout_id]
        new_hand = self._turnout_hand_var.get().strip().lower()

        if new_hand not in {"left", "right"}:
            self._set_status("Turnout hand must be 'left' or 'right'.")
            return

        if turnout.hand == new_hand:
            self._set_status(f"Turnout hand already set to {turnout.hand}.")
            return

        turnout.hand = new_hand
        turnout.recalculate_geometry_from_parameters()
        self._update_turnout_inspector(turnout)
        self._refresh_canvas()
        self._set_status(f"Updated turnout hand to {turnout.hand}.")

    def _apply_turnout_clearance(self) -> None:
        self._set_status("Turnout clearance editing is not implemented yet.")

    def _apply_turnout_diverge_angle(self) -> None:
        if self.selected_turnout_id is None:
            return

        turnout = self.turnouts[self.selected_turnout_id]

        try:
            new_angle = float(self._turnout_diverge_angle_var.get().strip())
        except ValueError:
            self._set_status("Diverge angle must be a number.")
            return

        if new_angle < 2.0:
            self._set_status("Diverge angle must be at least 2.0 degrees.")
            return

        turnout.diverge_angle_deg = new_angle
        turnout.recalculate_geometry_from_parameters()
        self._update_turnout_inspector(turnout)
        self._refresh_canvas()
        self._set_status(f"Updated diverge angle to {turnout.diverge_angle_deg:.1f}°.")

    def _apply_turnout_straight_len(self) -> None:
        if self.selected_turnout_id is None:
            return

        turnout = self.turnouts[self.selected_turnout_id]

        try:
            new_length = float(self._turnout_straight_len_var.get().strip())
        except ValueError:
            self._set_status("Straight length must be a number.")
            return

        if new_length < 20.0:
            self._set_status("Straight length must be at least 20.0 ft.")
            return

        turnout.straight_len = new_length
        turnout.recalculate_geometry_from_parameters()
        self._update_turnout_inspector(turnout)
        self._refresh_canvas()
        self._set_status(f"Updated straight length to {turnout.straight_len:.1f} ft.")

    def _on_rotate_command(self, degrees: float) -> None:
        total_selected = len(self.selected_track_ids) + len(self.selected_turnout_ids)
        if total_selected > 1:
            self._begin_group_rotation_state()

            if self._group_rotate_pivot is None:
                self._set_status("Group rotation aborted: no valid pivot.")
                return

            pivot_x, pivot_y = self._group_rotate_pivot
            angle_rad = math.radians(-degrees)
            cos_a = math.cos(angle_rad)
            sin_a = math.sin(angle_rad)

            # ------------------------------------------------------
            # Rotate selected tracks from frozen snapshot geometry
            # ------------------------------------------------------
            for track_id, (x1, y1, x2, y2) in self._group_rotate_track_snapshot.items():
                track = self.tracks.get(track_id)
                if track is None:
                    continue

                dx1 = x1 - pivot_x
                dy1 = y1 - pivot_y
                new_x1 = pivot_x + (dx1 * cos_a) - (dy1 * sin_a)
                new_y1 = pivot_y + (dx1 * sin_a) + (dy1 * cos_a)

                dx2 = x2 - pivot_x
                dy2 = y2 - pivot_y
                new_x2 = pivot_x + (dx2 * cos_a) - (dy2 * sin_a)
                new_y2 = pivot_y + (dx2 * sin_a) + (dy2 * cos_a)

                track.x1 = new_x1
                track.y1 = new_y1
                track.x2 = new_x2
                track.y2 = new_y2
                track.sync_endpoints_from_geometry()
                track.sync_length_from_geometry()

            # ------------------------------------------------------
            # Turnouts intentionally untouched in this step
            # ------------------------------------------------------
            # ------------------------------------------------------
            # Rotate selected turnouts from frozen snapshot geometry
            # ------------------------------------------------------
            for turnout_id, (
                x,
                y,
                angle_deg,
                trunk_x,
                trunk_y,
            ) in self._group_rotate_turnout_snapshot.items():
                turnout = self.turnouts.get(turnout_id)
                if turnout is None:
                    continue

                # ------------------------------------------------------
                # Rotate trunk endpoint around group pivot
                # ------------------------------------------------------
                dx = trunk_x - pivot_x
                dy = trunk_y - pivot_y

                new_trunk_x = pivot_x + (dx * cos_a) - (dy * sin_a)
                new_trunk_y = pivot_y + (dx * sin_a) + (dy * cos_a)

                # ------------------------------------------------------
                # Rotate turnout orientation (match track direction)
                # ------------------------------------------------------
                turnout.angle_deg = angle_deg - degrees
                turnout.angle_deg = (turnout.angle_deg + 180.0) % 360.0 - 180.0

                turnout.recalculate_geometry_from_parameters()

                # ------------------------------------------------------
                # Move turnout so trunk lands exactly on rotated trunk
                # ------------------------------------------------------
                trunk = turnout.endpoints()["trunk"]

                shift_x = new_trunk_x - trunk.x
                shift_y = new_trunk_y - trunk.y

                turnout.x += shift_x
                turnout.y += shift_y

                turnout.recalculate_geometry_from_parameters()

            self._sync_primary_selection_from_group()
            self._refresh_canvas()
            self._set_status(
                f"Rotating selected group by +{degrees}° "
                f"around pivot ({pivot_x:1f}, {pivot_y:1f})."
            )
            return

        if self.selected_track_id is not None:
            track = self.tracks[self.selected_track_id]

            # Clear any existing connections before rotation.
            self._clear_track_connections(track)

            # Current geometry endpoints.
            x1 = track.x1
            y1 = track.y1
            x2 = track.x2
            y2 = track.y2

            # Midpoint pivot.
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0

            # Negative angle so visual rotation feels correct in Tk canvas coords.
            angle_rad = math.radians(-degrees)
            cos_a = math.cos(angle_rad)
            sin_a = math.sin(angle_rad)

            # Rotate endpoint A about midpoint.
            dx1 = x1 - cx
            dy1 = y1 - cy
            new_x1 = cx + (dx1 * cos_a) - (dy1 * sin_a)
            new_y1 = cy + (dx1 * sin_a) + (dy1 * cos_a)

            # Rotate endpoint B about midpoint.
            dx2 = x2 - cx
            dy2 = y2 - cy
            new_x2 = cx + (dx2 * cos_a) - (dy2 * sin_a)
            new_y2 = cy + (dx2 * sin_a) + (dy2 * cos_a)

            # Update the real track geometry used by drawing / hit test / inspector.
            track.x1 = new_x1
            track.y1 = new_y1
            track.x2 = new_x2
            track.y2 = new_y2

            # Keep endpoint objects and derived length in sync.
            track.sync_endpoints_from_geometry()
            track.sync_length_from_geometry()

            self._update_inspector(track)
            self._refresh_canvas()
            self._set_status(f"Rotated {track.name} by +{degrees}°")
            return

        if self.selected_turnout_id is not None:
            turnout = self.turnouts[self.selected_turnout_id]

            # ----------------------------------------------------------
            # Clear existing turnout connections before rotation
            # ----------------------------------------------------------
            for endpoint_name, endpoint in turnout.endpoints().items():
                if endpoint.connected_to_track_id is None:
                    continue

                other_id = endpoint.connected_to_track_id
                other_endpoint_name = endpoint.connected_to_endpoint_name

                endpoint.connected_to_track_id = None
                endpoint.connected_to_endpoint_name = None

                if other_id is not None and other_endpoint_name is not None:
                    other_track = self.tracks.get(other_id)
                    if other_track is not None:
                        other_ep = other_track.endpoint(other_endpoint_name)
                        if other_ep.connected_to_track_id == turnout.track_id:
                            other_ep.connected_to_track_id = None
                            other_ep.connected_to_endpoint_name = None

                    other_turnout = self.turnouts.get(other_id)
                    if other_turnout is not None:
                        other_ep = other_turnout.endpoints()[other_endpoint_name]
                        if other_ep.connected_to_track_id == turnout.track_id:
                            other_ep.connected_to_track_id = None
                            other_ep.connected_to_endpoint_name = None

            # ----------------------------------------------------------
            # Preserve the visual center during menu rotation
            # ----------------------------------------------------------
            old_center_x, old_center_y = self._turnout_center_world(turnout)

            turnout.angle_deg += degrees
            turnout.angle_deg = (turnout.angle_deg + 180.0) % 360.0 - 180.0
            turnout.recalculate_geometry_from_parameters()

            new_center_x, new_center_y = self._turnout_center_world(turnout)

            turnout.x += old_center_x - new_center_x
            turnout.y += old_center_y - new_center_y
            turnout.recalculate_geometry_from_parameters()

            self._update_turnout_inspector(turnout)
            self._refresh_canvas()
            self._set_status(f"Rotated {turnout.name} by +{degrees}°")
            return

    def _on_rotate_specify(self) -> None:
        if self.selected_track_id is None and self.selected_turnout_id is None:
            self._set_status("No object selected for rotation.")
            return

        obj_name = None
        if self.selected_track_id is not None:
            obj_name = self.tracks[self.selected_track_id].name
        elif self.selected_turnout_id is not None:
            obj_name = self.turnouts[self.selected_turnout_id].name

        degrees = simpledialog.askfloat(
            "Specify Rotation",
            f"Rotate {obj_name} by degrees:",
            parent=self.root,
            minvalue=-360.0,
            maxvalue=360.0,
        )

        if degrees is None:
            self._set_status("Rotation canceled.")
            return

        if abs(degrees) < 1e-9:
            self._set_status("Rotation skipped (0°).")
            return

        self._on_rotate_command(degrees)

    def _on_name_entry_return(self, event: tk.Event) -> None:
        self._apply_track_name()
        self.canvas.focus_set()

    def _on_track_type_selected(self, event: tk.Event) -> None:
        self._apply_track_type()

    def _on_traffic_rule_selected(self, event: tk.Event) -> None:
        self._apply_traffic_rule()

    def _build_status_bar(self, parent: ttk.Frame) -> None:
        self.status_var = tk.StringVar(value="")
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill="x", side="bottom", pady=(4, 0))

        ttk.Separator(status_frame, orient="horizontal").pack(fill="x", pady=(0, 3))
        ttk.Label(status_frame, textvariable=self.status_var, anchor="w").pack(fill="x")

    def _bind_keys(self) -> None:
        self.root.bind("<Delete>", self._on_delete_key)
        self.root.bind("<Up>", lambda _e: self._nudge_selected(0, -1))
        self.root.bind("<Down>", lambda _e: self._nudge_selected(0, 1))
        self.root.bind("<Left>", lambda _e: self._nudge_selected(-1, 0))
        self.root.bind("<Right>", lambda _e: self._nudge_selected(1, 0))
        self.root.bind(
            "<plus>", lambda _e: self._zoom_at_canvas_center(1.0 / self.ZOOM_STEP)
        )
        self.root.bind(
            "<minus>", lambda _e: self._zoom_at_canvas_center(self.ZOOM_STEP)
        )

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def _refresh_canvas(self) -> None:
        self.canvas.delete("all")
        self._draw_grid()

        for track_id in self.track_order:
            self._draw_track(self.tracks[track_id])

        for turnout_id in self.turnout_order:
            self._draw_turnout(self.turnouts[turnout_id])

        if (
            self._marquee_start_world is not None
            and self._marquee_end_world is not None
        ):
            self._draw_marquee_selection_rect()

        if (
            self._group_smart_move_active
            and self._group_snap_preview_point is not None
            and self._group_snap_candidate is not None
        ):
            self._draw_group_smart_snap_preview()

        if self._snap_preview_point is not None and self._snap_candidate is not None:
            self._draw_snap_preview()

    def _draw_grid(self) -> None:
        if not self.show_grid.get():
            return

        spacing = self.GRID_SPACING * self.zoom_scale
        width = 4000 * self.zoom_scale
        height = 2600 * self.zoom_scale

        x = 0.0
        while x <= width:
            self.canvas.create_line(x, 0, x, height, fill="#efefef")
            x += spacing

        y = 0.0
        while y <= height:
            self.canvas.create_line(0, y, width, y, fill="#efefef")
            y += spacing

    def _track_colors_for_type(self, track_type: TrackType) -> tuple[str, str]:
        """
        Return (track_fill, rail_color) for the given track_type.
        Keep these colors fairly subtle so the board stays readable
        """
        color_map = {
            TrackType.MAINLINE: ("#d8d8d8", "#4a4a4a"),
            TrackType.SIDING: ("#e6e6e6", "#777777"),
            TrackType.YARD: ("#e8e1d6", "#7a746b"),
            TrackType.INDUSTRIAL: ("#dde5e8", "#6d7a89"),
            TrackType.STAGING: ("#ececec", "#999999"),
        }

        return color_map.get(track_type, ("#e6e6e6", "#8a8a8a"))

    def _draw_track(self, track: StraightTrackElement) -> None:
        # --------------------------------------------------------------
        # Convert world-space endpoints into screen-space coordinates.
        # World-space is the designer's logical coordinate system.
        # Screen-space is what we actually draw on the Tk canvas.
        # --------------------------------------------------------------
        sx1, sy1 = self._world_to_screen(track.x1, track.y1)
        sx2, sy2 = self._world_to_screen(track.x2, track.y2)

        # --------------------------------------------------------------
        # Compute the centerline vector and its length.
        # If the track has effectively zero visible length, do not draw it.
        # --------------------------------------------------------------
        dx = sx2 - sx1
        dy = sy2 - sy1
        length = math.hypot(dx, dy)
        if length < 1e-6:
            return

        # --------------------------------------------------------------
        # Unit direction along the centerline.
        # ux, uy point from endpoint A toward endpoint B.
        # --------------------------------------------------------------
        ux = dx / length
        uy = dy / length

        # --------------------------------------------------------------
        # If an endpoint is connected, trim the rendered track slightly
        # so that two connected pieces do not visibly stab into each other.
        #
        # IMPORTANT:
        # This is only a rendering trim. It does NOT change the real
        # geometry or the actual endpoint coordinates used for snapping
        # and topology.
        # --------------------------------------------------------------
        render_sx1 = sx1
        render_sy1 = sy1
        render_sx2 = sx2
        render_sy2 = sy2

        # trim_px = 0.5 * self.zoom_scale
        trim_px = 0.0

        if track.endpoint_a.connected_to_track_id is not None:
            render_sx1 += ux * trim_px
            render_sy1 += uy * trim_px

        if track.endpoint_b.connected_to_track_id is not None:
            render_sx2 -= ux * trim_px
            render_sy2 -= uy * trim_px

        # --------------------------------------------------------------
        # Recompute the visible centerline after trimming.
        # This visible centerline is what the rails/body are drawn from.
        # --------------------------------------------------------------
        render_dx = render_sx2 - render_sx1
        render_dy = render_sy2 - render_sy1
        render_length = math.hypot(render_dx, render_dy)
        if render_length < 1e-6:
            return

        # --------------------------------------------------------------
        # Compute a normal (perpendicular) vector to the visible centerline.
        # This lets us offset left/right to draw the two rails.
        # --------------------------------------------------------------
        nx = -render_dy / render_length
        ny = render_dx / render_length

        # --------------------------------------------------------------
        # Visual sizing for the track.
        #
        # TRACK_GAUGE_PX controls the separation between the two rails.
        # RAIL_WIDTH_PX controls the thickness of each rail line.
        # --------------------------------------------------------------
        gauge = self.TRACK_GAUGE_PX * self.zoom_scale
        half_gauge = gauge / 2.0
        rail_width = max(1.0, self.RAIL_WIDTH_PX * self.zoom_scale)

        # --------------------------------------------------------------
        # Compute the left and right rail endpoints from the visible
        # centerline plus/minus the normal vector.
        # --------------------------------------------------------------
        left_x1 = render_sx1 + (nx * half_gauge)
        left_y1 = render_sy1 + (ny * half_gauge)
        left_x2 = render_sx2 + (nx * half_gauge)
        left_y2 = render_sy2 + (ny * half_gauge)

        right_x1 = render_sx1 - (nx * half_gauge)
        right_y1 = render_sy1 - (ny * half_gauge)
        right_x2 = render_sx2 - (nx * half_gauge)
        right_y2 = render_sy2 - (ny * half_gauge)

        # --------------------------------------------------------------
        # Slight taper at connected endpoints to reduce visual collision
        # --------------------------------------------------------------
        taper_factor = 1.0

        if track.endpoint_a.connected_to_track_id is not None:
            mid_x1 = (left_x1 + right_x1) / 2.0
            mid_y1 = (left_y1 + right_y1) / 2.0
            half_dx1 = (left_x1 - right_x1) * 0.5 * taper_factor
            half_dy1 = (left_y1 - right_y1) * 0.5 * taper_factor
            left_x1 = mid_x1 + half_dx1
            left_y1 = mid_y1 + half_dy1
            right_x1 = mid_x1 - half_dx1
            right_y1 = mid_y1 - half_dy1

        if track.endpoint_b.connected_to_track_id is not None:
            mid_x2 = (left_x2 + right_x2) / 2.0
            mid_y2 = (left_y2 + right_y2) / 2.0
            half_dx2 = (left_x2 - right_x2) * 0.5 * taper_factor
            half_dy2 = (left_y2 - right_y2) * 0.5 * taper_factor
            left_x2 = mid_x2 + half_dx2
            left_y2 = mid_y2 + half_dy2
            right_x2 = mid_x2 - half_dx2
            right_y2 = mid_y2 - half_dy2

        # --------------------------------------------------------------
        # Choose fill and rail color based on Track Type
        # --------------------------------------------------------------
        track_fill, rail_color = self._track_colors_for_type(track.track_type)

        if self.show_topology_overlay.get() and (
            track.endpoint_a.connected_to_track_id
            or track.endpoint_b.connected_to_track_id
        ):
            rail_color = "#2c5fb0"

        self.canvas.create_polygon(
            left_x1,
            left_y1,
            left_x2,
            left_y2,
            right_x2,
            right_y2,
            right_x1,
            right_y1,
            fill=track_fill,
            outline="",
        )

        # --------------------------------------------------------------
        # Draw the two rail lines on top of the filled body.
        # --------------------------------------------------------------
        self.canvas.create_line(
            left_x1,
            left_y1,
            left_x2,
            left_y2,
            fill=rail_color,
            width=rail_width,
        )
        self.canvas.create_line(
            right_x1,
            right_y1,
            right_x2,
            right_y2,
            fill=rail_color,
            width=rail_width,
        )

        # --------------------------------------------------------------
        # Draw the track label slightly above the midpoint of the segment.
        # --------------------------------------------------------------
        if self.show_labels.get():
            mx, my = self._world_to_screen(*track.midpoint)
            self.canvas.create_text(
                mx,
                my - (16 * self.zoom_scale),
                text=track.name,
                font=("Arial", max(8, int(10 * self.zoom_scale))),
                fill="navy",
            )

        # --------------------------------------------------------------
        # Draw selection rectangle when this track is selected.
        # This uses the full underlying track bbox, not the trimmed render
        # extents, so selection remains easy and consistent.
        # --------------------------------------------------------------

        is_primary_selected = track.track_id == self.selected_track_id
        is_group_selected = track.track_id in self.selected_track_ids

        if is_primary_selected or is_group_selected:
            bbox = self._track_screen_bbox(track)

            if is_primary_selected:
                outline = "#ff9900"
                width = max(1.0, 2.0 * self.zoom_scale)
                dash = (4, 2)
            else:
                outline = "#2f9e44" if self._group_smart_move_active else "#2f80ed"
                width = max(1.0, 1.5 * self.zoom_scale)
                dash = (8, 4)

            self.canvas.create_rectangle(
                bbox[0] - 8,
                bbox[1] - 8,
                bbox[2] + 8,
                bbox[3] + 8,
                outline=outline,
                width=width,
                dash=dash,
            )

        # --------------------------------------------------------------
        # Draw endpoint handles only when endpoint display is enabled
        # or when the track itself is selected.
        # --------------------------------------------------------------
        if self.show_endpoints.get() or track.track_id == self.selected_track_id:
            self._draw_endpoint(track, "A")
            self._draw_endpoint(track, "B")

        if self.show_topology_overlay.get():
            self._draw_topology_endpoint_overlay(track, "A")
            self._draw_topology_endpoint_overlay(track, "B")

        # --------------------------------------------------------------

        # Draw connection mask (simple seam cleanup)
        # --------------------------------------------------------------
        mask_radius = 3.0 * self.zoom_scale
        track_fill = self._track_colors_for_type(track.track_type)[0]

        for endpoint in (track.endpoint_a, track.endpoint_b):
            if endpoint.connected_to_track_id is not None:
                sx, sy = self._world_to_screen(endpoint.x, endpoint.y)

                self.canvas.create_oval(
                    sx - mask_radius,
                    sy - mask_radius,
                    sx + mask_radius,
                    sy + mask_radius,
                    fill=track_fill,
                    outline="",
                )

    def _draw_turnout(self, turnout: TurnoutTrackElement) -> None:
        split_point = TurnoutEndpoint(
            role="split",
            x=turnout.split_x,
            y=turnout.split_y,
        )

        self._draw_turnout_leg(
            turnout=turnout,
            start=turnout.trunk,
            end=split_point,
            is_diverging=False,
        )
        self._draw_turnout_leg(
            turnout=turnout,
            start=split_point,
            end=turnout.straight,
            is_diverging=False,
        )
        self._draw_turnout_leg(
            turnout=turnout,
            start=split_point,
            end=turnout.diverging,
            is_diverging=True,
        )

        if self.show_labels.get():
            mx = (turnout.trunk.x + turnout.straight.x + turnout.diverging.x) / 3.0
            my = (turnout.trunk.y + turnout.straight.y + turnout.diverging.y) / 3.0
            smx, smy = self._world_to_screen(mx, my)

            self.canvas.create_text(
                smx,
                smy - (24 * self.zoom_scale),
                text=turnout.name,
                font=("Arial", max(8, int(10 * self.zoom_scale))),
                fill="navy",
            )

        is_primary_selected = turnout.track_id == self.selected_turnout_id
        is_group_selected = turnout.track_id in self.selected_turnout_ids

        if is_primary_selected or is_group_selected:
            bbox = self._turnout_screen_bbox(turnout)

            if is_primary_selected:
                outline = "#ff9900"
                width = max(1.0, 2.0 * self.zoom_scale)
                dash = (4, 2)
            else:
                outline = "#2f9e44" if self._group_smart_move_active else "#2f80ed"
                width = max(1.0, 1.5 * self.zoom_scale)
                dash = (8, 4)

            self.canvas.create_rectangle(
                bbox[0] - 8,
                bbox[1] - 8,
                bbox[2] + 8,
                bbox[3] + 8,
                outline=outline,
                width=width,
                dash=dash,
            )

        if is_primary_selected:
            self._draw_turnout_rotate_handle(turnout)

        if self.show_endpoints.get() or turnout.track_id == self.selected_turnout_id:
            self._draw_turnout_endpoint(turnout, "trunk")
            self._draw_turnout_endpoint(turnout, "straight")
            self._draw_turnout_endpoint(turnout, "diverging")

    def _draw_turnout_leg(
        self,
        turnout: TurnoutTrackElement,
        start: TurnoutEndpoint,
        end: TurnoutEndpoint,
        *,
        is_diverging: bool,
    ) -> None:
        sx1, sy1 = self._world_to_screen(start.x, start.y)
        sx2, sy2 = self._world_to_screen(end.x, end.y)

        dx = sx2 - sx1
        dy = sy2 - sy1
        length = math.hypot(dx, dy)
        if length < 1e-6:
            return

        ux = dx / length
        uy = dy / length

        render_sx1 = sx1
        render_sy1 = sy1
        render_sx2 = sx2
        render_sy2 = sy2

        trim_px = 0.5 * self.zoom_scale

        if start.connected_to_track_id is not None:
            render_sx1 += ux * trim_px
            render_sy1 += uy * trim_px

        if end.connected_to_track_id is not None:
            render_sx2 -= ux * trim_px
            render_sy2 -= uy * trim_px

        render_dx = render_sx2 - render_sx1
        render_dy = render_sy2 - render_sy1
        render_length = math.hypot(render_dx, render_dy)
        if render_length < 1e-6:
            return

        nx = -render_dy / render_length
        ny = render_dx / render_length

        gauge = self.TRACK_GAUGE_PX * self.zoom_scale
        half_gauge = gauge / 2.0
        rail_width = max(1.0, self.RAIL_WIDTH_PX * self.zoom_scale)

        left_x1 = render_sx1 + (nx * half_gauge)
        left_y1 = render_sy1 + (ny * half_gauge)
        left_x2 = render_sx2 + (nx * half_gauge)
        left_y2 = render_sy2 + (ny * half_gauge)

        right_x1 = render_sx1 - (nx * half_gauge)
        right_y1 = render_sy1 - (ny * half_gauge)
        right_x2 = render_sx2 - (nx * half_gauge)
        right_y2 = render_sy2 - (ny * half_gauge)

        taper_factor = 0.75

        if start.connected_to_track_id is not None:
            mid_x1 = (left_x1 + right_x1) / 2.0
            mid_y1 = (left_y1 + right_y1) / 2.0
            half_dx1 = (left_x1 - right_x1) * 0.5 * taper_factor
            half_dy1 = (left_y1 - right_y1) * 0.5 * taper_factor
            left_x1 = mid_x1 + half_dx1
            left_y1 = mid_y1 + half_dy1
            right_x1 = mid_x1 - half_dx1
            right_y1 = mid_y1 - half_dy1

        if end.connected_to_track_id is not None:
            mid_x2 = (left_x2 + right_x2) / 2.0
            mid_y2 = (left_y2 + right_y2) / 2.0
            half_dx2 = (left_x2 - right_x2) * 0.5 * taper_factor
            half_dy2 = (left_y2 - right_y2) * 0.5 * taper_factor
            left_x2 = mid_x2 + half_dx2
            left_y2 = mid_y2 + half_dy2
            right_x2 = mid_x2 - half_dx2
            right_y2 = mid_y2 - half_dy2

        track_fill = "#d8d8d8" if not is_diverging else "#dcdcdc"
        rail_color = "#4a4a4a"

        if self.show_topology_overlay.get() and (
            start.connected_to_track_id or end.connected_to_track_id
        ):
            rail_color = "#2c5fb0"

        self.canvas.create_polygon(
            left_x1,
            left_y1,
            left_x2,
            left_y2,
            right_x2,
            right_y2,
            right_x1,
            right_y1,
            fill=track_fill,
            outline="",
        )

        self.canvas.create_line(
            left_x1,
            left_y1,
            left_x2,
            left_y2,
            fill=rail_color,
            width=rail_width,
        )
        self.canvas.create_line(
            right_x1,
            right_y1,
            right_x2,
            right_y2,
            fill=rail_color,
            width=rail_width,
        )

        mask_radius = 3.0 * self.zoom_scale
        for endpoint in (start, end):
            if endpoint.connected_to_track_id is not None:
                sx, sy = self._world_to_screen(endpoint.x, endpoint.y)
                self.canvas.create_oval(
                    sx - mask_radius,
                    sy - mask_radius,
                    sx + mask_radius,
                    sy + mask_radius,
                    fill=track_fill,
                    outline="",
                )

    def _draw_turnout_endpoint(
        self,
        turnout: TurnoutTrackElement,
        endpoint_name: str,
    ) -> None:
        endpoint = turnout.endpoints()[endpoint_name]
        sx, sy = self._world_to_screen(endpoint.x, endpoint.y)
        size = self.ENDPOINT_BOX_SIZE_PX * self.zoom_scale
        half = size / 2.0

        is_hover = (
            self._hover_track_id == turnout.track_id
            and self._hover_endpoint_name == endpoint_name
        )
        is_snap_candidate = self._snap_candidate == (turnout.track_id, endpoint_name)
        is_snap_locked = self._snap_locked == (turnout.track_id, endpoint_name)
        is_connected = endpoint.connected_to_track_id is not None

        is_active_dragged_endpoint = (
            self.selected_turnout_id == turnout.track_id
            and self._drag_mode == "turnout_endpoint"
            and self._drag_endpoint_name == endpoint_name
        )

        has_active_snap_preview = (
            is_active_dragged_endpoint and self._snap_preview_point is not None
        )

        outline = "#777777"
        fill = "white"
        width = max(1.0, 1.5 * self.zoom_scale)

        if is_connected:
            fill = "#3f78c4"
            outline = "#275388"

        if is_hover:
            outline = "#111111"

        if is_snap_candidate:
            outline = "#2f9e44"

        if has_active_snap_preview:
            fill = "#d8f5dd"
            outline = "#2f9e44"

        if is_active_dragged_endpoint and self._snap_candidate is not None:
            fill = "#d8f5dd"
            outline = "#2f9e44"

        if is_snap_locked or (
            is_active_dragged_endpoint and self._snap_locked is not None
        ):
            fill = "#2f9e44"
            outline = "#1d6a2d"

        if is_hover or is_snap_candidate or is_snap_locked or has_active_snap_preview:
            preview_radius = self.SNAP_PREVIEW_RADIUS_PX * self.zoom_scale
            self.canvas.create_oval(
                sx - preview_radius,
                sy - preview_radius,
                sx + preview_radius,
                sy + preview_radius,
                outline="#b7e4c7",
            )

        self.canvas.create_rectangle(
            sx - half,
            sy - half,
            sx + half,
            sy + half,
            outline=outline,
            fill=fill,
            width=width,
        )

    def _draw_turnout_rotate_handle(self, turnout: TurnoutTrackElement) -> None:
        sx, sy = self._turnout_rotate_handle_screen_position(turnout)
        radius = self.TURNOUT_ROTATE_HANDLE_RADIUS_PX * self.zoom_scale

        center_x, center_y = self._turnout_center_world(turnout)
        scx, scy = self._world_to_screen(center_x, center_y)

        self.canvas.create_line(
            scx,
            scy,
            sx,
            sy,
            fill="#cc8400",
            width=max(1.0, 1.5 * self.zoom_scale),
            dash=(3, 2),
        )

        self.canvas.create_oval(
            sx - radius,
            sy - radius,
            sx + radius,
            sy + radius,
            outline="#cc8400",
            fill="#fff4d6",
            width=max(1.0, 1.5 * self.zoom_scale),
        )

        arrow_half = max(4.0, 5.0 * self.zoom_scale)
        self.canvas.create_line(
            sx - arrow_half,
            sy,
            sx + arrow_half,
            sy,
            fill="#8a5a00",
            width=max(1.0, 1.5 * self.zoom_scale),
            arrow=tk.BOTH,
        )

    def _turnout_screen_bbox(
        self,
        turnout: TurnoutTrackElement,
    ) -> tuple[float, float, float, float]:
        points = [
            self._world_to_screen(turnout.trunk.x, turnout.trunk.y),
            self._world_to_screen(turnout.split_x, turnout.split_y),
            self._world_to_screen(turnout.straight.x, turnout.straight.y),
            self._world_to_screen(turnout.diverging.x, turnout.diverging.y),
        ]
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        return (min(xs), min(ys), max(xs), max(ys))

    def _turnout_center_world(
        self,
        turnout: TurnoutTrackElement,
    ) -> tuple[float, float]:
        xs = [
            turnout.trunk.x,
            turnout.split_x,
            turnout.straight.x,
            turnout.diverging.x,
        ]
        ys = [
            turnout.trunk.y,
            turnout.split_y,
            turnout.straight.y,
            turnout.diverging.y,
        ]
        return ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)

    def _turnout_rotate_handle_screen_position(
        self,
        turnout: TurnoutTrackElement,
    ) -> tuple[float, float]:
        bbox = self._turnout_screen_bbox(turnout)
        cx = (bbox[0] + bbox[2]) / 2.0
        cy = bbox[1] - (self.TURNOUT_ROTATE_HANDLE_OFFSET_PX * self.zoom_scale)
        return (cx, cy)

    def _turnout_rotate_handle_world_position(
        self,
        turnout: TurnoutTrackElement,
    ) -> tuple[float, float]:
        sx, sy = self._turnout_rotate_handle_screen_position(turnout)
        return self._screen_to_world(sx, sy)

    def _draw_endpoint(self, track: StraightTrackElement, endpoint_name: str) -> None:
        endpoint = track.endpoint(endpoint_name)
        sx, sy = self._world_to_screen(endpoint.x, endpoint.y)
        size = self.ENDPOINT_BOX_SIZE_PX * self.zoom_scale
        half = size / 2.0

        is_hover = (
            self._hover_track_id == track.track_id
            and self._hover_endpoint_name == endpoint_name
        )
        is_snap_candidate = self._snap_candidate == (track.track_id, endpoint_name)
        is_snap_locked = self._snap_locked == (track.track_id, endpoint_name)
        is_connected = endpoint.connected_to_track_id is not None

        outline = "#777777"
        fill = "white"
        width = max(1.0, 1.5 * self.zoom_scale)

        if is_connected:
            fill = "#3f78c4"
            outline = "#275388"

        if is_hover:
            outline = "#111111"

        if is_snap_candidate:
            outline = "#2f9e44"

        if is_snap_locked:
            fill = "#2f9e44"
            outline = "#1d6a2d"

        if is_hover or is_snap_candidate or is_snap_locked:
            preview_radius = self.SNAP_PREVIEW_RADIUS_PX * self.zoom_scale
            self.canvas.create_oval(
                sx - preview_radius,
                sy - preview_radius,
                sx + preview_radius,
                sy + preview_radius,
                outline="#b7e4c7",
            )

        self.canvas.create_rectangle(
            sx - half,
            sy - half,
            sx + half,
            sy + half,
            outline=outline,
            fill=fill,
            width=width,
        )

    def _draw_snap_preview(self) -> None:
        if self._snap_preview_point is None:
            return
        sx, sy = self._world_to_screen(*self._snap_preview_point)
        radius = self.SNAP_COMMIT_RADIUS_PX * self.zoom_scale
        self.canvas.create_oval(
            sx - radius,
            sy - radius,
            sx + radius,
            sy + radius,
            outline="#2f9e44",
            width=max(1.0, 2.0 * self.zoom_scale),
            dash=(3, 2),
        )

    def _draw_marquee_selection_rect(self) -> None:
        if self._marquee_start_world is None or self._marquee_end_world is None:
            return

        sx1, sy1 = self._world_to_screen(*self._marquee_start_world)
        sx2, sy2 = self._world_to_screen(*self._marquee_end_world)

        dash_len = max(4, int(6 * self.zoom_scale))
        gap_len = max(2, int(4 * self.zoom_scale))

        self.canvas.create_rectangle(
            sx1,
            sy1,
            sx2,
            sy2,
            outline="#2f80ed",
            width=max(1.0, 1.5 * self.zoom_scale),
            dash=(dash_len, gap_len),
            fill="",
        )

    def _draw_group_smart_snap_preview(self) -> None:
        if self._group_snap_preview_point is None:
            return

        sx, sy = self._world_to_screen(*self._group_snap_preview_point)
        radius = self.SNAP_COMMIT_RADIUS_PX * self.zoom_scale

        self.canvas.create_oval(
            sx - radius,
            sy - radius,
            sx + radius,
            sy + radius,
            outline="#2f9e44",
            width=max(1.0, 2.0 * self.zoom_scale),
            dash=(3, 2),
        )

        preview_radius = self.SNAP_PREVIEW_RADIUS_PX * self.zoom_scale
        self.canvas.create_oval(
            sx - preview_radius,
            sy - preview_radius,
            sx + preview_radius,
            sy + preview_radius,
            outline="#b7e4c7",
        )

    def _marquee_world_bbox(self) -> tuple[float, float, float, float] | None:
        if self._marquee_start_world is None or self._marquee_end_world is None:
            return None

        x1, y1 = self._marquee_start_world
        x2, y2 = self._marquee_end_world

        return (
            min(x1, x2),
            min(y1, y2),
            max(x1, x2),
            max(y1, y2),
        )

    def _track_is_inside_marquee(
        self,
        track: StraightTrackElement,
        bbox: tuple[float, float, float, float],
    ) -> bool:
        min_x, min_y, max_x, max_y = bbox

        return (
            min_x <= track.x1 <= max_x
            and min_y <= track.y1 <= max_y
            and min_x <= track.x2 <= max_x
            and min_y <= track.y2 <= max_y
        )

    def _turnout_is_inside_marquee(
        self,
        turnout: TurnoutTrackElement,
        bbox: tuple[float, float, float, float],
    ) -> bool:
        min_x, min_y, max_x, max_y = bbox

        points = (
            (turnout.trunk.x, turnout.trunk.y),
            (turnout.split_x, turnout.split_y),
            (turnout.straight.x, turnout.straight.y),
            (turnout.diverging.x, turnout.diverging.y),
        )

        return all(min_x <= x <= max_x and min_y <= y <= max_y for x, y in points)

    def _commit_marquee_selection(self) -> None:
        bbox = self._marquee_world_bbox()
        if bbox is None:
            return

        self.selected_track_ids.clear()
        self.selected_turnout_ids.clear()

        for track_id, track in self.tracks.items():
            if self._track_is_inside_marquee(track, bbox):
                self.selected_track_ids.add(track_id)

        for turnout_id, turnout in self.turnouts.items():
            if self._turnout_is_inside_marquee(turnout, bbox):
                self.selected_turnout_ids.add(turnout_id)

        self.selected_track_id = None
        self.selected_turnout_id = None

        # Prefer the topmost enclosed turnout first, then the topmost enclosed track,
        # based on current draw order.
        for turnout_id in reversed(self.turnout_order):
            if turnout_id in self.selected_turnout_ids:
                self.selected_turnout_id = turnout_id
                self._update_turnout_inspector(self.turnouts[turnout_id])
                break

        if self.selected_turnout_id is None:
            for track_id in reversed(self.track_order):
                if track_id in self.selected_track_ids:
                    self.selected_track_id = track_id
                    self._update_inspector(self.tracks[track_id])
                    break

        if self.selected_track_id is None and self.selected_turnout_id is None:
            self._update_inspector(None)

        total = len(self.selected_track_ids) + len(self.selected_turnout_ids)
        self._set_status(f"Marquee selected {total} object(s).")

    def _sync_primary_selection_from_group(self) -> None:
        self.selected_track_id = None
        self.selected_turnout_id = None

        for turnout_id in reversed(self.turnout_order):
            if turnout_id in self.selected_turnout_ids:
                self.selected_turnout_id = turnout_id
                self._update_turnout_inspector(self.turnouts[turnout_id])
                return

        for track_id in reversed(self.track_order):
            if track_id in self.selected_track_ids:
                self.selected_track_id = track_id
                self._update_inspector(self.tracks[track_id])
                return

        self._update_inspector(None)

    def _has_active_group_selection(self) -> bool:
        total = len(self.selected_track_ids) + len(self.selected_turnout_ids)
        return total > 1

    def _hit_is_in_selected_group(self, hit: dict[str, str]) -> bool:
        if hit["type"] == "track":
            return hit["track_id"] in self.selected_track_ids

        if hit["type"] == "turnout":
            return hit["turnout_id"] in self.selected_turnout_ids

        return False

    def _toggle_group_selection_for_hit(self, hit: dict[str, str]) -> None:
        if hit["type"] == "track":
            track_id = hit["track_id"]

            if track_id in self.selected_track_ids:
                self.selected_track_ids.remove(track_id)
            else:
                self.selected_track_ids.add(track_id)

            if self.selected_track_id == track_id:
                self.selected_track_id = None

        elif hit["type"] == "turnout":
            turnout_id = hit["turnout_id"]

            if turnout_id in self.selected_turnout_ids:
                self.selected_turnout_ids.remove(turnout_id)
            else:
                self.selected_turnout_ids.add(turnout_id)

            if self.selected_turnout_id == turnout_id:
                self.selected_turnout_id = None

        self._sync_primary_selection_from_group()

        total = len(self.selected_track_ids) + len(self.selected_turnout_ids)
        self._set_status(f"Group selection now contains {total} object(s).")
        self._refresh_canvas()

    def _selected_group_world_bbox(self) -> tuple[float, float, float, float] | None:
        xs: list[float] = []
        ys: list[float] = []

        for track_id in self.selected_track_ids:
            track = self.tracks.get(track_id)
            if track is None:
                continue
            xs.extend([track.x1, track.x2])
            ys.extend([track.y1, track.y2])

        for turnout_id in self.selected_turnout_ids:
            turnout = self.turnouts.get(turnout_id)
            if turnout is None:
                continue
            xs.extend(
                [
                    turnout.trunk.x,
                    turnout.split_x,
                    turnout.straight.x,
                    turnout.diverging.x,
                ]
            )
            ys.extend(
                [
                    turnout.trunk.y,
                    turnout.split_y,
                    turnout.straight.y,
                    turnout.diverging.y,
                ]
            )

        if not xs or not ys:
            return None

        return (min(xs), min(ys), max(xs), max(ys))

    def _selected_group_rotation_pivot(self) -> tuple[float, float] | None:
        bbox = self._selected_group_world_bbox()
        if bbox is None:
            return None

        min_x, min_y, max_x, max_y = bbox
        return ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)

    def _capture_group_rotation_snapshot(self) -> None:
        self._group_rotate_track_snapshot.clear()
        self._group_rotate_turnout_snapshot.clear()

        for track_id in self.selected_track_ids:
            track = self.tracks.get(track_id)
            if track is None:
                continue

            self._group_rotate_track_snapshot[track_id] = (
                track.x1,
                track.y1,
                track.x2,
                track.y2,
            )

        for turnout_id in self.selected_turnout_ids:
            turnout = self.turnouts.get(turnout_id)
            if turnout is None:
                continue

            trunk = turnout.endpoints()["trunk"]
            self._group_rotate_turnout_snapshot[turnout_id] = (
                turnout.x,
                turnout.y,
                turnout.angle_deg,
                trunk.x,
                trunk.y,
            )

    def _begin_group_rotation_state(self) -> None:
        self._group_rotate_active = False
        self._group_rotate_pivot = self._selected_group_rotation_pivot()

        # Preserve internal selected↔selected connections,
        # sever only selected↔unselected connections.
        self._clear_group_rotation_external_connections()

        self._capture_group_rotation_snapshot()

    def _clear_group_rotation_external_connections(self) -> None:
        selected_ids = set(self.selected_track_ids) | set(self.selected_turnout_ids)

        if not selected_ids:
            return

        # ----------------------------------------------------------
        # Tracks: clear only endpoints connected outside the group
        # ----------------------------------------------------------
        for track_id in list(self.selected_track_ids):
            track = self.tracks.get(track_id)
            if track is None:
                continue

            for endpoint_name in ("A", "B"):
                endpoint = track.endpoint(endpoint_name)
                other_id = endpoint.connected_to_track_id

                if other_id is None:
                    continue

                if other_id not in selected_ids:
                    self._clear_endpoint_connection(track, endpoint_name)

        # ----------------------------------------------------------
        # Turnouts: clear only endpoints connected outside the group
        # ----------------------------------------------------------
        for turnout_id in list(self.selected_turnout_ids):
            turnout = self.turnouts.get(turnout_id)
            if turnout is None:
                continue

            for endpoint_name in ("trunk", "straight", "diverging"):
                endpoint = turnout.endpoints()[endpoint_name]
                other_id = endpoint.connected_to_track_id

                if other_id is None:
                    continue

                if other_id not in selected_ids:
                    self._clear_turnout_endpoint_connection(turnout, endpoint_name)

    def _draw_topology_endpoint_overlay(
        self, track: StraightTrackElement, endpoint_name: str
    ) -> None:
        classification = self._connection_classification(track, endpoint_name)
        if classification == "open":
            return

        if classification == "continuation":
            color = "#cfcfcf"  # very light gray

        endpoint = track.endpoint(endpoint_name)
        sx, sy = self._world_to_screen(endpoint.x, endpoint.y)

        radius = 10.0 * self.zoom_scale
        color = self._connection_overlay_color(classification)

        self.canvas.create_oval(
            sx - radius,
            sy - radius,
            sx + radius,
            sy + radius,
            outline=color,
            width=max(1.0, 2.0 * self.zoom_scale),
        )

        self.canvas.create_text(
            sx,
            sy - (18.0 * self.zoom_scale),
            text=classification,
            font=("Arial", max(7, int(8 * self.zoom_scale))),
            fill=color,
        )

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def _on_canvas_press(self, event: tk.Event) -> None:
        world_x, world_y = self._event_world(event)
        self.tooltip.hide()
        self._cancel_tooltip_timer()

        state = int(getattr(event, "state", 0))
        ctrl_down = bool(state & 0x0004)
        shift_down = bool(state & 0x0001)
        alt_down = bool(state & 0x0008)
        hit = self._hit_test(world_x, world_y)
        tool = self.selected_tool.get()

        if tool == "track":
            self._begin_track_creation(world_x, world_y)
            return

        if tool == "turnout":
            self._begin_turnout_creation(world_x, world_y)
            return

        if shift_down and tool == "select":
            self._drag_mode = "marquee_select"
            self._drag_track_id = None
            self._drag_endpoint_name = None
            self._drag_last_world = None

            self._marquee_start_world = (world_x, world_y)
            self._marquee_end_world = (world_x, world_y)

            self._refresh_canvas()
            self._set_status("Marquee selection started.")
            return

        if hit is None:
            self.selected_track_id = None
            self.selected_turnout_id = None
            self.selected_track_ids.clear()
            self.selected_turnout_ids.clear()

            self._drag_mode = None
            self._drag_track_id = None
            self._drag_endpoint_name = None

            self._update_inspector(None)
            self._refresh_canvas()
            self._set_status("Selection cleared.")
            return

        if ctrl_down and tool == "select":
            self._drag_mode = None
            self._drag_track_id = None
            self._drag_endpoint_name = None
            self._drag_last_world = None
            self._toggle_group_selection_for_hit(hit)
            return

        if (
            tool == "select"
            and hit is not None
            and self._has_active_group_selection()
            and self._hit_is_in_selected_group(hit)
            and hit["part"] == "body"
        ):
            self._drag_mode = "group_move"
            self._drag_track_id = None
            self._drag_endpoint_name = None
            self._drag_last_world = (world_x, world_y)

            self._group_drag_track_ids = set(self.selected_track_ids)
            self._group_drag_turnout_ids = set(self.selected_turnout_ids)
            self._group_smart_move_active = alt_down

            self._clear_group_external_connections()

            self._refresh_canvas()
            if self._group_smart_move_active:
                self._set_status("Smart moving selected group.")
            else:
                self._set_status("Moving selected group.")
            return

        if hit["type"] == "track":
            self.selected_track_ids.clear()
            self.selected_turnout_ids.clear()

            self.selected_track_id = hit["track_id"]
            self.selected_turnout_id = None

            self._drag_track_id = hit["track_id"]
            self._drag_last_world = (world_x, world_y)

            if ctrl_down and hit["part"] == "endpoint":
                self._drag_mode = "endpoint"
                self._drag_endpoint_name = hit["endpoint_name"]
                self._set_status(
                    f"Reshaping {self.tracks[self.selected_track_id].name} from endpoint {self._drag_endpoint_name}."
                )
            elif hit["part"] == "endpoint":
                self._drag_mode = "endpoint"
                self._drag_endpoint_name = hit["endpoint_name"]
                self._set_status(
                    f"Reshaping {self.tracks[self.selected_track_id].name} from endpoint {self._drag_endpoint_name}."
                )
            else:
                self._drag_mode = "move"
                self._drag_endpoint_name = None
                self._set_status(f"Moving {self.tracks[self.selected_track_id].name}.")

            self._update_inspector(self.tracks[self.selected_track_id])
            self._refresh_canvas()
            return

        if hit["type"] == "turnout":
            self.selected_track_ids.clear()
            self.selected_turnout_ids.clear()

            self.selected_turnout_id = hit["turnout_id"]
            self.selected_track_id = None
            self._drag_track_id = None
            self._drag_last_world = (world_x, world_y)

            turnout = self.turnouts[self.selected_turnout_id]

            if hit["part"] == "rotate_handle":
                self._drag_mode = "turnout_rotate"
                self._drag_endpoint_name = None
                self._rotate_turnout_id = turnout.track_id

                # --------------------------------------------------
                # CLEAR CONNECTIONS BEFORE ROTATION
                # --------------------------------------------------
                for endpoint_name, endpoint in turnout.endpoints().items():
                    if endpoint.connected_to_track_id is None:
                        continue

                    other_id = endpoint.connected_to_track_id
                    other_endpoint_name = endpoint.connected_to_endpoint_name

                    endpoint.connected_to_track_id = None
                    endpoint.connected_to_endpoint_name = None

                    if other_id and other_endpoint_name:
                        other_track = self.tracks.get(other_id)
                        if other_track:
                            other_ep = other_track.endpoint(other_endpoint_name)
                            if other_ep.connected_to_track_id == turnout.track_id:
                                other_ep.connected_to_track_id = None
                                other_ep.connected_to_endpoint_name = None

                        other_turnout = self.turnouts.get(other_id)
                        if other_turnout:
                            other_ep = other_turnout.endpoints()[other_endpoint_name]
                            if other_ep.connected_to_track_id == turnout.track_id:
                                other_ep.connected_to_track_id = None
                                other_ep.connected_to_endpoint_name = None

                pivot_x, pivot_y = self._turnout_center_world(turnout)
                self._rotate_pivot_world = (pivot_x, pivot_y)

                self._rotate_start_mouse_angle_deg = math.degrees(
                    math.atan2(world_y - pivot_y, world_x - pivot_x)
                )
                self._rotate_start_turnout_angle_deg = turnout.angle_deg

                self._set_status(f"Rotating {turnout.name}.")

            elif hit["part"] == "endpoint":
                self._drag_mode = "turnout_endpoint"
                self._drag_endpoint_name = hit["endpoint_name"]
                self._set_status(
                    f"Reshaping {turnout.name} from endpoint {self._drag_endpoint_name}."
                )
            else:
                self._drag_mode = "move"
                self._drag_endpoint_name = None
                self._set_status(f"Moving {turnout.name}.")

            self._update_turnout_inspector(turnout)
            self._refresh_canvas()
            return

    def _on_canvas_right_click(self, event: tk.Event) -> None:
        print("RIGHT CLICK DETECTED")

        world_x, world_y = self._event_world(event)
        hit = self._hit_test(world_x, world_y)

        print("HIT:", hit)

        total_selected = len(self.selected_track_ids) + len(self.selected_turnout_ids)

        # ----------------------------------------------------------
        # If a multi-selection already exists and the right-click is
        # on one of its members, keep the group selection intact and
        # show the group menu.
        # ----------------------------------------------------------
        if (
            total_selected > 1
            and hit is not None
            and self._hit_is_in_selected_group(hit)
        ):
            label = "Rotate Group"
            self.canvas_context_menu.entryconfig(0, label=label)

            try:
                self.canvas_context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.canvas_context_menu.grab_release()
            return

        if hit is None:
            return

        # ----------------------------------------------------------
        # Force selection to the object under cursor
        # ----------------------------------------------------------
        if hit["type"] == "track":
            track_id = hit["track_id"]

            self.selected_track_id = track_id
            self.selected_turnout_id = None

            self.selected_track_ids = {track_id}
            self.selected_turnout_ids.clear()

            self._update_inspector(self.tracks[track_id])

        elif hit["type"] == "turnout":
            turnout_id = hit["turnout_id"]

            self.selected_turnout_id = turnout_id
            self.selected_track_id = None

            self.selected_turnout_ids = {turnout_id}
            self.selected_track_ids.clear()

            self._update_turnout_inspector(self.turnouts[turnout_id])

        # Refresh visuals to reflect new selection
        self._refresh_canvas()

        total_selected = len(self.selected_track_ids) + len(self.selected_turnout_ids)
        if total_selected == 0:
            return

        # ----------------------------------------------------------
        # Update Rotate menu label dynamically
        # ----------------------------------------------------------
        if total_selected > 1:
            label = "Rotate Group"
        elif self.selected_track_id:
            obj = self.tracks[self.selected_track_id]
            label = f"Rotate {obj.name}"
        elif self.selected_turnout_id:
            obj = self.turnouts[self.selected_turnout_id]
            label = f"Rotate {obj.name}"
        else:
            label = "Rotate"

        self.canvas_context_menu.entryconfig(0, label=label)

        try:
            self.canvas_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.canvas_context_menu.grab_release()

    def _on_canvas_drag(self, event: tk.Event) -> None:
        world_x, world_y = self._event_world(event)

        if self._drag_mode == "marquee_select":
            self._marquee_end_world = (world_x, world_y)
            self._refresh_canvas()
            return

        if self._drag_mode == "group_move" and self._drag_last_world is not None:
            dx = world_x - self._drag_last_world[0]
            dy = world_y - self._drag_last_world[1]

            for track_id in self._group_drag_track_ids:
                track = self.tracks.get(track_id)
                if track is not None:
                    track.move_by(dx, dy)

            for turnout_id in self._group_drag_turnout_ids:
                turnout = self.turnouts.get(turnout_id)
                if turnout is not None:
                    turnout.x += dx
                    turnout.y += dy
                    turnout.recalculate_geometry_from_parameters()

            self._drag_last_world = (world_x, world_y)

            if self._group_smart_move_active:
                candidate = self._find_best_group_smart_snap_candidate()
                if candidate is None:
                    self._group_snap_candidate = None
                    self._group_snap_active_endpoint = None
                    self._group_snap_preview_point = None
                else:
                    (
                        external_candidate,
                        moving_candidate,
                        preview_point,
                    ) = candidate
                    self._group_snap_candidate = external_candidate
                    self._group_snap_active_endpoint = moving_candidate
                    self._group_snap_preview_point = preview_point
            else:
                self._group_snap_candidate = None
                self._group_snap_active_endpoint = None
                self._group_snap_preview_point = None

            if self.selected_turnout_id is not None:
                turnout = self.turnouts.get(self.selected_turnout_id)
                if turnout is not None:
                    self._update_turnout_inspector(turnout)
            elif self.selected_track_id is not None:
                track = self.tracks.get(self.selected_track_id)
                if track is not None:
                    self._update_inspector(track)

            self._refresh_canvas()
            return

        if self._drag_mode == "create" and self._create_track_id is not None:
            track = self.tracks[self._create_track_id]
            x, y = self._apply_grid_snap(world_x, world_y)
            track.set_endpoint("B", x, y)
            self._update_snap_state(
                active_track_id=track.track_id,
                active_endpoint_name="B",
                active_x=x,
                active_y=y,
            )
            self._update_inspector(track)
            self._refresh_canvas()
            return

        if self._drag_track_id is not None and self._drag_last_world is not None:
            track = self.tracks[self._drag_track_id]

            if self._drag_mode == "move":
                dx = world_x - self._drag_last_world[0]
                dy = world_y - self._drag_last_world[1]

                track.move_by(dx, dy)
                self._clamp_track_to_canvas(track)

                self._drag_last_world = (world_x, world_y)
                self._clear_track_connections(track)

                best_snap = self._find_best_snap_for_moved_track(track)
                if best_snap is None:
                    self._snap_candidate = None
                    self._snap_candidate_since = None
                    self._snap_locked = None
                    self._snap_preview_point = None
                else:
                    (
                        active_endpoint_name,
                        _candidate_track_id,
                        _candidate_endpoint_name,
                        _candidate_x,
                        _candidate_y,
                    ) = best_snap

                    self._update_snap_state(
                        active_track_id=track.track_id,
                        active_endpoint_name=active_endpoint_name,
                        active_x=track.endpoint(active_endpoint_name).x,
                        active_y=track.endpoint(active_endpoint_name).y,
                    )

                self._update_inspector(track)
                self._refresh_canvas()
                return

            if self._drag_mode == "endpoint" and self._drag_endpoint_name is not None:
                x, y = self._apply_grid_snap(world_x, world_y)
                track.set_endpoint(self._drag_endpoint_name, x, y)
                self._clear_endpoint_connection(track, self._drag_endpoint_name)
                self._update_snap_state(
                    active_track_id=track.track_id,
                    active_endpoint_name=self._drag_endpoint_name,
                    active_x=x,
                    active_y=y,
                )
                self._update_inspector(track)
                self._refresh_canvas()
                return

        if self.selected_turnout_id is not None and self._drag_last_world is not None:
            turnout = self.turnouts[self.selected_turnout_id]

            # ----------------------------------------------------------
            # TURNOUT ROTATION
            # ----------------------------------------------------------
            if self._drag_mode == "turnout_rotate" and self._rotate_turnout_id:
                if (
                    self._rotate_pivot_world is None
                    or self._rotate_start_mouse_angle_deg is None
                    or self._rotate_start_turnout_angle_deg is None
                ):
                    return

                turnout = self.turnouts[self._rotate_turnout_id]

                pivot_x, pivot_y = self._rotate_pivot_world

                current_mouse_angle = math.degrees(
                    math.atan2(world_y - pivot_y, world_x - pivot_x)
                )

                # changes to handle 15 degree increments rotate
                delta_angle = current_mouse_angle - self._rotate_start_mouse_angle_deg
                new_angle = self._rotate_start_turnout_angle_deg + delta_angle

                state = int(getattr(event, "state", 0))
                shift_down = bool(state & 0x0001)
                if shift_down:
                    new_angle = self._snap_angle(new_angle, 15.0)

                # normalize to [-180, 180]
                new_angle = (new_angle + 180.0) % 360.0 - 180.0

                # Preserve the visual pivot during rotation.
                old_center_x, old_center_y = self._turnout_center_world(turnout)

                turnout.angle_deg = new_angle
                turnout.recalculate_geometry_from_parameters()

                new_center_x, new_center_y = self._turnout_center_world(turnout)

                turnout.x += old_center_x - new_center_x
                turnout.y += old_center_y - new_center_y
                turnout.recalculate_geometry_from_parameters()

                self._update_turnout_inspector(turnout)
                self._refresh_canvas()
                return

            if self._drag_mode == "move":
                dx = world_x - self._drag_last_world[0]
                dy = world_y - self._drag_last_world[1]

                turnout.x += dx
                turnout.y += dy
                turnout.recalculate_geometry_from_parameters()

                self._drag_last_world = (world_x, world_y)

                best_snap = self._find_best_snap_for_moved_turnout(turnout)
                if best_snap is None:
                    self._snap_candidate = None
                    self._snap_candidate_since = None
                    self._snap_locked = None
                    self._snap_preview_point = None
                else:
                    (
                        active_endpoint_name,
                        _candidate_track_id,
                        _candidate_endpoint_name,
                        _candidate_x,
                        _candidate_y,
                    ) = best_snap

                    active_endpoint = turnout.endpoints()[active_endpoint_name]
                    self._update_turnout_snap_state(
                        turnout_id=turnout.track_id,
                        endpoint_name=active_endpoint_name,
                        active_x=active_endpoint.x,
                        active_y=active_endpoint.y,
                    )

                self._update_turnout_inspector(turnout)
                self._refresh_canvas()
                return

            if (
                self._drag_mode == "turnout_endpoint"
                and self._drag_endpoint_name is not None
            ):
                x, y = self._apply_grid_snap(world_x, world_y)

                if self._drag_endpoint_name == "trunk":
                    turnout.x = x
                    turnout.y = y
                    turnout.recalculate_geometry_from_parameters()

                elif self._drag_endpoint_name == "straight":
                    dx = x - turnout.trunk.x
                    dy = y - turnout.trunk.y
                    turnout.angle_deg = math.degrees(math.atan2(dy, dx))
                    turnout.straight_len = max(20.0, math.hypot(dx, dy))
                    turnout.recalculate_geometry_from_parameters()

                elif self._drag_endpoint_name == "diverging":
                    dx = x - turnout.split_x
                    dy = y - turnout.split_y

                    diverge_heading_deg = math.degrees(math.atan2(dy, dx))
                    signed_angle = diverge_heading_deg - turnout.angle_deg

                    turnout.diverge_angle_deg = max(2.0, abs(signed_angle))
                    turnout.diverge_len = max(20.0, math.hypot(dx, dy))
                    turnout.recalculate_geometry_from_parameters()

                self._update_turnout_snap_state(
                    turnout_id=turnout.track_id,
                    endpoint_name=self._drag_endpoint_name,
                    active_x=x,
                    active_y=y,
                )

                self._drag_last_world = (world_x, world_y)
                self._update_turnout_inspector(turnout)
                self._refresh_canvas()
                return

    def _find_best_snap_for_moved_turnout(
        self,
        turnout: TurnoutTrackElement,
    ) -> tuple[str, str, str, float, float] | None:
        best: tuple[str, str, str, float, float] | None = None
        best_distance = float("inf")

        # Whole-turnout body move stays rigid-body translation only.
        # We still allow trunk / straight / diverging to participate as
        # snap candidates so the user gets the same cue/lock behavior.
        for active_endpoint_name in ("trunk", "straight", "diverging"):
            active_endpoint = turnout.endpoints()[active_endpoint_name]
            candidate = self._find_snap_candidate_for_turnout_endpoint(
                turnout_id=turnout.track_id,
                endpoint_name=active_endpoint_name,
                active_x=active_endpoint.x,
                active_y=active_endpoint.y,
            )
            if candidate is None:
                continue

            (
                candidate_track_id,
                candidate_endpoint_name,
                candidate_x,
                candidate_y,
                _candidate_kind,
            ) = candidate

            distance = math.hypot(
                candidate_x - active_endpoint.x,
                candidate_y - active_endpoint.y,
            )

            if distance < best_distance:
                best_distance = distance
                best = (
                    active_endpoint_name,
                    candidate_track_id,
                    candidate_endpoint_name,
                    candidate_x,
                    candidate_y,
                )

        return best

    def _find_snap_candidate_for_turnout_endpoint(
        self,
        *,
        turnout_id: str,
        endpoint_name: str,
        active_x: float,
        active_y: float,
    ) -> tuple[str, str, float, float, str] | None:
        turnout = self.turnouts[turnout_id]
        active_heading = self._turnout_endpoint_heading_deg(turnout, endpoint_name)

        best: tuple[str, str, float, float, str] | None = None
        best_distance = float("inf")

        preview_radius = self.SNAP_PREVIEW_RADIUS_PX / max(self.zoom_scale, 0.001)

        for track in self.tracks.values():
            for candidate_endpoint_name in ("A", "B"):
                endpoint = track.endpoint(candidate_endpoint_name)
                distance = math.hypot(endpoint.x - active_x, endpoint.y - active_y)
                if distance > preview_radius:
                    continue

                candidate_heading = self._endpoint_heading_deg(
                    track,
                    candidate_endpoint_name,
                )

                if endpoint_name == "diverging":
                    headings_ok = True
                else:
                    headings_ok = self._headings_are_compatible(
                        active_heading,
                        candidate_heading,
                    )

                if not headings_ok:
                    continue

                if distance < best_distance:
                    best_distance = distance
                    best = (
                        track.track_id,
                        candidate_endpoint_name,
                        endpoint.x,
                        endpoint.y,
                        "track",
                    )

        for other_turnout in self.turnouts.values():
            if other_turnout.track_id == turnout_id:
                continue

            for candidate_endpoint_name, endpoint in other_turnout.endpoints().items():
                distance = math.hypot(endpoint.x - active_x, endpoint.y - active_y)
                if distance > preview_radius:
                    continue

                candidate_heading = self._turnout_endpoint_heading_deg(
                    other_turnout,
                    candidate_endpoint_name,
                )

                if endpoint_name == "diverging":
                    headings_ok = True
                else:
                    headings_ok = self._headings_are_compatible(
                        active_heading,
                        candidate_heading,
                    )

                if not headings_ok:
                    continue

                if distance < best_distance:
                    best_distance = distance
                    best = (
                        other_turnout.track_id,
                        candidate_endpoint_name,
                        endpoint.x,
                        endpoint.y,
                        "turnout",
                    )

        return best

    def _clamp_track_to_canvas(self, track: StraightTrackElement) -> None:
        min_x = min(track.x1, track.x2)
        min_y = min(track.y1, track.y2)
        max_x = max(track.x1, track.x2)
        max_y = max(track.y1, track.y2)

        dx = 0.0
        dy = 0.0

        if min_x < 0.0:
            dx = -min_x
        elif max_x > 4000.0:
            dx = 4000.0 - max_x

        if min_y < 0.0:
            dy = -min_y
        elif max_y > 2600.0:
            dy = 2600.0 - max_y

        if dx != 0.0 or dy != 0.0:
            track.move_by(dx, dy)

    def _on_canvas_release(self, event: tk.Event) -> None:
        if self._drag_mode == "marquee_select":
            self._commit_marquee_selection()
            self._end_drag()
            self._refresh_canvas()
            return

        if self._drag_mode == "group_move":
            total = len(self.selected_track_ids) + len(self.selected_turnout_ids)
            snapped = self._commit_group_smart_snap_if_available()
            self._end_drag()
            self._refresh_canvas()

            if snapped:
                self._set_status(
                    f"Smart moved selected group ({total} object(s)) and connected."
                )
            else:
                self._set_status(f"Moved selected group ({total} object(s)).")
            return

        if self._drag_mode == "create" and self._create_track_id is not None:
            track = self.tracks[self._create_track_id]
            if track.pixel_length < 4.0:
                self._delete_track(track.track_id)
                self._set_status("Track creation canceled.")
            else:
                self._commit_snap_if_locked(track.track_id, "B")
                self.selected_track_id = track.track_id
                self._set_status(f"Placed {track.name}.")
                self._update_inspector(track)
            self._end_drag()
            self._refresh_canvas()
            return

        if (
            self._drag_track_id is not None
            and self._drag_mode == "endpoint"
            and self._drag_endpoint_name is not None
        ):
            self._commit_snap_if_locked(self._drag_track_id, self._drag_endpoint_name)
            self._update_inspector(self.tracks[self._drag_track_id])
            self._set_status(
                f"Updated geometry for {self.tracks[self._drag_track_id].name}."
            )

        elif self._drag_track_id is not None and self._drag_mode == "move":
            track = self.tracks[self._drag_track_id]

            # ----------------------------------------------------------
            # IMPORTANT:
            # Try endpoint snap first. Only fall back to grid snap if
            # no endpoint snap target is available.
            # ----------------------------------------------------------
            best_snap = self._find_best_snap_for_moved_track(track)
            if best_snap is not None:
                active_endpoint_name = best_snap[0]
                self._update_snap_state(
                    active_track_id=track.track_id,
                    active_endpoint_name=active_endpoint_name,
                    active_x=track.endpoint(active_endpoint_name).x,
                    active_y=track.endpoint(active_endpoint_name).y,
                )
                self._commit_snap_if_locked(track.track_id, active_endpoint_name)

            elif self.snap_to_grid.get():
                snapped_x1, snapped_y1 = self._apply_grid_snap(track.x1, track.y1)
                dx = snapped_x1 - track.x1
                dy = snapped_y1 - track.y1
                track.move_by(dx, dy)
                self._clamp_track_to_canvas(track)

            self._update_inspector(track)
            self._set_status(f"Moved {track.name}.")

        elif self.selected_turnout_id is not None:
            turnout = self.turnouts[self.selected_turnout_id]

            if (
                self._drag_mode == "turnout_endpoint"
                and self._drag_endpoint_name is not None
            ):
                self._commit_turnout_snap_if_locked(
                    self.selected_turnout_id,
                    self._drag_endpoint_name,
                )
                self._update_turnout_inspector(turnout)
                self._set_status(f"Updated geometry for {turnout.name}.")

            elif self._drag_mode == "move":
                best_snap = self._find_best_snap_for_moved_turnout(turnout)

                if best_snap is not None:
                    active_endpoint_name = best_snap[0]
                    active_endpoint = turnout.endpoints()[active_endpoint_name]

                    self._update_turnout_snap_state(
                        turnout_id=turnout.track_id,
                        endpoint_name=active_endpoint_name,
                        active_x=active_endpoint.x,
                        active_y=active_endpoint.y,
                    )
                    self._commit_moved_turnout_snap_if_locked(
                        turnout.track_id,
                        active_endpoint_name,
                    )

                elif self.snap_to_grid.get():
                    snapped_x, snapped_y = self._apply_grid_snap(turnout.x, turnout.y)
                    turnout.x = snapped_x
                    turnout.y = snapped_y
                    turnout.recalculate_geometry_from_parameters()

                self._update_turnout_inspector(turnout)
                self._set_status(f"Moved {turnout.name}.")

        self._end_drag()
        self._refresh_canvas()

    def _on_delete_key(self, _event: tk.Event | None = None) -> None:
        track_ids_to_delete = set(self.selected_track_ids)
        turnout_ids_to_delete = set(self.selected_turnout_ids)

        if not track_ids_to_delete and not turnout_ids_to_delete:
            if self.selected_track_id is not None:
                track_ids_to_delete.add(self.selected_track_id)
            if self.selected_turnout_id is not None:
                turnout_ids_to_delete.add(self.selected_turnout_id)

        total = len(track_ids_to_delete) + len(turnout_ids_to_delete)
        if total == 0:
            return

        confirmed = messagebox.askyesno(
            "Confirm Delete",
            f"Delete {total} selected object(s)?",
            parent=self.root,
        )
        if not confirmed:
            return

        for track_id in list(track_ids_to_delete):
            self._delete_track(track_id)

        for turnout_id in list(turnout_ids_to_delete):
            self._delete_turnout(turnout_id)

        self.selected_track_id = None
        self.selected_turnout_id = None
        self.selected_track_ids.clear()
        self.selected_turnout_ids.clear()

        self._update_inspector(None)
        self._refresh_canvas()
        self._set_status(f"Deleted {total} object(s).")

    def _on_canvas_motion(self, event: tk.Event) -> None:
        world_x, world_y = self._event_world(event)
        hit = self._hit_test(world_x, world_y)

        self._hover_track_id = None
        self._hover_endpoint_name = None

        if hit is not None:
            if hit["type"] == "track":
                self._hover_track_id = hit["track_id"]
                if hit["part"] == "endpoint":
                    self._hover_endpoint_name = hit["endpoint_name"]

            elif hit["type"] == "turnout":
                self._hover_track_id = hit["turnout_id"]
                if hit["part"] == "endpoint":
                    self._hover_endpoint_name = hit["endpoint_name"]

            self._schedule_tooltip(
                event.x_root,
                event.y_root,
                self._tooltip_text_for_hit(hit),
            )
        else:
            self.tooltip.hide()
            self._cancel_tooltip_timer()

        if self._drag_mode is None:
            self._refresh_canvas()

    def _on_canvas_leave(self, _event: tk.Event) -> None:
        self._hover_track_id = None
        self._hover_endpoint_name = None
        self.tooltip.hide()
        self._cancel_tooltip_timer()
        if self._drag_mode is None:
            self._refresh_canvas()

    def _on_mousewheel_zoom(self, event: tk.Event) -> None:
        factor = 1.0 / self.ZOOM_STEP if event.delta > 0 else self.ZOOM_STEP
        self._zoom_at(event.x, event.y, factor)

    # ------------------------------------------------------------------
    # Track creation/edit helpers
    # ------------------------------------------------------------------
    def _begin_track_creation(self, world_x: float, world_y: float) -> None:
        x, y = self._apply_grid_snap(world_x, world_y)
        track_id = str(uuid4())
        suffix = len(self.tracks) + 1
        new_track = StraightTrackElement(
            track_id=track_id,
            name=f"Track {suffix}",
            track_type=TrackType.MAINLINE,
            x1=x,
            y1=y,
            x2=x,
            y2=y,
            length_ft=100.0,
        )

        self.tracks[track_id] = new_track
        self.track_order.append(track_id)

        self.selected_track_id = track_id
        self.selected_turnout_id = None
        self.selected_track_ids.clear()
        self.selected_turnout_ids.clear()

        self._create_track_id = track_id

        self._drag_track_id = track_id
        self._drag_mode = "create"
        self._drag_endpoint_name = "B"
        self._drag_last_world = (x, y)
        self._update_inspector(new_track)
        self._refresh_canvas()
        self._set_status("Drag to place a new straight track segment.")

    def _begin_turnout_creation(self, world_x: float, world_y: float) -> None:
        x, y = self._apply_grid_snap(world_x, world_y)
        suffix = len(self.turnouts) + 1

        turnout = TurnoutTrackElement(
            name=f"Turnout {suffix}",
            hand=self._turnout_hand_var.get().strip() or "right",
            clearance_length_ft=float(
                self._turnout_clearance_var.get().strip() or "150.0"
            ),
            x=x,
            y=y,
            angle_deg=0.0,
        )

        self.turnouts[turnout.track_id] = turnout
        self.turnout_order.append(turnout.track_id)

        self.selected_track_id = None
        self.selected_turnout_id = turnout.track_id
        self.selected_track_ids.clear()
        self.selected_turnout_ids.clear()

        self._update_turnout_inspector(turnout)
        self._refresh_canvas()
        self._set_status(f"Placed {turnout.name}.")

    def _delete_selected(self, _event: tk.Event | None = None) -> None:
        if self.selected_track_id is not None:
            name = self.tracks[self.selected_track_id].name
            self._delete_track(self.selected_track_id)
            self.selected_track_id = None
            self._update_inspector(None)
            self._refresh_canvas()
            self._set_status(f"Deleted {name}.")
            return

        if self.selected_turnout_id is not None:
            name = self.turnouts[self.selected_turnout_id].name
            self._delete_turnout(self.selected_turnout_id)
            self.selected_turnout_id = None
            self._update_turnout_inspector(None)
            self._refresh_canvas()
            self._set_status(f"Deleted {name}.")

    def _delete_track(self, track_id: str) -> None:
        track = self.tracks.get(track_id)
        if track is None:
            return

        for other in self.tracks.values():
            if other.track_id == track_id:
                continue
            if other.endpoint_a.connected_to_track_id == track_id:
                other.endpoint_a.connected_to_track_id = None
                other.endpoint_a.connected_to_endpoint_name = None
            if other.endpoint_b.connected_to_track_id == track_id:
                other.endpoint_b.connected_to_track_id = None
                other.endpoint_b.connected_to_endpoint_name = None

        self.tracks.pop(track_id, None)
        if track_id in self.track_order:
            self.track_order.remove(track_id)

    def _delete_turnout(self, turnout_id: str) -> None:
        self.turnouts.pop(turnout_id, None)
        if turnout_id in self.turnout_order:
            self.turnout_order.remove(turnout_id)

    def _nudge_selected(self, dx_units: int, dy_units: int) -> None:
        if self.selected_track_id is None:
            return
        track = self.tracks[self.selected_track_id]
        step = self.GRID_SPACING if self.snap_to_grid.get() else 5.0
        track.move_by(dx_units * step, dy_units * step)
        self._clear_track_connections(track)
        self._update_inspector(track)
        self._refresh_canvas()
        self._set_status(f"Nudged {track.name}.")

    def _clear_track_connections(self, track: StraightTrackElement) -> None:
        self._clear_endpoint_connection(track, "A")
        self._clear_endpoint_connection(track, "B")

    def _clear_endpoint_connection(
        self, track: StraightTrackElement, endpoint_name: str
    ) -> None:
        endpoint = track.endpoint(endpoint_name)
        other_track_id = endpoint.connected_to_track_id
        other_endpoint_name = endpoint.connected_to_endpoint_name

        endpoint.connected_to_track_id = None
        endpoint.connected_to_endpoint_name = None

        if other_track_id is None or other_endpoint_name is None:
            return

        other_track = self.tracks.get(other_track_id)
        if other_track is not None:
            other_endpoint = other_track.endpoint(other_endpoint_name)
            if other_endpoint.connected_to_track_id == track.track_id:
                other_endpoint.connected_to_track_id = None
                other_endpoint.connected_to_endpoint_name = None
            return

        other_turnout = self.turnouts.get(other_track_id)
        if other_turnout is not None:
            other_endpoint = other_turnout.endpoints()[other_endpoint_name]
            if other_endpoint.connected_to_track_id == track.track_id:
                other_endpoint.connected_to_track_id = None
                other_endpoint.connected_to_endpoint_name = None

    def _clear_turnout_endpoint_connection(
        self,
        turnout: TurnoutTrackElement,
        endpoint_name: str,
    ) -> None:
        endpoint = turnout.endpoints()[endpoint_name]
        other_track_id = endpoint.connected_to_track_id
        other_endpoint_name = endpoint.connected_to_endpoint_name

        endpoint.connected_to_track_id = None
        endpoint.connected_to_endpoint_name = None

        if other_track_id is None or other_endpoint_name is None:
            return

        other_track = self.tracks.get(other_track_id)
        if other_track is not None:
            other_endpoint = other_track.endpoint(other_endpoint_name)
            if other_endpoint.connected_to_track_id == turnout.track_id:
                other_endpoint.connected_to_track_id = None
                other_endpoint.connected_to_endpoint_name = None
            return

        other_turnout = self.turnouts.get(other_track_id)
        if other_turnout is not None:
            other_endpoint = other_turnout.endpoints()[other_endpoint_name]
            if other_endpoint.connected_to_track_id == turnout.track_id:
                other_endpoint.connected_to_track_id = None
                other_endpoint.connected_to_endpoint_name = None

    def _clear_group_external_connections(self) -> None:
        selected_ids = set(self.selected_track_ids) | set(self.selected_turnout_ids)

        if not selected_ids:
            return

        for track_id in list(self.selected_track_ids):
            track = self.tracks.get(track_id)
            if track is None:
                continue

            for endpoint_name in ("A", "B"):
                endpoint = track.endpoint(endpoint_name)
                other_id = endpoint.connected_to_track_id

                if other_id is None:
                    continue

                if other_id not in selected_ids:
                    self._clear_endpoint_connection(track, endpoint_name)

        for turnout_id in list(self.selected_turnout_ids):
            turnout = self.turnouts.get(turnout_id)
            if turnout is None:
                continue

            for endpoint_name in ("trunk", "straight", "diverging"):
                endpoint = turnout.endpoints()[endpoint_name]
                other_id = endpoint.connected_to_track_id

                if other_id is None:
                    continue

                if other_id not in selected_ids:
                    self._clear_turnout_endpoint_connection(turnout, endpoint_name)

    def _collect_group_open_endpoints(
        self,
    ) -> list[tuple[str, str, float, float, float]]:
        endpoints: list[tuple[str, str, float, float, float]] = []

        for track_id in self._group_drag_track_ids:
            track = self.tracks.get(track_id)
            if track is None:
                continue

            for endpoint_name in ("A", "B"):
                endpoint = track.endpoint(endpoint_name)
                if endpoint.connected_to_track_id is not None:
                    continue

                heading_deg = self._endpoint_heading_deg(track, endpoint_name)
                endpoints.append(
                    (
                        track_id,
                        endpoint_name,
                        endpoint.x,
                        endpoint.y,
                        heading_deg,
                    )
                )

        for turnout_id in self._group_drag_turnout_ids:
            turnout = self.turnouts.get(turnout_id)
            if turnout is None:
                continue

            for endpoint_name, endpoint in turnout.endpoints().items():
                if endpoint.connected_to_track_id is not None:
                    continue

                heading_deg = self._turnout_endpoint_heading_deg(turnout, endpoint_name)
                endpoints.append(
                    (
                        turnout_id,
                        endpoint_name,
                        endpoint.x,
                        endpoint.y,
                        heading_deg,
                    )
                )

        return endpoints

    def _collect_external_open_endpoints(
        self,
    ) -> list[tuple[str, str, float, float, float]]:
        endpoints: list[tuple[str, str, float, float, float]] = []

        selected_ids = set(self._group_drag_track_ids) | set(
            self._group_drag_turnout_ids
        )

        for track_id, track in self.tracks.items():
            if track_id in selected_ids:
                continue

            for endpoint_name in ("A", "B"):
                endpoint = track.endpoint(endpoint_name)
                if endpoint.connected_to_track_id is not None:
                    continue

                heading_deg = self._endpoint_heading_deg(track, endpoint_name)
                endpoints.append(
                    (
                        track_id,
                        endpoint_name,
                        endpoint.x,
                        endpoint.y,
                        heading_deg,
                    )
                )

        for turnout_id, turnout in self.turnouts.items():
            if turnout_id in selected_ids:
                continue

            for endpoint_name, endpoint in turnout.endpoints().items():
                if endpoint.connected_to_track_id is not None:
                    continue

                heading_deg = self._turnout_endpoint_heading_deg(turnout, endpoint_name)
                endpoints.append(
                    (
                        turnout_id,
                        endpoint_name,
                        endpoint.x,
                        endpoint.y,
                        heading_deg,
                    )
                )

        return endpoints

    def _get_object_endpoint_world_position(
        self,
        object_id: str,
        endpoint_name: str,
    ) -> tuple[float, float] | None:
        track = self.tracks.get(object_id)
        if track is not None:
            endpoint = track.endpoint(endpoint_name)
            return (endpoint.x, endpoint.y)

        turnout = self.turnouts.get(object_id)
        if turnout is not None:
            endpoint = turnout.endpoints()[endpoint_name]
            return (endpoint.x, endpoint.y)

        return None

    def _connect_designer_endpoints(
        self,
        first_id: str,
        first_endpoint_name: str,
        second_id: str,
        second_endpoint_name: str,
    ) -> None:
        first_track = self.tracks.get(first_id)
        first_turnout = self.turnouts.get(first_id)

        second_track = self.tracks.get(second_id)
        second_turnout = self.turnouts.get(second_id)

        if first_track is not None:
            first_endpoint = first_track.endpoint(first_endpoint_name)
        elif first_turnout is not None:
            first_endpoint = first_turnout.endpoints()[first_endpoint_name]
        else:
            return

        if second_track is not None:
            second_endpoint = second_track.endpoint(second_endpoint_name)
        elif second_turnout is not None:
            second_endpoint = second_turnout.endpoints()[second_endpoint_name]
        else:
            return

        first_endpoint.connected_to_track_id = second_id
        first_endpoint.connected_to_endpoint_name = second_endpoint_name
        second_endpoint.connected_to_track_id = first_id
        second_endpoint.connected_to_endpoint_name = first_endpoint_name

    def _commit_group_smart_snap_if_available(self) -> bool:
        if (
            not self._group_smart_move_active
            or self._group_snap_candidate is None
            or self._group_snap_active_endpoint is None
            or self._group_snap_preview_point is None
        ):
            return False

        target_id, target_endpoint_name = self._group_snap_candidate
        moving_id, moving_endpoint_name = self._group_snap_active_endpoint
        target_x, target_y = self._group_snap_preview_point

        moving_position = self._get_object_endpoint_world_position(
            moving_id,
            moving_endpoint_name,
        )
        if moving_position is None:
            return False

        moving_x, moving_y = moving_position
        dx = target_x - moving_x
        dy = target_y - moving_y

        for track_id in self._group_drag_track_ids:
            track = self.tracks.get(track_id)
            if track is not None:
                track.move_by(dx, dy)

        for turnout_id in self._group_drag_turnout_ids:
            turnout = self.turnouts.get(turnout_id)
            if turnout is not None:
                turnout.x += dx
                turnout.y += dy
                turnout.recalculate_geometry_from_parameters()

        self._connect_designer_endpoints(
            moving_id,
            moving_endpoint_name,
            target_id,
            target_endpoint_name,
        )

        return True

    def _find_best_group_smart_snap_candidate(
        self,
    ) -> tuple[tuple[str, str], tuple[str, str], tuple[float, float]] | None:
        moving_endpoints = self._collect_group_open_endpoints()
        external_endpoints = self._collect_external_open_endpoints()

        best: tuple[tuple[str, str], tuple[str, str], tuple[float, float]] | None = None
        best_distance = float("inf")

        preview_radius = self.SNAP_PREVIEW_RADIUS_PX / max(self.zoom_scale, 0.001)

        for (
            moving_id,
            moving_endpoint_name,
            moving_x,
            moving_y,
            moving_heading,
        ) in moving_endpoints:
            for (
                external_id,
                external_endpoint_name,
                external_x,
                external_y,
                external_heading,
            ) in external_endpoints:
                distance = math.hypot(external_x - moving_x, external_y - moving_y)
                if distance > preview_radius:
                    continue

                if not self._headings_are_compatible(moving_heading, external_heading):
                    continue

                if distance < best_distance:
                    best_distance = distance
                    best = (
                        (external_id, external_endpoint_name),
                        (moving_id, moving_endpoint_name),
                        (external_x, external_y),
                    )

        return best

    def _commit_snap_if_locked(
        self, active_track_id: str, active_endpoint_name: str
    ) -> None:
        if self._snap_locked is None or self._snap_preview_point is None:
            return

        target_track_id, target_endpoint_name = self._snap_locked
        if (
            active_track_id == target_track_id
            and active_endpoint_name == target_endpoint_name
        ):
            return

        active_track = self.tracks[active_track_id]
        snap_x, snap_y = self._snap_preview_point

        target_track = self.tracks.get(target_track_id)
        target_turnout = self.turnouts.get(target_track_id)

        # ----------------------------------------------------------
        # Apply snap geometry
        # ----------------------------------------------------------
        if target_track is not None:
            # Preserve the moving track's current angle and length.
            # Just translate the whole track so the active endpoint lands
            # exactly on the snap point.
            active_endpoint = active_track.endpoint(active_endpoint_name)
            dx = snap_x - active_endpoint.x
            dy = snap_y - active_endpoint.y
            active_track.move_by(dx, dy)

            if self.DEBUG_SNAP:
                # ------------------------------------------------------
                # Debug: verify both endpoints after the move
                # ------------------------------------------------------
                ep_a = active_track.endpoint("A")
                ep_b = active_track.endpoint("B")

                print("AFTER MOVE:")
                print(f"A: ({ep_a.x:.2f}, {ep_a.y:.2f})")
                print(f"B: ({ep_b.x:.2f}, {ep_b.y:.2f})")

        elif target_turnout is not None:
            # Keep tangent alignment behavior for turnout targets for now.
            target_heading_deg = self._turnout_endpoint_heading_deg(
                target_turnout,
                target_endpoint_name,
            )
            self._align_track_endpoint_to_target_tangent(
                track=active_track,
                active_endpoint_name=active_endpoint_name,
                target_heading_deg=target_heading_deg,
                snap_x=snap_x,
                snap_y=snap_y,
            )
        else:
            return

        # ----------------------------------------------------------
        # Clear old connection on active endpoint
        # ----------------------------------------------------------
        self._clear_endpoint_connection(active_track, active_endpoint_name)

        # ----------------------------------------------------------
        # Clear old connection on target endpoint
        # ----------------------------------------------------------
        if target_track is not None:
            target_endpoint = target_track.endpoint(target_endpoint_name)
            self._clear_endpoint_connection(target_track, target_endpoint_name)
        else:
            if target_turnout is None:
                return
            target_endpoint = target_turnout.endpoints()[target_endpoint_name]
            target_endpoint.connected_to_track_id = None
            target_endpoint.connected_to_endpoint_name = None

        # ----------------------------------------------------------
        # Connect both sides
        # ----------------------------------------------------------
        active_endpoint = active_track.endpoint(active_endpoint_name)

        active_endpoint.connected_to_track_id = target_track_id
        active_endpoint.connected_to_endpoint_name = target_endpoint_name
        target_endpoint.connected_to_track_id = active_track_id
        target_endpoint.connected_to_endpoint_name = active_endpoint_name

    def _normalize_angle_deg(self, angle_deg: float) -> float:
        return (angle_deg + 180.0) % 360.0 - 180.0

    def _align_track_endpoint_to_target_tangent(
        self,
        *,
        track: StraightTrackElement,
        active_endpoint_name: str,
        target_heading_deg: float,
        snap_x: float,
        snap_y: float,
    ) -> None:
        """
        Keep the snapped endpoint fixed, preserve track length, and rotate the
        straight segment so it leaves the connection tangent to the target.
        """

        length = track.pixel_length
        heading_rad = math.radians(target_heading_deg)

        free_x = snap_x + (length * math.cos(heading_rad))
        free_y = snap_y + (length * math.sin(heading_rad))

        if active_endpoint_name == "A":
            track.set_endpoint("A", snap_x, snap_y)
            track.set_endpoint("B", free_x, free_y)
            return

        if active_endpoint_name == "B":
            track.set_endpoint("B", snap_x, snap_y)
            track.set_endpoint("A", free_x, free_y)
            return

        raise ValueError(f"Unknown endpoint name: {active_endpoint_name}")

    # new debug code start
    def _commit_turnout_snap_if_locked(
        self,
        turnout_id: str,
        turnout_endpoint_name: str,
    ) -> None:
        self._debug(
            "TURNOUT COMMIT START "
            f"id={turnout_id} endpoint={turnout_endpoint_name} "
            f"snap_locked={self._snap_locked} "
            f"snap_preview={self._snap_preview_point}"
        )

        if self._snap_locked is None or self._snap_preview_point is None:
            self._debug("TURNOUT COMMIT ABORT no locked snap or preview point")
            return

        turnout = self.turnouts[turnout_id]
        turnout_endpoint = turnout.endpoints()[turnout_endpoint_name]

        target_id, target_endpoint_name = self._snap_locked

        if target_id == turnout_id and target_endpoint_name == turnout_endpoint_name:
            self._debug("TURNOUT COMMIT ABORT target is same endpoint")
            return

        target_track = self.tracks.get(target_id)
        target_turnout = self.turnouts.get(target_id)

        if turnout_endpoint.connected_to_track_id is not None:
            old_other_id = turnout_endpoint.connected_to_track_id
            old_other_endpoint_name = turnout_endpoint.connected_to_endpoint_name

            turnout_endpoint.connected_to_track_id = None
            turnout_endpoint.connected_to_endpoint_name = None

            if old_other_id is not None and old_other_endpoint_name is not None:
                old_track = self.tracks.get(old_other_id)
                if old_track is not None:
                    other_endpoint = old_track.endpoint(old_other_endpoint_name)
                    if other_endpoint.connected_to_track_id == turnout_id:
                        other_endpoint.connected_to_track_id = None
                        other_endpoint.connected_to_endpoint_name = None

                old_turnout = self.turnouts.get(old_other_id)
                if old_turnout is not None:
                    other_endpoint = old_turnout.endpoints()[old_other_endpoint_name]
                    if other_endpoint.connected_to_track_id == turnout_id:
                        other_endpoint.connected_to_track_id = None
                        other_endpoint.connected_to_endpoint_name = None

        snap_x, snap_y = self._snap_preview_point

        self._debug(
            "TURNOUT COMMIT APPLY GEOMETRY "
            f"id={turnout_id} endpoint={turnout_endpoint_name} "
            f"snap_point=({snap_x:.2f}, {snap_y:.2f}) "
            f"anchor_before=({turnout.x:.2f}, {turnout.y:.2f}) "
            f"trunk_before=({turnout.trunk.x:.2f}, {turnout.trunk.y:.2f}) "
            f"straight_before=({turnout.straight.x:.2f}, {turnout.straight.y:.2f}) "
            f"diverging_before=({turnout.diverging.x:.2f}, {turnout.diverging.y:.2f})"
        )

        if turnout_endpoint_name == "trunk":
            turnout.x = snap_x
            turnout.y = snap_y
            turnout.recalculate_geometry_from_parameters()

        elif turnout_endpoint_name == "straight":
            dx = snap_x - turnout.trunk.x
            dy = snap_y - turnout.trunk.y
            turnout.angle_deg = math.degrees(math.atan2(dy, dx))
            turnout.straight_len = max(20.0, math.hypot(dx, dy))
            turnout.recalculate_geometry_from_parameters()

        elif turnout_endpoint_name == "diverging":
            dx = snap_x - turnout.split_x
            dy = snap_y - turnout.split_y
            diverge_heading_deg = math.degrees(math.atan2(dy, dx))
            signed_angle = diverge_heading_deg - turnout.angle_deg

            turnout.diverge_angle_deg = max(2.0, abs(signed_angle))
            turnout.diverge_len = max(20.0, math.hypot(dx, dy))
            turnout.recalculate_geometry_from_parameters()

            turnout.diverging.x = snap_x
            turnout.diverging.y = snap_y

        turnout_endpoint = turnout.endpoints()[turnout_endpoint_name]

        self._debug(
            "TURNOUT COMMIT AFTER GEOMETRY "
            f"id={turnout_id} endpoint={turnout_endpoint_name} "
            f"anchor_after=({turnout.x:.2f}, {turnout.y:.2f}) "
            f"trunk_after=({turnout.trunk.x:.2f}, {turnout.trunk.y:.2f}) "
            f"straight_after=({turnout.straight.x:.2f}, {turnout.straight.y:.2f}) "
            f"diverging_after=({turnout.diverging.x:.2f}, {turnout.diverging.y:.2f})"
        )

        if target_track is not None:
            target_endpoint = target_track.endpoint(target_endpoint_name)
            self._clear_endpoint_connection(target_track, target_endpoint_name)

            turnout_endpoint.connected_to_track_id = target_track.track_id
            turnout_endpoint.connected_to_endpoint_name = target_endpoint_name
            target_endpoint.connected_to_track_id = turnout.track_id
            target_endpoint.connected_to_endpoint_name = turnout_endpoint_name

            self._debug(
                "TURNOUT COMMIT COMPLETE target_kind=track "
                f"turnout={turnout_id}:{turnout_endpoint_name} "
                f"target={target_track.track_id}:{target_endpoint_name}"
            )
            return

        if target_turnout is not None:
            target_endpoint = target_turnout.endpoints()[target_endpoint_name]

            if target_endpoint.connected_to_track_id is not None:
                old_other_id = target_endpoint.connected_to_track_id
                old_other_endpoint_name = target_endpoint.connected_to_endpoint_name
                target_endpoint.connected_to_track_id = None
                target_endpoint.connected_to_endpoint_name = None

                if old_other_id is not None and old_other_endpoint_name is not None:
                    old_track = self.tracks.get(old_other_id)
                    if old_track is not None:
                        other_endpoint = old_track.endpoint(old_other_endpoint_name)
                        if (
                            other_endpoint.connected_to_track_id
                            == target_turnout.track_id
                        ):
                            other_endpoint.connected_to_track_id = None
                            other_endpoint.connected_to_endpoint_name = None

                    old_turnout = self.turnouts.get(old_other_id)
                    if old_turnout is not None:
                        other_endpoint = old_turnout.endpoints()[
                            old_other_endpoint_name
                        ]
                        if (
                            other_endpoint.connected_to_track_id
                            == target_turnout.track_id
                        ):
                            other_endpoint.connected_to_track_id = None
                            other_endpoint.connected_to_endpoint_name = None

            turnout_endpoint.connected_to_track_id = target_turnout.track_id
            turnout_endpoint.connected_to_endpoint_name = target_endpoint_name
            target_endpoint.connected_to_track_id = turnout.track_id
            target_endpoint.connected_to_endpoint_name = turnout_endpoint_name

            self._debug(
                "TURNOUT COMMIT COMPLETE target_kind=turnout "
                f"turnout={turnout_id}:{turnout_endpoint_name} "
                f"target={target_turnout.track_id}:{target_endpoint_name}"
            )

    def _commit_moved_turnout_snap_if_locked(
        self,
        turnout_id: str,
        turnout_endpoint_name: str,
    ) -> None:
        self._debug(
            "TURNOUT BODY COMMIT START "
            f"id={turnout_id} endpoint={turnout_endpoint_name} "
            f"snap_locked={self._snap_locked} "
            f"snap_preview={self._snap_preview_point}"
        )

        if self._snap_locked is None or self._snap_preview_point is None:
            self._debug("TURNOUT BODY COMMIT ABORT no locked snap or preview point")
            return

        turnout = self.turnouts[turnout_id]
        turnout_endpoint = turnout.endpoints()[turnout_endpoint_name]

        target_id, target_endpoint_name = self._snap_locked

        if target_id == turnout_id and target_endpoint_name == turnout_endpoint_name:
            self._debug("TURNOUT BODY COMMIT ABORT target is same endpoint")
            return

        target_track = self.tracks.get(target_id)
        target_turnout = self.turnouts.get(target_id)

        # Clear existing connection on the moving turnout endpoint first.
        if turnout_endpoint.connected_to_track_id is not None:
            old_other_id = turnout_endpoint.connected_to_track_id
            old_other_endpoint_name = turnout_endpoint.connected_to_endpoint_name

            turnout_endpoint.connected_to_track_id = None
            turnout_endpoint.connected_to_endpoint_name = None

            if old_other_id is not None and old_other_endpoint_name is not None:
                old_track = self.tracks.get(old_other_id)
                if old_track is not None:
                    other_endpoint = old_track.endpoint(old_other_endpoint_name)
                    if other_endpoint.connected_to_track_id == turnout_id:
                        other_endpoint.connected_to_track_id = None
                        other_endpoint.connected_to_endpoint_name = None

                old_turnout = self.turnouts.get(old_other_id)
                if old_turnout is not None:
                    other_endpoint = old_turnout.endpoints()[old_other_endpoint_name]
                    if other_endpoint.connected_to_track_id == turnout_id:
                        other_endpoint.connected_to_track_id = None
                        other_endpoint.connected_to_endpoint_name = None

        snap_x, snap_y = self._snap_preview_point

        dx = snap_x - turnout_endpoint.x
        dy = snap_y - turnout_endpoint.y

        self._debug(
            "TURNOUT BODY COMMIT TRANSLATE "
            f"id={turnout_id} endpoint={turnout_endpoint_name} "
            f"endpoint_before=({turnout_endpoint.x:.2f}, {turnout_endpoint.y:.2f}) "
            f"snap_point=({snap_x:.2f}, {snap_y:.2f}) "
            f"delta=({dx:.2f}, {dy:.2f}) "
            f"anchor_before=({turnout.x:.2f}, {turnout.y:.2f}) "
            f"trunk_before=({turnout.trunk.x:.2f}, {turnout.trunk.y:.2f}) "
            f"straight_before=({turnout.straight.x:.2f}, {turnout.straight.y:.2f}) "
            f"diverging_before=({turnout.diverging.x:.2f}, {turnout.diverging.y:.2f})"
        )

        # Rigid-body move only. No rotation here.
        turnout.x += dx
        turnout.y += dy
        turnout.recalculate_geometry_from_parameters()

        turnout_endpoint = turnout.endpoints()[turnout_endpoint_name]

        self._debug(
            "TURNOUT BODY COMMIT AFTER TRANSLATE "
            f"id={turnout_id} endpoint={turnout_endpoint_name} "
            f"anchor_after=({turnout.x:.2f}, {turnout.y:.2f}) "
            f"trunk_after=({turnout.trunk.x:.2f}, {turnout.trunk.y:.2f}) "
            f"straight_after=({turnout.straight.x:.2f}, {turnout.straight.y:.2f}) "
            f"diverging_after=({turnout.diverging.x:.2f}, {turnout.diverging.y:.2f})"
        )

        if target_track is not None:
            target_endpoint = target_track.endpoint(target_endpoint_name)
            self._clear_endpoint_connection(target_track, target_endpoint_name)

            turnout_endpoint.connected_to_track_id = target_track.track_id
            turnout_endpoint.connected_to_endpoint_name = target_endpoint_name
            target_endpoint.connected_to_track_id = turnout.track_id
            target_endpoint.connected_to_endpoint_name = turnout_endpoint_name

            self._debug(
                "TURNOUT BODY COMMIT COMPLETE target_kind=track "
                f"turnout={turnout_id}:{turnout_endpoint_name} "
                f"target={target_track.track_id}:{target_endpoint_name}"
            )
            return

        if target_turnout is not None:
            target_endpoint = target_turnout.endpoints()[target_endpoint_name]

            if target_endpoint.connected_to_track_id is not None:
                old_other_id = target_endpoint.connected_to_track_id
                old_other_endpoint_name = target_endpoint.connected_to_endpoint_name
                target_endpoint.connected_to_track_id = None
                target_endpoint.connected_to_endpoint_name = None

                if old_other_id is not None and old_other_endpoint_name is not None:
                    old_track = self.tracks.get(old_other_id)
                    if old_track is not None:
                        other_endpoint = old_track.endpoint(old_other_endpoint_name)
                        if (
                            other_endpoint.connected_to_track_id
                            == target_turnout.track_id
                        ):
                            other_endpoint.connected_to_track_id = None
                            other_endpoint.connected_to_endpoint_name = None

                    old_turnout = self.turnouts.get(old_other_id)
                    if old_turnout is not None:
                        other_endpoint = old_turnout.endpoints()[
                            old_other_endpoint_name
                        ]
                        if (
                            other_endpoint.connected_to_track_id
                            == target_turnout.track_id
                        ):
                            other_endpoint.connected_to_track_id = None
                            other_endpoint.connected_to_endpoint_name = None

            turnout_endpoint.connected_to_track_id = target_turnout.track_id
            turnout_endpoint.connected_to_endpoint_name = target_endpoint_name
            target_endpoint.connected_to_track_id = turnout.track_id
            target_endpoint.connected_to_endpoint_name = turnout_endpoint_name

            self._debug(
                "TURNOUT BODY COMMIT COMPLETE target_kind=turnout "
                f"turnout={turnout_id}:{turnout_endpoint_name} "
                f"target={target_turnout.track_id}:{target_endpoint_name}"
            )

    def _end_drag(self) -> None:
        self._drag_mode = None
        self._drag_track_id = None
        self._drag_endpoint_name = None
        self._drag_last_world = None
        self._create_track_id = None
        self._rotate_turnout_id = None
        self._rotate_pivot_world = None
        self._rotate_start_mouse_angle_deg = None
        self._rotate_start_turnout_angle_deg = None

        self._snap_candidate = None
        self._snap_candidate_since = None
        self._snap_locked = None
        self._snap_preview_point = None

        self._marquee_start_world = None
        self._marquee_end_world = None

        self._group_drag_track_ids.clear()
        self._group_drag_turnout_ids.clear()
        self._group_smart_move_active = False
        self._group_snap_candidate = None
        self._group_snap_preview_point = None
        self._group_snap_active_endpoint = None

    # ------------------------------------------------------------------
    # Snapping
    # ------------------------------------------------------------------
    def _update_snap_state(
        self,
        *,
        active_track_id: str,
        active_endpoint_name: str,
        active_x: float,
        active_y: float,
    ) -> None:
        candidate = self._find_snap_candidate(
            active_track_id=active_track_id,
            active_endpoint_name=active_endpoint_name,
            active_x=active_x,
            active_y=active_y,
        )

        now = time.monotonic()

        if candidate is None:
            self._snap_candidate = None
            self._snap_candidate_since = None
            self._snap_locked = None
            self._snap_preview_point = None
            return

        (
            candidate_track_id,
            candidate_endpoint_name,
            candidate_x,
            candidate_y,
            _candidate_kind,
        ) = candidate

        candidate_key = (
            candidate_track_id,
            candidate_endpoint_name,
        )
        candidate_point = (
            candidate_x,
            candidate_y,
        )

        if self._snap_candidate != candidate_key:
            self._snap_candidate = candidate_key
            self._snap_candidate_since = now
            self._snap_locked = None
            self._snap_preview_point = candidate_point
            return

        self._snap_preview_point = candidate_point
        if (
            self._snap_candidate_since is not None
            and (now - self._snap_candidate_since) >= self.SNAP_DWELL_SECONDS
        ):
            self._snap_locked = candidate_key
            self._set_status(
                f"Snap locked: {active_track_id}:{active_endpoint_name} ->"
                f"{candidate_track_id}:{candidate_endpoint_name}"
            )
        else:
            self._snap_locked = None

    def _find_snap_candidate(
        self,
        *,
        active_track_id: str,
        active_endpoint_name: str,
        active_x: float,
        active_y: float,
    ) -> tuple[str, str, float, float, str] | None:

        best: tuple[str, str, float, float, str] | None = None
        best_distance = float("inf")

        active_track = self.tracks[active_track_id]
        active_heading = self._endpoint_heading_deg(active_track, active_endpoint_name)

        # ----------------------------------------------------------
        # Track endpoints as snap targets
        #
        # For track-to-track snapping, allow the cue based on proximity.
        # Final alignment is handled during commit by
        # _align_track_endpoint_to_target_tangent().
        # ----------------------------------------------------------
        for track in self.tracks.values():
            if track.track_id == active_track_id:
                continue

            for endpoint_name in ("A", "B"):
                endpoint = track.endpoint(endpoint_name)
                distance = math.hypot(endpoint.x - active_x, endpoint.y - active_y)
                if distance > self.SNAP_PREVIEW_RADIUS_PX / max(self.zoom_scale, 0.001):
                    continue

                if distance < best_distance:
                    best_distance = distance
                    best = (
                        track.track_id,
                        endpoint_name,
                        endpoint.x,
                        endpoint.y,
                        "track",
                    )

        # ----------------------------------------------------------
        # Turnout endpoints as snap targets
        #
        # Keep existing heading compatibility behavior for now.
        # ----------------------------------------------------------
        for turnout in self.turnouts.values():
            turnout_targets = {
                "trunk": turnout.trunk,
                "straight": turnout.straight,
                "diverging": turnout.diverging,
            }

            turnout_headings = {
                "trunk": self._turnout_endpoint_heading_deg(turnout, "trunk"),
                "straight": self._turnout_endpoint_heading_deg(turnout, "straight"),
                "diverging": self._turnout_endpoint_heading_deg(turnout, "diverging"),
            }

            for endpoint_name, endpoint in turnout_targets.items():
                distance = math.hypot(endpoint.x - active_x, endpoint.y - active_y)
                if distance > self.SNAP_PREVIEW_RADIUS_PX / max(self.zoom_scale, 0.001):
                    continue

                candidate_heading = turnout_headings[endpoint_name]
                if not self._headings_are_compatible(active_heading, candidate_heading):
                    continue

                if distance < best_distance:
                    best_distance = distance
                    best = (
                        turnout.track_id,
                        endpoint_name,
                        endpoint.x,
                        endpoint.y,
                        "turnout",
                    )

        if best is None:
            self._set_status(
                f"No snap candidate for {active_track_id}:{active_endpoint_name}"
            )
            return None

        return best

    def _find_best_snap_for_moved_track(
        self,
        track: StraightTrackElement,
    ) -> tuple[str, str, str, float, float] | None:
        best: tuple[str, str, str, float, float] | None = None
        best_distance = float("inf")

        for active_endpoint_name in ("A", "B"):
            active_endpoint = track.endpoint(active_endpoint_name)
            candidate = self._find_snap_candidate(
                active_track_id=track.track_id,
                active_endpoint_name=active_endpoint_name,
                active_x=active_endpoint.x,
                active_y=active_endpoint.y,
            )
            if candidate is None:
                continue

            (
                candidate_track_id,
                candidate_endpoint_name,
                candidate_x,
                candidate_y,
                _candidate_kind,
            ) = candidate

            distance = math.hypot(
                candidate_x - active_endpoint.x,
                candidate_y - active_endpoint.y,
            )

            if distance < best_distance:
                best_distance = distance
                best = (
                    active_endpoint_name,
                    candidate_track_id,
                    candidate_endpoint_name,
                    candidate_x,
                    candidate_y,
                )

        return best

    def _endpoint_heading_deg(
        self, track: StraightTrackElement, endpoint_name: str
    ) -> float:
        if endpoint_name == "A":
            return math.degrees(math.atan2(track.y1 - track.y2, track.x1 - track.x2))
        return math.degrees(math.atan2(track.y2 - track.y1, track.x2 - track.x1))

    def _turnout_endpoint_heading_deg(
        self,
        turnout: TurnoutTrackElement,
        endpoint_name: str,
    ) -> float:
        signed_diverge_angle = (
            turnout.diverge_angle_deg
            if turnout.hand == "right"
            else -turnout.diverge_angle_deg
        )

        if endpoint_name == "trunk":
            return turnout.angle_deg + 180.0

        if endpoint_name == "straight":
            return turnout.angle_deg

        if endpoint_name == "diverging":
            return turnout.angle_deg + signed_diverge_angle

        raise ValueError(f"Unknown turnout endpoint name: {endpoint_name}")

    # new debug code
    def _update_turnout_snap_state(
        self,
        *,
        turnout_id: str,
        endpoint_name: str,
        active_x: float,
        active_y: float,
    ) -> None:
        turnout = self.turnouts[turnout_id]
        active_heading = self._turnout_endpoint_heading_deg(turnout, endpoint_name)

        self._debug(
            "TURNOUT SNAP CHECK START "
            f"id={turnout_id} endpoint={endpoint_name} "
            f"active=({active_x:.2f}, {active_y:.2f}) "
            f"active_heading={active_heading:.2f}"
        )

        best: tuple[str, str, float, float, str] | None = None
        best_distance = float("inf")

        preview_radius = self.SNAP_PREVIEW_RADIUS_PX / max(self.zoom_scale, 0.001)

        for track in self.tracks.values():
            for candidate_endpoint_name in ("A", "B"):
                endpoint = track.endpoint(candidate_endpoint_name)
                distance = math.hypot(endpoint.x - active_x, endpoint.y - active_y)
                candidate_heading = self._endpoint_heading_deg(
                    track,
                    candidate_endpoint_name,
                )

                if endpoint_name == "diverging":
                    headings_ok = True
                else:
                    headings_ok = self._headings_are_compatible(
                        active_heading,
                        candidate_heading,
                    )

                self._debug(
                    "TURNOUT SNAP VS TRACK "
                    f"turnout={turnout_id}:{endpoint_name} "
                    f"target={track.track_id}:{candidate_endpoint_name} "
                    f"target_point=({endpoint.x:.2f}, {endpoint.y:.2f}) "
                    f"distance={distance:.2f} "
                    f"preview_radius={preview_radius:.2f} "
                    f"candidate_heading={candidate_heading:.2f} "
                    f"headings_ok={headings_ok}"
                )

                if distance > preview_radius:
                    continue

                if not headings_ok:
                    continue

                if distance < best_distance:
                    best_distance = distance
                    best = (
                        track.track_id,
                        candidate_endpoint_name,
                        endpoint.x,
                        endpoint.y,
                        "track",
                    )

        for other_turnout in self.turnouts.values():
            if other_turnout.track_id == turnout_id:
                continue

            for candidate_endpoint_name, endpoint in other_turnout.endpoints().items():
                distance = math.hypot(endpoint.x - active_x, endpoint.y - active_y)
                candidate_heading = self._turnout_endpoint_heading_deg(
                    other_turnout,
                    candidate_endpoint_name,
                )

                if endpoint_name == "diverging":
                    headings_ok = True
                else:
                    headings_ok = self._headings_are_compatible(
                        active_heading,
                        candidate_heading,
                    )

                self._debug(
                    "TURNOUT SNAP VS TURNOUT "
                    f"turnout={turnout_id}:{endpoint_name} "
                    f"target={other_turnout.track_id}:{candidate_endpoint_name} "
                    f"target_point=({endpoint.x:.2f}, {endpoint.y:.2f}) "
                    f"distance={distance:.2f} "
                    f"preview_radius={preview_radius:.2f} "
                    f"candidate_heading={candidate_heading:.2f} "
                    f"headings_ok={headings_ok}"
                )

                if distance > preview_radius:
                    continue

                if not headings_ok:
                    continue

                if distance < best_distance:
                    best_distance = distance
                    best = (
                        other_turnout.track_id,
                        candidate_endpoint_name,
                        endpoint.x,
                        endpoint.y,
                        "turnout",
                    )

        if best is None:
            self._debug(
                "TURNOUT SNAP CHECK RESULT "
                f"id={turnout_id} endpoint={endpoint_name} result=None"
            )
            self._snap_candidate = None
            self._snap_candidate_since = None
            self._snap_locked = None
            self._snap_preview_point = None
            return

        (
            candidate_track_id,
            candidate_endpoint_name,
            candidate_x,
            candidate_y,
            candidate_kind,
        ) = best

        candidate_key = (candidate_track_id, candidate_endpoint_name)
        candidate_point = (candidate_x, candidate_y)

        self._snap_candidate = candidate_key
        self._snap_candidate_since = time.monotonic()
        self._snap_locked = candidate_key
        self._snap_preview_point = candidate_point

        self._debug(
            "TURNOUT SNAP CHECK RESULT "
            f"id={turnout_id} endpoint={endpoint_name} "
            f"best_kind={candidate_kind} "
            f"best_target={candidate_track_id}:{candidate_endpoint_name} "
            f"best_point=({candidate_x:.2f}, {candidate_y:.2f}) "
            f"best_distance={best_distance:.2f}"
        )

        self._set_status(
            f"Snap locked: {turnout_id}:{endpoint_name} -> "
            f"{candidate_track_id}:{candidate_endpoint_name}"
        )

    def _headings_are_compatible(self, heading_a: float, heading_b: float) -> bool:
        diff = abs((heading_a - heading_b + 180.0) % 360.0 - 180.0)

        # Endpoints should generally face each other to form a straight
        # continuation, so compatibility is based on being near 180° apart.
        return abs(diff - 180.0) <= self.ANGLE_COMPATIBILITY_DEG

    def _snap_angle(self, angle_deg: float, increment_deg: float) -> float:
        if increment_deg <= 0.0:
            return angle_deg
        return round(angle_deg / increment_deg) * increment_deg

    # ------------------------------------------------------------------
    # Hit testing / coordinates
    # ------------------------------------------------------------------
    def _hit_test(self, world_x: float, world_y: float) -> dict[str, str] | None:
        # ----------------------------------------------------------
        # TURNOUT rotate handle hit (highest priority)
        # ----------------------------------------------------------
        for turnout_id in reversed(self.turnout_order):
            turnout = self.turnouts[turnout_id]
            if turnout.track_id != self.selected_turnout_id:
                continue

            handle_x, handle_y = self._turnout_rotate_handle_world_position(turnout)
            if math.hypot(handle_x - world_x, handle_y - world_y) <= (
                self.TURNOUT_ROTATE_HANDLE_RADIUS_PX + 4.0
            ) / max(self.zoom_scale, 0.001):
                return {
                    "type": "turnout",
                    "turnout_id": turnout_id,
                    "part": "rotate_handle",
                    "endpoint_name": "",
                }

        # ----------------------------------------------------------
        # TURNOUT endpoint hit
        # ----------------------------------------------------------
        for turnout_id in reversed(self.turnout_order):
            turnout = self.turnouts[turnout_id]

            for endpoint_name, endpoint in turnout.endpoints().items():
                if math.hypot(
                    endpoint.x - world_x,
                    endpoint.y - world_y,
                ) <= self.ENDPOINT_HIT_RADIUS_PX / max(self.zoom_scale, 0.001):
                    return {
                        "type": "turnout",
                        "turnout_id": turnout_id,
                        "part": "endpoint",
                        "endpoint_name": endpoint_name,
                    }

        # ----------------------------------------------------------
        # TRACK endpoint hit
        # ----------------------------------------------------------
        for track_id in reversed(self.track_order):
            track = self.tracks[track_id]
            for endpoint_name in ("A", "B"):
                endpoint = track.endpoint(endpoint_name)
                if math.hypot(
                    endpoint.x - world_x, endpoint.y - world_y
                ) <= self.ENDPOINT_HIT_RADIUS_PX / max(self.zoom_scale, 0.001):
                    return {
                        "type": "track",
                        "track_id": track_id,
                        "part": "endpoint",
                        "endpoint_name": endpoint_name,
                    }

        # ----------------------------------------------------------
        # TURNOUT body hit (distance to either leg)
        # ----------------------------------------------------------
        for turnout_id in reversed(self.turnout_order):
            turnout = self.turnouts[turnout_id]

            split_point = TurnoutEndpoint(
                role="split",
                x=turnout.split_x,
                y=turnout.split_y,
            )

            legs = [
                (turnout.trunk, split_point),
                (split_point, turnout.straight),
                (split_point, turnout.diverging),
            ]

            for start, end in legs:
                distance = self._distance_point_to_segment(
                    world_x,
                    world_y,
                    start.x,
                    start.y,
                    end.x,
                    end.y,
                )

                if distance <= (self.TRACK_GAUGE_PX + 12.0) / max(
                    self.zoom_scale, 0.001
                ):
                    return {
                        "type": "turnout",
                        "turnout_id": turnout_id,
                        "part": "body",
                        "endpoint_name": "",
                    }

        # ----------------------------------------------------------
        # TRACK body hit
        # ----------------------------------------------------------
        for track_id in reversed(self.track_order):
            track = self.tracks[track_id]
            distance = self._distance_point_to_segment(
                world_x, world_y, track.x1, track.y1, track.x2, track.y2
            )
            if distance <= (self.TRACK_GAUGE_PX + 12.0) / max(self.zoom_scale, 0.001):
                return {
                    "type": "track",
                    "track_id": track_id,
                    "part": "body",
                    "endpoint_name": "",
                }

        return None

    def _distance_point_to_segment(
        self,
        px: float,
        py: float,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
    ) -> float:
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(px - x1, py - y1)

        t = ((px - x1) * dx + (py - y1) * dy) / ((dx * dx) + (dy * dy))
        t = max(0.0, min(1.0, t))
        proj_x = x1 + (t * dx)
        proj_y = y1 + (t * dy)
        return math.hypot(px - proj_x, py - proj_y)

    def _world_to_screen(self, x: float, y: float) -> tuple[float, float]:
        return x * self.zoom_scale, y * self.zoom_scale

    def _screen_to_world(self, x: float, y: float) -> tuple[float, float]:
        return x / self.zoom_scale, y / self.zoom_scale

    def _event_world(self, event: tk.Event) -> tuple[float, float]:
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        return self._screen_to_world(canvas_x, canvas_y)

    def _apply_grid_snap(self, x: float, y: float) -> tuple[float, float]:
        if not self.snap_to_grid.get():
            return x, y
        spacing = float(self.GRID_SPACING)
        return round(x / spacing) * spacing, round(y / spacing) * spacing

    def _track_screen_bbox(
        self, track: StraightTrackElement
    ) -> tuple[float, float, float, float]:
        sx1, sy1 = self._world_to_screen(track.x1, track.y1)
        sx2, sy2 = self._world_to_screen(track.x2, track.y2)
        return (
            min(sx1, sx2),
            min(sy1, sy2),
            max(sx1, sx2),
            max(sy1, sy2),
        )

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------
    def _zoom_at_canvas_center(self, factor: float) -> None:
        self._zoom_at(
            self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2, factor
        )

    def _zoom_at(self, screen_x: int, screen_y: int, factor: float) -> None:
        old_zoom = self.zoom_scale
        new_zoom = max(self.ZOOM_MIN, min(self.ZOOM_MAX, old_zoom * factor))
        if abs(new_zoom - old_zoom) < 1e-9:
            return

        world_x, world_y = self._screen_to_world(
            self.canvas.canvasx(screen_x), self.canvas.canvasy(screen_y)
        )
        self.zoom_scale = new_zoom
        self.canvas.configure(
            scrollregion=(0, 0, 4000 * self.zoom_scale, 2600 * self.zoom_scale)
        )

        target_canvas_x = world_x * self.zoom_scale
        target_canvas_y = world_y * self.zoom_scale
        self.canvas.xview_moveto(
            max(0.0, (target_canvas_x - screen_x) / max(1.0, 4000 * self.zoom_scale))
        )
        self.canvas.yview_moveto(
            max(0.0, (target_canvas_y - screen_y) / max(1.0, 2600 * self.zoom_scale))
        )

        self._refresh_canvas()
        self._set_status(f"Zoom: {self.zoom_scale:.2f}x")

    def _reset_zoom(self) -> None:
        self.zoom_scale = 1.0
        self.canvas.configure(scrollregion=(0, 0, 4000, 2600))
        self._refresh_canvas()
        self._set_status("Zoom reset.")

    # ------------------------------------------------------------------
    # Inspector / tooltip / status
    # ------------------------------------------------------------------
    def _show_track_fields(self) -> None:
        self.turnout_field_frame.pack_forget()
        self.track_fields_frame.pack(fill="x", expand=False, before=self.inspector_body)

    def _show_turnout_fields(self) -> None:
        self.track_fields_frame.pack_forget()
        self.turnout_field_frame.pack(
            fill="x", expand=False, before=self.inspector_body
        )

    def _update_inspector(self, track: StraightTrackElement | None) -> None:
        if track is None:
            self._show_track_fields()
            self.inspector_header.config(text="No Selection")
            self.track_type_var.set("mainline")
            self.traffic_rule_var.set(TrackTrafficRule.BIDIRECTIONAL.value)
            self.name_entry_var.set("")
            text = (
                "Select a track to inspect it.\n\n"
                "V2 focus:\n"
                "• Straight track placement by drag\n"
                "• Two-rail rendering\n"
                "• Endpoint handles\n"
                "• Intent-based magnetic snapping\n"
                "• Scroll + zoom design board"
            )
        else:
            self._show_track_fields()
            self.inspector_header.config(text=track.name)
            self.name_entry_var.set(track.name)
            self.track_type_var.set(track.track_type.value)
            self.traffic_rule_var.set(track.traffic_rule.value)
            text = (
                f"Track ID: {track.track_id}\n"
                f"Name: {track.name}\n"
                f"Type: {track.track_type.value}\n"
                f"Length (ft): {track.length_ft:.1f}\n"
                f"Traffic Rule: {track.traffic_rule.value}\n"
                f"Condition: {track.condition}\n\n"
                f"Endpoint A: ({track.x1:.1f}, {track.y1:.1f})\n"
                f"Endpoint B: ({track.x2:.1f}, {track.y2:.1f})\n"
                f"Pixel Length: {track.pixel_length:.1f}\n"
                f"Angle: {track.angle_deg:.1f}°\n\n"
                f"Elevation A: {track.elevation_start_ft:.2f} ft\n"
                f"Elevation B: {track.elevation_end_ft:.2f} ft\n"
                f"Grade: {track.grade_percent:.2f}%\n\n"
                f"Connection A: {self._connection_summary(track, 'A')}\n"
                f"Connection A Class: {self._connection_classification(track, 'A')}\n"
                f"Connection B: {self._connection_summary(track, 'B')}\n"
                f"Connection B Class: {self._connection_classification(track, 'B')}"
            )

        self.inspector_body.config(state="normal")
        self.inspector_body.delete("1.0", "end")
        self.inspector_body.insert("1.0", text)
        self.inspector_body.config(state="disabled")

    def _update_turnout_inspector(self, turnout: TurnoutTrackElement | None) -> None:
        if turnout is None:
            self.inspector_header.config(text="No Selection")
            self._show_turnout_fields()
            self.name_entry_var.set("")
            self._turnout_hand_var.set("right")
            self._turnout_clearance_var.set("150.0")
            self._turnout_diverge_angle_var.set("14.0")
            self._turnout_straight_len_var.set("100.0")
            text = (
                "Select a turnout to inspect it.\n\n"
                "Turnout focus:\n"
                "• Handedness (left/right)\n"
                "• Clearance length for future fouling support\n"
                "• Trunk / straight / diverging endpoints\n"
                "• Designer-side turnout authoring"
            )
        else:
            self.inspector_header.config(text=turnout.name)
            self._show_turnout_fields()
            self.name_entry_var.set(turnout.name)
            self._turnout_hand_var.set(turnout.hand)
            self._turnout_clearance_var.set(f"{turnout.clearance_length_ft:.1f}")
            self._turnout_diverge_angle_var.set(f"{turnout.diverge_angle_deg:.1f}")
            self._turnout_straight_len_var.set(f"{turnout.straight_len:.1f}")

            text = (
                f"Turnout ID: {turnout.track_id}\n"
                f"Name: {turnout.name}\n"
                f"Hand: {turnout.hand}\n"
                f"Clearance Length (ft): {turnout.clearance_length_ft:.1f}\n"
                f"Diverge Angle (deg): {turnout.diverge_angle_deg:.1f}\n"
                f"Straight Length (ft): {turnout.straight_len:.1f}\n"
                f"Angle: {turnout.angle_deg:.1f}°\n\n"
                f"Trunk: ({turnout.trunk.x:.1f}, {turnout.trunk.y:.1f})\n"
                f"Straight: ({turnout.straight.x:.1f}, {turnout.straight.y:.1f})\n"
                f"Diverging: ({turnout.diverging.x:.1f}, {turnout.diverging.y:.1f})\n\n"
                f"Trunk Connection: "
                f"{turnout.trunk.connected_to_track_id or 'Open'}\n"
                f"Straight Connection: "
                f"{turnout.straight.connected_to_track_id or 'Open'}\n"
                f"Diverging Connection: "
                f"{turnout.diverging.connected_to_track_id or 'Open'}"
            )

        self.inspector_body.config(state="normal")
        self.inspector_body.delete("1.0", "end")
        self.inspector_body.insert("1.0", text)
        self.inspector_body.config(state="disabled")

    def _collect_connection_pairs(self) -> list[tuple[str, str, str]]:
        """
        Returns a list of unique connection pairs.

        Each item:
            (track_name_A:endpoint, track_name_B:endpoint, classification)

        Ensures each connection is only reported once.
        """

        seen: set[tuple[tuple[str, str], tuple[str, str]]] = set()
        results: list[tuple[str, str, str]] = []

        for track in self.tracks.values():
            for endpoint_name in ("A", "B"):
                endpoint = track.endpoint(endpoint_name)

                if (
                    endpoint.connected_to_track_id is None
                    or endpoint.connected_to_endpoint_name is None
                ):
                    continue

                other = self.tracks.get(endpoint.connected_to_track_id)
                if other is None:
                    continue

                other_endpoint_name = endpoint.connected_to_endpoint_name

                # Build a normalized key so A->B and B->A don't duplicate
                key_items = sorted(
                    [
                        (track.track_id, endpoint_name),
                        (other.track_id, other_endpoint_name),
                    ]
                )
                key: tuple[tuple[str, str], tuple[str, str]] = (
                    key_items[0],
                    key_items[1],
                )

                if key in seen:
                    continue

                seen.add(key)

                classification = self._connection_classification(track, endpoint_name)

                label_a = f"{track.name}:{endpoint_name}"
                label_b = f"{other.name}:{other_endpoint_name}"

                results.append((label_a, label_b, classification))

        return results

    def _connection_summary(
        self, track: StraightTrackElement, endpoint_name: str
    ) -> str:
        endpoint = track.endpoint(endpoint_name)
        if (
            endpoint.connected_to_track_id is None
            or endpoint.connected_to_endpoint_name is None
        ):
            return "Open"

        other = self.tracks.get(endpoint.connected_to_track_id)
        if other is None:
            return "Open"

        return f"{other.name}:{endpoint.connected_to_endpoint_name}"

    def _connection_classification(
        self, track: StraightTrackElement, endpoint_name: str
    ) -> str:
        endpoint = track.endpoint(endpoint_name)
        if (
            endpoint.connected_to_track_id is None
            or endpoint.connected_to_endpoint_name is None
        ):
            return "open"

        other = self.tracks.get(endpoint.connected_to_track_id)
        if other is None:
            return "open"

        this_heading = self._endpoint_heading_deg(track, endpoint_name)
        other_heading = self._endpoint_heading_deg(
            other, endpoint.connected_to_endpoint_name
        )

        diff = abs((this_heading - other_heading + 180.0) % 360.0 - 180.0)

        # Straight continuation: endpoints face each other.
        if abs(diff - 180.0) <= 12.0:
            return "continuation"

        # Moderate angle away from straight-through suggests turnout-like branch.
        if abs(diff - 180.0) <= 45.0:
            return "turnout_candidate"

        # Large deviation from straight-through.
        if diff <= 100.0:
            return "crossing_candidate"

        return "unknown"

    def _connection_overlay_color(self, classification: str) -> str:
        color_map = {
            "continuation": "#2f9e44",
            "turnout_candidate": "#d97706",
            "crossing_candidate": "#c92a2a",
            "unknown": "#6b7289",
            "open": "#6b7289",
        }
        return color_map.get(classification, "#6b7289")

    def _tooltip_text_for_hit(self, hit: dict[str, str]) -> str:
        if hit["type"] == "track":
            track = self.tracks[hit["track_id"]]

            if hit["part"] == "endpoint":
                endpoint_name = hit["endpoint_name"]
                classification = self._connection_classification(track, endpoint_name)
                return (
                    f"{track.name} endpoint {endpoint_name}\n"
                    f"Connected: {self._connection_summary(track, endpoint_name)}\n"
                    f"Classification: {classification}\n"
                    f"Ctrl+drag or drag to reshape"
                )

            return (
                f"{track.name}\n"
                f"Length: {track.length_ft:.1f} ft\n"
                f"Angle: {track.angle_deg:.1f}°\n"
                f"Drag body to move"
            )

        turnout = self.turnouts[hit["turnout_id"]]

        if hit["part"] == "endpoint":
            endpoint_name = hit["endpoint_name"]
            return (
                f"{turnout.name} endpoint {endpoint_name}\n"
                f"Hand: {turnout.hand}\n"
                f"Diverge Angle: {turnout.diverge_angle_deg:.1f}°\n"
                f"Drag to reshape turnout geometry"
            )

        return (
            f"{turnout.name}\n"
            f"Hand: {turnout.hand}\n"
            f"Straight Length: {turnout.straight_len:.1f} ft\n"
            f"Diverge Angle: {turnout.diverge_angle_deg:.1f}°\n"
            f"Drag body to move"
        )

    def _schedule_tooltip(self, x_root: int, y_root: int, text: str) -> None:
        self._cancel_tooltip_timer()
        self._tooltip_after_id = self.root.after(
            350, lambda: self.tooltip.show(x_root, y_root, text)
        )

    def _cancel_tooltip_timer(self) -> None:
        if self._tooltip_after_id is not None:
            self.root.after_cancel(self._tooltip_after_id)
            self._tooltip_after_id = None

    def _set_status(self, message: str) -> None:
        self.status_var.set(message)

    def _debug(self, message: str) -> None:
        line = f"[layout debug] {message}"

        try:
            with self._debug_log_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

    def _debug_point(self, label: str, x: float, y: float) -> str:
        return f"{label}=({x:2f}, {y:2f})"

    # ------------------------------------------------------------------
    # Menu commands
    # ------------------------------------------------------------------

    def _validate_layout(self) -> None:
        pairs = self._collect_connection_pairs()
        flagged = [pair for pair in pairs if pair[2] != "continuation"]

        classification_counts = {
            "continuation": 0,
            "turnout_candidate": 0,
            "crossing_candidate": 0,
            "unknown": 0,
        }

        for _, _, classification in pairs:
            if classification in classification_counts:
                classification_counts[classification] += 1
            else:
                classification_counts["unknown"] += 1

        lines: list[str] = []
        lines.append("Layout Validation Report")
        lines.append("")
        lines.append(f"Tracks: {len(self.tracks)}")
        lines.append(f"Connections reviewed: {len(pairs)}")
        lines.append(f"Flagged connections: {len(flagged)}")
        lines.append("")

        lines.append("Classification Summary")
        lines.append("----------------------")
        lines.append(f"continuation: {classification_counts['continuation']}")
        lines.append(f"turnout_candidate: {classification_counts['turnout_candidate']}")
        lines.append(
            f"crossing_candidate: {classification_counts['crossing_candidate']}"
        )
        lines.append(f"unknown: {classification_counts['unknown']}")
        lines.append("")

        if not flagged:
            lines.append("All connections are valid (continuation).")
            self._set_status("Layout validation passed.")
        else:
            lines.append("Flagged Items")
            lines.append("-------------")
            for label_a, label_b, classification in flagged:
                lines.append(f"{label_a} -> {label_b} [{classification}]")

            lines.append("")
            lines.append("Notes")
            lines.append("-----")
            lines.append("• continuation = straight-through connection")
            lines.append("• turnout_candidate = likely future switch geometry")
            lines.append("• crossing_candidate = strong angular conflict")
            lines.append("• unknown = connected but not clearly categorized")

            self._set_status(
                f"Layout validation found {len(flagged)} flagged connection(s)."
            )

        report_text = "\n".join(lines)

        self.inspector_header.config(text="Validation Report")
        self.name_entry_var.set("")
        self.track_type_var.set(TrackType.MAINLINE.value)
        self.traffic_rule_var.set(TrackTrafficRule.BIDIRECTIONAL.value)

        self.inspector_body.config(state="normal")
        self.inspector_body.delete("1.0", "end")
        self.inspector_body.insert("1.0", report_text)
        self.inspector_body.config(state="disabled")

    def _new_layout(self) -> None:
        self.tracks.clear()
        self.track_order.clear()
        self.turnouts.clear()
        self.turnout_order.clear()

        self.selected_track_id = None
        self.selected_turnout_id = None

        self._end_drag()
        self._update_inspector(None)
        self._refresh_canvas()
        self._set_status("Started a new blank layout.")

    def _show_about(self) -> None:
        top = tk.Toplevel(self.root)
        top.title("About Layout Designer V2")
        top.transient(self.root)
        top.grab_set()

        frame = ttk.Frame(top, padding=14)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text=(
                "Layout Designer V2\n\n"
                "Current focus:\n"
                "• Straight-track authoring\n"
                "• Two-rail rendering\n"
                "• Endpoint handles\n"
                "• Intent-based magnetic snapping\n"
                "• Scrollable / zoomable design board\n\n"
                "This remains a designer-side scaffold and is not yet the full\n"
                "domain-backed layout/session pipeline."
            ),
            justify="left",
        ).pack(anchor="w")

        ttk.Button(frame, text="Close", command=top.destroy).pack(
            anchor="e", pady=(12, 0)
        )

    def _not_implemented(self) -> None:
        self._set_status("That action is reserved for a later iteration.")


def main() -> None:
    root = tk.Tk()
    LayoutDesignerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
