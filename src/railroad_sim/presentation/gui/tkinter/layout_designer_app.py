from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
import math
import time
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import Misc, ttk
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

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Layout Designer")
        self.root.geometry("1500x900")
        self.root.minsize(1180, 760)
        self.name_entry_var = tk.StringVar(value="")
        self.track_type_var = tk.StringVar(value=TrackType.MAINLINE.value)
        self.traffic_rule_var = tk.StringVar(value=TrackTrafficRule.BIDIRECTIONAL.value)

        self.selected_tool = tk.StringVar(value="select")
        self.show_grid = tk.BooleanVar(value=True)
        self.snap_to_grid = tk.BooleanVar(value=True)
        self.show_endpoints = tk.BooleanVar(value=True)
        self.show_topology_overlay = tk.BooleanVar(value=False)

        self.zoom_scale = 1.0

        self.tracks: dict[str, StraightTrackElement] = {}
        self.track_order: list[str] = []
        self.selected_track_id: str | None = None

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

        self._snap_candidate: tuple[str, str] | None = None
        self._snap_candidate_since: float | None = None
        self._snap_locked: tuple[str, str] | None = None
        self._snap_preview_point: tuple[float, float] | None = None

        self._build_style()
        self._build_menu()
        self._build_ui()
        self._bind_keys()
        self._refresh_canvas()
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

        tools = (("Select", "select"), ("Track", "track"))
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
            text="Topology",
            variable=self.show_topology_overlay,
            command=self._refresh_canvas,
        ).grid(row=0, column=5, padx=(0, 8), sticky="w")
        ttk.Checkbutton(frame, text="Snap Grid", variable=self.snap_to_grid).grid(
            row=0, column=6, padx=(0, 8), sticky="w"
        )

        ttk.Label(
            frame,
            text="Place: select Track, press-drag-release. Edit: drag body to move, Ctrl+drag endpoint to reshape.",
        ).grid(row=1, column=0, columnspan=7, sticky="w", pady=(8, 0))

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

    def _build_inspector(self, parent: ttk.Frame) -> None:
        panel = ttk.LabelFrame(parent, text="Inspector", padding=10)
        panel.pack(fill="both", expand=True)

        self.inspector_header = ttk.Label(
            panel, text="No Selection", style="InspectorHeader.TLabel"
        )
        self.inspector_header.pack(anchor="w", pady=(0, 10))

        # Name
        name_row = ttk.Frame(panel)
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
        type_row = ttk.Frame(panel)
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
        rule_row = ttk.Frame(panel)
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
        self.root.bind("<Delete>", self._delete_selected)
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

        trim_px = 0.5 * self.zoom_scale

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
        taper_factor = 0.75

        if track.endpoint_a.connected_to_track_id is not None:
            left_x1 = (left_x1 + right_x1) / 2 + (
                left_x1 - right_x1
            ) * 0.5 * taper_factor
            left_y1 = (left_y1 + right_y1) / 2 + (
                left_y1 - right_y1
            ) * 0.5 * taper_factor

            right_x1 = (left_x1 + right_x1) / 2 - (
                left_x1 - right_x1
            ) * 0.5 * taper_factor
            right_y1 = (left_y1 + right_y1) / 2 - (
                left_y1 - right_y1
            ) * 0.5 * taper_factor

        if track.endpoint_b.connected_to_track_id is not None:
            left_x2 = (left_x2 + right_x2) / 2 + (
                left_x2 - right_x2
            ) * 0.5 * taper_factor
            left_y2 = (left_y2 + right_y2) / 2 + (
                left_y2 - right_y2
            ) * 0.5 * taper_factor

            right_x2 = (left_x2 + right_x2) / 2 - (
                left_x2 - right_x2
            ) * 0.5 * taper_factor
            right_y2 = (left_y2 + right_y2) / 2 - (
                left_y2 - right_y2
            ) * 0.5 * taper_factor

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
        if track.track_id == self.selected_track_id:
            bbox = self._track_screen_bbox(track)
            self.canvas.create_rectangle(
                bbox[0] - 8,
                bbox[1] - 8,
                bbox[2] + 8,
                bbox[3] + 8,
                outline="#ff9900",
                width=max(1.0, 2.0 * self.zoom_scale),
                dash=(4, 2),
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
        hit = self._hit_test(world_x, world_y)
        tool = self.selected_tool.get()

        if tool == "track":
            self._begin_track_creation(world_x, world_y)
            return

        if hit is None:
            self.selected_track_id = None
            self._drag_mode = None
            self._drag_track_id = None
            self._drag_endpoint_name = None
            self._update_inspector(None)
            self._refresh_canvas()
            self._set_status("Selection cleared.")
            return

        self.selected_track_id = hit["track_id"]
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

    def _on_canvas_drag(self, event: tk.Event) -> None:
        world_x, world_y = self._event_world(event)

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

        if self._drag_track_id is None or self._drag_last_world is None:
            return

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
                    candidate_track_id,
                    candidate_endpoint_name,
                    candidate_x,
                    candidate_y,
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
        world_x, world_y = self._event_world(event)

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

            if self.snap_to_grid.get():
                snapped_x1, snapped_y1 = self._apply_grid_snap(track.x1, track.y1)
                dx = snapped_x1 - track.x1
                dy = snapped_y1 - track.y1
                track.move_by(dx, dy)
                self._clamp_track_to_canvas(track)

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

            self._update_inspector(track)
            self._set_status(f"Moved {track.name}.")

        _ = (world_x, world_y)
        self._end_drag()
        self._refresh_canvas()

    def _on_canvas_motion(self, event: tk.Event) -> None:
        world_x, world_y = self._event_world(event)
        hit = self._hit_test(world_x, world_y)

        self._hover_track_id = None
        self._hover_endpoint_name = None

        if hit is not None:
            self._hover_track_id = hit["track_id"]
            if hit["part"] == "endpoint":
                self._hover_endpoint_name = hit["endpoint_name"]
            self._schedule_tooltip(
                event.x_root, event.y_root, self._tooltip_text_for_hit(hit)
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
        self._create_track_id = track_id
        self._drag_track_id = track_id
        self._drag_mode = "create"
        self._drag_endpoint_name = "B"
        self._drag_last_world = (x, y)
        self._update_inspector(new_track)
        self._refresh_canvas()
        self._set_status("Drag to place a new straight track segment.")

    def _delete_selected(self, _event: tk.Event | None = None) -> None:
        if self.selected_track_id is None:
            return
        name = self.tracks[self.selected_track_id].name
        self._delete_track(self.selected_track_id)
        self.selected_track_id = None
        self._update_inspector(None)
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
        if other_track is None:
            return

        other_endpoint = other_track.endpoint(other_endpoint_name)
        if other_endpoint.connected_to_track_id == track.track_id:
            other_endpoint.connected_to_track_id = None
            other_endpoint.connected_to_endpoint_name = None

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
        target_track = self.tracks[target_track_id]
        x, y = self._snap_preview_point
        active_track.set_endpoint(active_endpoint_name, x, y)

        self._clear_endpoint_connection(active_track, active_endpoint_name)
        self._clear_endpoint_connection(target_track, target_endpoint_name)

        active_endpoint = active_track.endpoint(active_endpoint_name)
        target_endpoint = target_track.endpoint(target_endpoint_name)

        active_endpoint.connected_to_track_id = target_track_id
        active_endpoint.connected_to_endpoint_name = target_endpoint_name
        target_endpoint.connected_to_track_id = active_track_id
        target_endpoint.connected_to_endpoint_name = active_endpoint_name

    def _end_drag(self) -> None:
        self._drag_mode = None
        self._drag_track_id = None
        self._drag_endpoint_name = None
        self._drag_last_world = None
        self._create_track_id = None
        self._snap_candidate = None
        self._snap_candidate_since = None
        self._snap_locked = None
        self._snap_preview_point = None

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

        candidate_track_id, candidate_endpoint_name, candidate_x, candidate_y = (
            candidate
        )

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
    ) -> tuple[str, str, float, float] | None:

        best: tuple[str, str, float, float] | None = None
        best_distance = float("inf")

        active_track = self.tracks[active_track_id]
        active_heading = self._endpoint_heading_deg(active_track, active_endpoint_name)

        for track in self.tracks.values():
            if track.track_id == active_track_id:
                continue

            for endpoint_name in ("A", "B"):
                endpoint = track.endpoint(endpoint_name)
                distance = math.hypot(endpoint.x - active_x, endpoint.y - active_y)
                if distance > self.SNAP_PREVIEW_RADIUS_PX / max(self.zoom_scale, 0.001):
                    continue

                candidate_heading = self._endpoint_heading_deg(track, endpoint_name)
                if not self._headings_are_compatible(active_heading, candidate_heading):
                    continue

                if distance < best_distance:
                    best_distance = distance
                    best = (track.track_id, endpoint_name, endpoint.x, endpoint.y)

        if best is None:
            self._set_status(
                f"No snap candidate for {active_track_id}:{active_endpoint_name}"
            )
            return None

        if best_distance > self.SNAP_COMMIT_RADIUS_PX / max(self.zoom_scale, 0.001):
            # Preview only if in outer ring, but still return candidate so hover cue can show.
            return best

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

            candidate_track_id, candidate_endpoint_name, candidate_x, candidate_y = (
                candidate
            )

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

    def _headings_are_compatible(self, heading_a: float, heading_b: float) -> bool:
        diff = abs((heading_a - heading_b + 180.0) % 360.0 - 180.0)

        # Endpoints should generally face each other to form a straight
        # continuation, so compatibility is based on being near 180° apart.
        return abs(diff - 180.0) <= self.ANGLE_COMPATIBILITY_DEG

    # ------------------------------------------------------------------
    # Hit testing / coordinates
    # ------------------------------------------------------------------
    def _hit_test(self, world_x: float, world_y: float) -> dict[str, str] | None:
        # Endpoint hit has priority.
        for track_id in reversed(self.track_order):
            track = self.tracks[track_id]
            for endpoint_name in ("A", "B"):
                endpoint = track.endpoint(endpoint_name)
                if math.hypot(
                    endpoint.x - world_x, endpoint.y - world_y
                ) <= self.ENDPOINT_HIT_RADIUS_PX / max(self.zoom_scale, 0.001):
                    return {
                        "track_id": track_id,
                        "part": "endpoint",
                        "endpoint_name": endpoint_name,
                    }

        for track_id in reversed(self.track_order):
            track = self.tracks[track_id]
            distance = self._distance_point_to_segment(
                world_x, world_y, track.x1, track.y1, track.x2, track.y2
            )
            if distance <= (self.TRACK_GAUGE_PX + 12.0) / max(self.zoom_scale, 0.001):
                return {"track_id": track_id, "part": "body", "endpoint_name": ""}

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
    def _update_inspector(self, track: StraightTrackElement | None) -> None:
        if track is None:
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
        self.selected_track_id = None
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
