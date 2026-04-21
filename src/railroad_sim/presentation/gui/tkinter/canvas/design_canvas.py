from __future__ import annotations

import tkinter as tk
from tkinter import simpledialog, ttk
from typing import Callable

from railroad_sim.presentation.gui.tkinter.canvas.elements import (
    StraightTrackElement,
    TurnoutElement,
)
from railroad_sim.presentation.gui.tkinter.canvas.rulers.guide_model import GuideModel
from railroad_sim.presentation.gui.tkinter.canvas.rulers.ruler_widgets import (
    HorizontalRuler,
    VerticalRuler,
)
from railroad_sim.presentation.gui.tkinter.canvas.snap_helpers import (
    SnapCandidate,
)
from railroad_sim.presentation.gui.tkinter.utils.rotation_utils import (
    rotate_straight_track,
    rotate_straight_track_about_pivot,
    rotate_turnout,
    rotate_turnout_about_pivot,
)


class DesignCanvas(ttk.Frame):
    """
    Standalone design surface for Railroad Studio.

    First pass responsibilities:
    - own the Tk canvas
    - own horizontal / vertical scrollbars
    - manage scrollregion
    - optionally draw a simple background grid

    Deliberately does NOT own:
    - rulers
    - object drawing
    - snapping
    - tools
    - selection logic
    """

    DEFAULT_WORLD_WIDTH = 4000
    DEFAULT_WORLD_HEIGHT = 2600
    DEFAULT_GRID_SPACING = 20
    SCROLL_UNITS_PER_TICK = 10
    MAX_VERTICAL_GUIDES = 5  # from top ruler
    MAX_HORIZONTAL_GUIDES = 5  # from left ruler

    CURSOR_DEFAULT = ""
    CURSOR_VERTICAL_GUIDE = "sb_h_double_arrow"
    CURSOR_HORIZONTAL_GUIDE = "sb_v_double_arrow"
    CURSOR_SELECTABLE = "hand2"
    CURSOR_ADD_ARMED = "crosshair"

    GUIDE_AUTOSCROLL_EDGE_MARGIN = 24
    GUIDE_AUTOSCROLL_UNITS_PER_TICK = 8

    TRACK_GUIDE_SNAP_TOLERANCE = 8.0
    GUIDE_COLOR = "#ff5c7a"

    def __init__(
        self,
        parent: tk.Misc,
        *,
        on_mouse_move: Callable[[float | None, float | None], None] | None = None,
        on_status_message: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent, padding=0)

        # ------------------------------------------------------------------
        # External callbacks
        # ------------------------------------------------------------------
        self.on_mouse_move = on_mouse_move
        self.on_status_message = on_status_message

        # ------------------------------------------------------------------
        # Canvas/world configuration
        # ------------------------------------------------------------------
        self.world_width = self.DEFAULT_WORLD_WIDTH
        self.world_height = self.DEFAULT_WORLD_HEIGHT
        self.grid_spacing = self.DEFAULT_GRID_SPACING
        self._last_mouse_canvas_x: int | None = None
        self._last_mouse_canvas_y: int | None = None

        # ------------------------------------------------------------------
        # Guide/ruler state
        # ------------------------------------------------------------------
        self.guides = GuideModel(
            max_vertical_guides=self.MAX_VERTICAL_GUIDES,
            max_horizontal_guides=self.MAX_HORIZONTAL_GUIDES,
        )
        self._dragging_new_vertical_guide = False
        self._dragging_new_horizontal_guide = False
        self._temp_vertical_guide_x: float | None = None
        self._temp_horizontal_guide_y: float | None = None
        self._show_rulers = True
        self._show_grid = False
        self._show_snap = True
        self._active_guide_drag: str | None = None  # "vertical" | "horizontal" | None
        self._alt_pressed = False
        self._moving_vertical_guide_index: int | None = None
        self._moving_horizontal_guide_index: int | None = None
        self._guide_hit_tolerance = 6.0

        # ------------------------------------------------------------------
        # Canvas elements / committed layout objects
        # ------------------------------------------------------------------
        self._tracks: list[StraightTrackElement] = []
        self._turnouts: list[TurnoutElement] = []

        # ------------------------------------------------------------------
        # Placement / creation mode
        # ------------------------------------------------------------------
        self._creating_track = False
        self._temp_track: StraightTrackElement | None = None
        self._current_trackwork_element = "Track"
        self._pending_trackwork_add = False

        # ------------------------------------------------------------------
        # Selection state
        # single-selection = editing handles / endpoint editing
        # multi-selection = marquee/group operations
        # ------------------------------------------------------------------
        self._selected_track_id: str | None = None
        self._selected_turnout_id: str | None = None
        self._selected_track_ids: set[str] = set()
        self._selected_turnout_ids: set[str] = set()

        # ------------------------------------------------------------------
        # Marquee selection / group move
        # ------------------------------------------------------------------
        self._marquee_selecting = False
        self._marquee_start_world_x: float | None = None
        self._marquee_start_world_y: float | None = None
        self._marquee_current_world_x: float | None = None
        self._marquee_current_world_y: float | None = None
        self._group_dragging = False

        # ------------------------------------------------------------------
        # Active drag state
        # ------------------------------------------------------------------
        self._active_track_drag_id: str | None = None
        self._active_turnout_drag_id: str | None = None
        self._active_endpoint_drag: int | None = None  # 1 or 2
        self._active_turnout_endpoint_drag: str | None = (
            None  # "trunk", "straight", or "diverging"
        )
        self._drag_start_world_x: float | None = None
        self._drag_start_world_y: float | None = None

        # ------------------------------------------------------------------
        # Temporary snap preview during track creation
        # ------------------------------------------------------------------
        self._track_snap_preview_x: float | None = None
        self._track_snap_preview_y: float | None = None
        self._track_snap_preview_show_vertical = False
        self._track_snap_preview_show_horizontal = False

        # ------------------------------------------------------------------
        # Snap preview / snap commit helpers
        # ------------------------------------------------------------------
        self._endpoint_snap_candidate = None
        self._endpoint_snap_flash = None
        self._body_drag_snap_endpoint_index: int | None = None
        self._turnout_body_drag_snap_endpoint_name: str | None = None

        self._build_ui()
        self._build_canvas_context_menu()
        self._configure_canvas()
        self.redraw()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.rowconfigure(1, weight=1)
        self.columnconfigure(1, weight=1)

        ruler_size = HorizontalRuler.RULER_THICKNESS

        # --------------------------------------------------------------
        # Top-left corner block where the rulers meet
        # --------------------------------------------------------------
        self.corner = tk.Canvas(
            self,
            width=ruler_size,
            height=ruler_size,
            background="#f4f4f4",
            highlightthickness=1,
            highlightbackground="#b8b8b8",
            bd=0,
        )
        self.corner.grid(row=0, column=0, sticky="nsew")

        # --------------------------------------------------------------
        # Top horizontal ruler
        # --------------------------------------------------------------
        self.h_ruler = HorizontalRuler(self, design_canvas=None)  # temp assign below
        self.h_ruler.configure(height=ruler_size)
        self.h_ruler.grid(row=0, column=1, sticky="ew")

        # --------------------------------------------------------------
        # Left vertical ruler
        # --------------------------------------------------------------
        self.v_ruler = VerticalRuler(self, design_canvas=None)  # temp assign below
        self.v_ruler.configure(width=ruler_size)
        self.v_ruler.grid(row=1, column=0, sticky="ns")

        # --------------------------------------------------------------
        # Main canvas
        # --------------------------------------------------------------
        self.canvas = tk.Canvas(
            self,
            background="white",
            highlightthickness=1,
            highlightbackground="#b8b8b8",
            xscrollincrement=1,
            yscrollincrement=1,
        )
        self.canvas.grid(row=1, column=1, sticky="nsew")

        # now that canvas exists, attach it to rulers
        self.h_ruler.design_canvas = self.canvas
        self.v_ruler.design_canvas = self.canvas

        # --------------------------------------------------------------
        # Vertical scrollbar
        # --------------------------------------------------------------
        self.v_scrollbar = ttk.Scrollbar(
            self,
            orient="vertical",
            command=self._on_vertical_scrollbar,
        )
        self.v_scrollbar.grid(row=1, column=2, sticky="ns")

        # --------------------------------------------------------------
        # Horizontal scrollbar
        # --------------------------------------------------------------
        self.h_scrollbar = ttk.Scrollbar(
            self,
            orient="horizontal",
            command=self._on_horizontal_scrollbar,
        )
        self.h_scrollbar.grid(row=2, column=1, sticky="ew")

        # --------------------------------------------------------------
        # Canvas event bindings
        # --------------------------------------------------------------

        self.canvas.bind("<Enter>", self._on_canvas_enter)
        self.canvas.bind("<Leave>", self._on_canvas_leave)
        self.canvas.bind("<Button-4>", self._on_mousewheel_linux_up)
        self.canvas.bind("<Button-5>", self._on_mousewheel_linux_down)
        self.canvas.bind("<Motion>", self._on_canvas_motion)
        self.canvas.bind("<ButtonPress-1>", self._on_canvas_button_press)
        self.canvas.bind("<Leave>", self._on_canvas_leave_status, add="+")
        self.canvas.bind("<Leave>", self._on_canvas_leave_hover, add="+")
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        self.canvas.bind("<Alt_L>", self._on_alt_press)
        self.canvas.bind("<KeyRelease-Alt_L>", self._on_alt_release)
        self.canvas.bind("<Alt_R>", self._on_alt_press)
        self.canvas.bind("<KeyRelease-Alt_R>", self._on_alt_release)

        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<Button-3>", self._on_canvas_right_click)

    def _build_canvas_context_menu(self) -> None:
        self.canvas_context_menu = tk.Menu(self.canvas, tearoff=0)

        self.canvas_context_menu.add_command(
            label="Rotate -90°",
            command=lambda: self.rotate_selected_trackwork_counterclockwise(90.0),
        )
        self.canvas_context_menu.add_command(
            label="Rotate -45°",
            command=lambda: self.rotate_selected_trackwork_counterclockwise(45.0),
        )
        self.canvas_context_menu.add_command(
            label="Rotate -15°",
            command=lambda: self.rotate_selected_trackwork_counterclockwise(15.0),
        )

        self.canvas_context_menu.add_separator()

        self.canvas_context_menu.add_command(
            label="Rotate +15°",
            command=lambda: self.rotate_selected_trackwork_clockwise(15.0),
        )
        self.canvas_context_menu.add_command(
            label="Rotate +45°",
            command=lambda: self.rotate_selected_trackwork_clockwise(45.0),
        )
        self.canvas_context_menu.add_command(
            label="Rotate +90°",
            command=lambda: self.rotate_selected_trackwork_clockwise(90.0),
        )
        self.canvas_context_menu.add_separator()
        self.canvas_context_menu.add_command(
            label="Specify Angle...",
            command=self._on_context_menu_rotate_specify_angle,
        )

    def _on_canvas_right_click(self, event: tk.Event) -> None:
        world_x = self.canvas.canvasx(event.x)
        world_y = self.canvas.canvasy(event.y)

        # --------------------------------------------------------------
        # If a group is selected and the right-click lands on that group,
        # preserve the group selection and open the rotate menu.
        # --------------------------------------------------------------
        if self._has_group_selection():
            if self._is_point_on_group_selected_track_body(
                world_x,
                world_y,
            ) or self._is_point_on_group_selected_turnout(world_x, world_y):
                self.redraw()
                self._set_status_message("Selected group ready.")
                self.canvas_context_menu.tk_popup(event.x_root, event.y_root)
                return

        # --------------------------------------------------------------
        # Hit test track first
        # --------------------------------------------------------------
        clicked_track = self._find_track_at_point(world_x, world_y)
        if clicked_track is not None:
            self._clear_group_selection()
            self._selected_track_id = clicked_track.id
            self._selected_turnout_id = None
            self.redraw()
            self._set_status_message("Track selected.")

            self.canvas_context_menu.tk_popup(event.x_root, event.y_root)
            return

        # --------------------------------------------------------------
        # Hit test turnout
        # --------------------------------------------------------------
        clicked_turnout = self._find_turnout_at_point(world_x, world_y)
        if clicked_turnout is not None:
            self._clear_group_selection()
            self._selected_turnout_id = clicked_turnout.id
            self._selected_track_id = None
            self.redraw()
            self._set_status_message("Turnout selected.")

            self.canvas_context_menu.tk_popup(event.x_root, event.y_root)
            return

        # --------------------------------------------------------------
        # Empty canvas → do NOT show rotate menu
        # --------------------------------------------------------------
        return

    def _on_context_menu_rotate_specify_angle(self) -> None:
        degrees = simpledialog.askfloat(
            "Specify Rotation",
            "Rotate selected trackwork by degrees:",
            parent=self.winfo_toplevel(),
            minvalue=-360.0,
            maxvalue=360.0,
        )

        if degrees is None:
            return

        if abs(degrees) < 1e-9:
            self._set_status_message("Rotation skipped (0°).")
            return

        self.rotate_selected_trackwork_by_custom_angle(degrees)

    def _configure_canvas(self) -> None:
        self.canvas.configure(
            xscrollcommand=self._on_canvas_xscroll,
            yscrollcommand=self._on_canvas_yscroll,
            scrollregion=(0, 0, self.world_width, self.world_height),
        )

    def _on_canvas_xscroll(self, first: float, last: float) -> None:
        self.h_scrollbar.set(first, last)
        self._redraw_rulers()

    def _on_canvas_yscroll(self, first: float, last: float) -> None:
        self.v_scrollbar.set(first, last)
        self._redraw_rulers()

    def _on_horizontal_scrollbar(self, *args: object) -> None:
        self.canvas.xview(*args)
        self._redraw_rulers()
        self._notify_mouse_position()

    def _on_vertical_scrollbar(self, *args: object) -> None:
        self.canvas.yview(*args)
        self._redraw_rulers()
        self._notify_mouse_position()

    def _on_canvas_configure(self, _event: tk.Event) -> None:
        self._redraw_rulers()

    def _redraw_rulers(self) -> None:
        self.h_ruler.redraw()
        self.v_ruler.redraw()

    def set_show_rulers(self, value: bool) -> None:
        self._show_rulers = value

        # show/hide ruler widgets
        if value:
            self.h_ruler.grid()
            self.v_ruler.grid()
            self.corner.grid()
        else:
            self.h_ruler.grid_remove()
            self.v_ruler.grid_remove()
            self.corner.grid_remove()

        self.redraw()

    def set_show_grid(self, value: bool) -> None:
        self._show_grid = value
        self.redraw()

    def set_trackwork_element(self, value: str) -> None:
        self._current_trackwork_element = value
        self._set_status_message(f"Trackwork element set to {value}.")

    def arm_add_current_trackwork_element(self) -> None:
        self._pending_trackwork_add = True
        self._selected_track_id = None
        self._selected_turnout_id = None
        self._active_track_drag_id = None
        self._active_turnout_drag_id = None
        self._active_endpoint_drag = None
        self._active_turnout_endpoint_drag = None
        self._drag_start_world_x = None
        self._drag_start_world_y = None
        self._clear_endpoint_snap_candidate()
        self._clear_track_snap_preview()
        self.redraw()
        self._set_status_message(
            f"Add armed: click canvas to place {self._current_trackwork_element}."
        )
        self._update_canvas_cursor_for_mode()

    def delete_selected_trackwork(self) -> None:
        if self._selected_track_ids or self._selected_turnout_ids:
            self._tracks = [
                track
                for track in self._tracks
                if track.id not in self._selected_track_ids
            ]
            self._turnouts = [
                turnout
                for turnout in self._turnouts
                if turnout.id not in self._selected_turnout_ids
            ]
            self._clear_group_selection()
            self._selected_track_id = None
            self._selected_turnout_id = None
            self._active_track_drag_id = None
            self._active_turnout_drag_id = None
            self._active_endpoint_drag = None
            self._active_turnout_endpoint_drag = None
            self._drag_start_world_x = None
            self._drag_start_world_y = None
            self._clear_endpoint_snap_candidate()
            self.redraw()
            self._set_status_message("Selected trackwork deleted.")
            return

        if self._selected_track_id is not None:
            self._tracks = [
                track for track in self._tracks if track.id != self._selected_track_id
            ]
            self._selected_track_id = None
            self._active_track_drag_id = None
            self._active_endpoint_drag = None
            self._drag_start_world_x = None
            self._drag_start_world_y = None
            self._clear_endpoint_snap_candidate()
            self.redraw()
            self._set_status_message("Track deleted.")
            return

        if self._selected_turnout_id is not None:
            self._turnouts = [
                turnout
                for turnout in self._turnouts
                if turnout.id != self._selected_turnout_id
            ]
            self._selected_turnout_id = None
            self._active_turnout_drag_id = None
            self._active_turnout_endpoint_drag = None
            self._drag_start_world_x = None
            self._drag_start_world_y = None
            self._clear_endpoint_snap_candidate()
            self.redraw()
            self._set_status_message("Turnout deleted.")
            return

        self._set_status_message("Nothing selected to delete.")

    def select_all_trackwork(self) -> None:
        if not self._tracks and not self._turnouts:
            self._set_status_message("Nothing to select.")
            return

        self._selected_track_ids = {track.id for track in self._tracks}
        self._selected_turnout_ids = {turnout.id for turnout in self._turnouts}
        self._selected_track_id = None
        self._selected_turnout_id = None
        self._active_track_drag_id = None
        self._active_turnout_drag_id = None
        self._active_endpoint_drag = None
        self._active_turnout_endpoint_drag = None
        self._drag_start_world_x = None
        self._drag_start_world_y = None
        self._clear_endpoint_snap_candidate()
        self.redraw()
        self._set_status_message("All trackwork selected.")

    def rotate_selected_trackwork_by_custom_angle(
        self,
        delta_degrees: float,
    ) -> None:
        """
        Rotate the current single selected trackwork object by an arbitrary angle.
        """
        self.rotate_selected_trackwork(delta_degrees)

    def rotate_selected_trackwork(self, delta_degrees: float) -> None:
        """
        Rotate the current selected trackwork object(s).

        Current behavior:
        - single selected straight track
        - single selected turnout
        - selected group rotation about group pivot
        """
        if self._has_group_selection():
            pivot = self._get_selected_group_rotation_pivot()
            if pivot is None:
                self._set_status_message("Nothing selected to rotate.")
                return

            pivot_x, pivot_y = pivot

            for track in self._tracks:
                if track.id in self._selected_track_ids:
                    rotate_straight_track_about_pivot(
                        track,
                        pivot_x,
                        pivot_y,
                        delta_degrees,
                    )

            for turnout in self._turnouts:
                if turnout.id in self._selected_turnout_ids:
                    rotate_turnout_about_pivot(
                        turnout,
                        pivot_x,
                        pivot_y,
                        delta_degrees,
                    )

            rotated_count = len(self._selected_track_ids) + len(
                self._selected_turnout_ids
            )
            self._clear_endpoint_snap_candidate()
            self.redraw()
            self._set_status_message(
                f"Rotated {rotated_count} selected piece(s) by {delta_degrees:.1f}°."
            )
            return

        selected_track = self._get_selected_track()
        if selected_track is not None:
            rotate_straight_track(selected_track, delta_degrees)
            self._clear_endpoint_snap_candidate()
            self.redraw()
            self._set_status_message(f"Rotated track by {delta_degrees:.1f}°.")
            return

        selected_turnout = self._get_selected_turnout()
        if selected_turnout is not None:
            rotate_turnout(selected_turnout, delta_degrees)
            self._clear_endpoint_snap_candidate()
            self.redraw()
            self._set_status_message(f"Rotated turnout by {delta_degrees:.1f}°.")
            return

        self._set_status_message("Nothing selected to rotate.")

    def rotate_selected_trackwork_clockwise(self, delta_degrees: float) -> None:
        """
        Convenience wrapper for clockwise UI actions.
        """
        self.rotate_selected_trackwork(delta_degrees)

    def rotate_selected_trackwork_counterclockwise(
        self,
        delta_degrees: float,
    ) -> None:
        """
        Convenience wrapper for counterclockwise UI actions.
        """
        self.rotate_selected_trackwork(-delta_degrees)

    def _clear_group_selection(self) -> None:
        self._selected_track_ids.clear()
        self._selected_turnout_ids.clear()

    def _has_group_selection(self) -> bool:
        return bool(self._selected_track_ids or self._selected_turnout_ids)

    def _track_intersects_rect(
        self,
        track: StraightTrackElement,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
    ) -> bool:
        left = min(x1, x2)
        right = max(x1, x2)
        top = min(y1, y2)
        bottom = max(y1, y2)

        pad = 4.0
        track_left = min(track.x1, track.x2) - pad
        track_right = max(track.x1, track.x2) + pad
        track_top = min(track.y1, track.y2) - pad
        track_bottom = max(track.y1, track.y2) + pad

        return not (
            track_right < left
            or track_left > right
            or track_bottom < top
            or track_top > bottom
        )

    def _turnout_intersects_rect(
        self,
        turnout: TurnoutElement,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
    ) -> bool:
        left = min(x1, x2)
        right = max(x1, x2)
        top = min(y1, y2)
        bottom = max(y1, y2)

        endpoints = self._get_turnout_endpoint_positions(turnout)
        xs = [turnout.x]
        ys = [turnout.y]

        for endpoint_x, endpoint_y in endpoints.values():
            xs.append(endpoint_x)
            ys.append(endpoint_y)

        pad = 4.0
        turnout_left = min(xs) - pad
        turnout_right = max(xs) + pad
        turnout_top = min(ys) - pad
        turnout_bottom = max(ys) + pad

        return not (
            turnout_right < left
            or turnout_left > right
            or turnout_bottom < top
            or turnout_top > bottom
        )

    def _commit_marquee_selection(self) -> None:
        if (
            self._marquee_start_world_x is None
            or self._marquee_start_world_y is None
            or self._marquee_current_world_x is None
            or self._marquee_current_world_y is None
        ):
            return

        x1 = self._marquee_start_world_x
        y1 = self._marquee_start_world_y
        x2 = self._marquee_current_world_x
        y2 = self._marquee_current_world_y

        self._selected_track_ids = {
            track.id
            for track in self._tracks
            if self._track_intersects_rect(track, x1, y1, x2, y2)
        }
        self._selected_turnout_ids = {
            turnout.id
            for turnout in self._turnouts
            if self._turnout_intersects_rect(turnout, x1, y1, x2, y2)
        }

        self._selected_track_id = None
        self._selected_turnout_id = None

    def _is_point_on_group_selected_track_body(
        self,
        world_x: float,
        world_y: float,
    ) -> bool:
        for track in self._tracks:
            if track.id not in self._selected_track_ids:
                continue

            if self._point_near_segment(
                px=world_x,
                py=world_y,
                x1=track.x1,
                y1=track.y1,
                x2=track.x2,
                y2=track.y2,
                tolerance=6.0,
            ):
                return True

        return False

    def _is_point_on_group_selected_turnout(
        self,
        world_x: float,
        world_y: float,
    ) -> bool:
        turnout = self._find_turnout_at_point(world_x, world_y)
        if turnout is None:
            return False

        return turnout.id in self._selected_turnout_ids

    def _move_selected_group(
        self,
        dx: float,
        dy: float,
    ) -> None:
        for track in self._tracks:
            if track.id in self._selected_track_ids:
                track.move(dx, dy)

        for turnout in self._turnouts:
            if turnout.id in self._selected_turnout_ids:
                turnout.move(dx, dy)

    def _snap_value_to_grid(self, value: float) -> float:
        return round(value / self.grid_spacing) * self.grid_spacing

    def _snap_point_to_grid(
        self,
        x: float,
        y: float,
    ) -> tuple[float, float]:
        return (
            self._snap_value_to_grid(x),
            self._snap_value_to_grid(y),
        )

    def _get_selected_group_rotation_pivot(self) -> tuple[float, float] | None:
        points: list[tuple[float, float]] = []

        for track in self._tracks:
            if track.id in self._selected_track_ids:
                points.append((track.x1, track.y1))
                points.append((track.x2, track.y2))

        for turnout in self._turnouts:
            if turnout.id in self._selected_turnout_ids:
                points.append((turnout.x, turnout.y))

                endpoints = self._get_turnout_endpoint_positions(turnout)
                points.extend(endpoints.values())

        if not points:
            return None

        min_x = min(x for x, _ in points)
        max_x = max(x for x, _ in points)
        min_y = min(y for _, y in points)
        max_y = max(y for _, y in points)

        return ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)

    def set_show_snap(self, value: bool) -> None:
        self._show_snap = value

        if not value:
            self._clear_track_snap_preview()

        self.redraw()

    def _set_vertical_guide_cursor(self) -> None:
        self.canvas.configure(cursor=self.CURSOR_VERTICAL_GUIDE)
        self.h_ruler.configure(cursor=self.CURSOR_VERTICAL_GUIDE)

    def _set_horizontal_guide_cursor(self) -> None:
        self.canvas.configure(cursor=self.CURSOR_HORIZONTAL_GUIDE)
        self.v_ruler.configure(cursor=self.CURSOR_HORIZONTAL_GUIDE)

    def _reset_guide_cursor(self) -> None:
        self.canvas.configure(cursor=self.CURSOR_DEFAULT)
        self.h_ruler.configure(cursor=self.CURSOR_DEFAULT)
        self.v_ruler.configure(cursor=self.CURSOR_DEFAULT)

    def _update_canvas_cursor_for_mode(self) -> None:
        if self._pending_trackwork_add:
            self.canvas.configure(cursor=self.CURSOR_ADD_ARMED)
            return

        self._update_track_hover_cursor()

    def _update_guide_hover_cursor(self) -> None:
        if self._pending_trackwork_add:
            return

        if self._active_guide_drag is not None:
            return

        if not self._show_rulers:
            return

        if not self._alt_pressed:
            return

        if self._last_mouse_canvas_x is None or self._last_mouse_canvas_y is None:
            self._reset_guide_cursor()
            return

        world_x = self.canvas.canvasx(self._last_mouse_canvas_x)
        world_y = self.canvas.canvasy(self._last_mouse_canvas_y)

        vertical_index = self.guides.find_nearest_vertical(
            world_x,
            self._guide_hit_tolerance,
        )
        if vertical_index is not None:
            self._set_vertical_guide_cursor()
            return

        horizontal_index = self.guides.find_nearest_horizontal(
            world_y,
            self._guide_hit_tolerance,
        )
        if horizontal_index is not None:
            self._set_horizontal_guide_cursor()
            return

        self._reset_guide_cursor()

    def _pointer_is_over_top_ruler(self, x_root: int, y_root: int) -> bool:
        x0 = self.h_ruler.winfo_rootx()
        y0 = self.h_ruler.winfo_rooty()
        x1 = x0 + self.h_ruler.winfo_width()
        y1 = y0 + self.h_ruler.winfo_height()
        return x0 <= x_root <= x1 and y0 <= y_root <= y1

    def _pointer_is_over_left_ruler(self, x_root: int, y_root: int) -> bool:
        x0 = self.v_ruler.winfo_rootx()
        y0 = self.v_ruler.winfo_rooty()
        x1 = x0 + self.v_ruler.winfo_width()
        y1 = y0 + self.v_ruler.winfo_height()
        return x0 <= x_root <= x1 and y0 <= y_root <= y1

    def _clear_track_snap_preview(self) -> None:
        self._track_snap_preview_x = None
        self._track_snap_preview_y = None
        self._track_snap_preview_show_vertical = False
        self._track_snap_preview_show_horizontal = False

    def _update_track_snap_preview(
        self,
        world_x: float,
        world_y: float,
    ) -> tuple[float, float]:
        if not self._show_snap:
            self._clear_track_snap_preview()
            return world_x, world_y

        snapped_x = self._get_snapped_x_to_vertical_guide(world_x)
        snapped_y = self._get_snapped_y_to_horizontal_guide(world_y)

        self._track_snap_preview_show_vertical = snapped_x != world_x
        self._track_snap_preview_show_horizontal = snapped_y != world_y

        self._track_snap_preview_x = snapped_x
        self._track_snap_preview_y = snapped_y

        return snapped_x, snapped_y

    def _get_snapped_x_to_vertical_guide(self, world_x: float) -> float:
        guide_index = self.guides.find_nearest_vertical(
            world_x,
            self.TRACK_GUIDE_SNAP_TOLERANCE,
        )
        if guide_index is None:
            return world_x
        return self.guides.vertical_guides[guide_index]

    def _get_snapped_y_to_horizontal_guide(self, world_y: float) -> float:
        guide_index = self.guides.find_nearest_horizontal(
            world_y,
            self.TRACK_GUIDE_SNAP_TOLERANCE,
        )
        if guide_index is None:
            return world_y
        return self.guides.horizontal_guides[guide_index]

    def _auto_scroll_during_guide_drag(
        self,
        canvas_local_x: float,
        canvas_local_y: float,
    ) -> None:
        """
        Auto-scroll the canvas when an active guide drag reaches the viewport edge.

        Vertical guide drags scroll horizontally.
        Horizontal guide drags scroll vertically.
        """
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        margin = self.GUIDE_AUTOSCROLL_EDGE_MARGIN
        units = self.GUIDE_AUTOSCROLL_UNITS_PER_TICK

        if self._active_guide_drag in ("vertical", "vertical_move"):
            if canvas_local_x <= margin:
                self.canvas.xview_scroll(-units, "units")
                self._redraw_rulers()
            elif canvas_local_x >= (width - margin):
                self.canvas.xview_scroll(units, "units")
                self._redraw_rulers()

        elif self._active_guide_drag in ("horizontal", "horizontal_move"):
            if canvas_local_y <= margin:
                self.canvas.yview_scroll(-units, "units")
                self._redraw_rulers()
                self._notify_mouse_position()
            elif canvas_local_y >= (height - margin):
                self.canvas.yview_scroll(units, "units")
                self._redraw_rulers()
                self._notify_mouse_position()

    # guide placement and drag
    def start_vertical_guide_drag(self, world_x: float) -> None:
        self._active_guide_drag = "vertical"
        self.begin_vertical_guide_drag(world_x)
        self._set_vertical_guide_cursor()

        self.bind_all("<Motion>", self._on_global_guide_drag_motion)
        self.bind_all("<ButtonRelease-1>", self._on_global_guide_drag_release)

    def start_horizontal_guide_drag(self, world_y: float) -> None:
        self._active_guide_drag = "horizontal"
        self.begin_horizontal_guide_drag(world_y)
        self._set_horizontal_guide_cursor()

        self.bind_all("<Motion>", self._on_global_guide_drag_motion)
        self.bind_all("<ButtonRelease-1>", self._on_global_guide_drag_release)

    def _end_active_guide_drag(self) -> None:
        self.unbind_all("<Motion>")
        self.unbind_all("<ButtonRelease-1>")

        self._active_guide_drag = None
        self._moving_vertical_guide_index = None
        self._moving_horizontal_guide_index = None

        self._reset_guide_cursor()

    def start_vertical_guide_move(self, index: int, world_x: float) -> None:
        self._active_guide_drag = "vertical_move"
        self._moving_vertical_guide_index = index
        self._temp_vertical_guide_x = world_x
        self._set_vertical_guide_cursor()
        self.redraw()

        self.bind_all("<Motion>", self._on_global_guide_drag_motion)
        self.bind_all("<ButtonRelease-1>", self._on_global_guide_drag_release)

    def start_horizontal_guide_move(self, index: int, world_y: float) -> None:
        self._active_guide_drag = "horizontal_move"
        self._moving_horizontal_guide_index = index
        self._temp_horizontal_guide_y = world_y
        self._set_horizontal_guide_cursor()
        self.redraw()

        self.bind_all("<Motion>", self._on_global_guide_drag_motion)
        self.bind_all("<ButtonRelease-1>", self._on_global_guide_drag_release)

    def _commit_vertical_guide_move(self) -> bool:
        if (
            self._moving_vertical_guide_index is None
            or self._temp_vertical_guide_x is None
        ):
            return False

        moved = self.guides.move_vertical(
            self._moving_vertical_guide_index,
            self._temp_vertical_guide_x,
        )

        self._moving_vertical_guide_index = None
        self._temp_vertical_guide_x = None
        self.redraw()

        if moved:
            self._set_status_message("Vertical guide moved.")

        return moved

    def _commit_horizontal_guide_move(self) -> bool:
        if (
            self._moving_horizontal_guide_index is None
            or self._temp_horizontal_guide_y is None
        ):
            return False

        moved = self.guides.move_horizontal(
            self._moving_horizontal_guide_index,
            self._temp_horizontal_guide_y,
        )

        self._moving_horizontal_guide_index = None
        self._temp_horizontal_guide_y = None
        self.redraw()

        if moved:
            self._set_status_message("Horizontal guide moved.")

        return moved

    def _remove_vertical_guide_if_released_over_ruler(
        self,
        x_root: int,
        y_root: int,
    ) -> bool:
        if self._moving_vertical_guide_index is None:
            return False

        if not self._pointer_is_over_top_ruler(x_root, y_root):
            return False

        removed = self.guides.remove_vertical(self._moving_vertical_guide_index)

        self._moving_vertical_guide_index = None
        self._temp_vertical_guide_x = None
        self.redraw()

        if removed:
            self._set_status_message("Vertical guide removed.")

        return removed

    def _remove_horizontal_guide_if_released_over_ruler(
        self,
        x_root: int,
        y_root: int,
    ) -> bool:
        if self._moving_horizontal_guide_index is None:
            return False

        if not self._pointer_is_over_left_ruler(x_root, y_root):
            return False

        removed = self.guides.remove_horizontal(self._moving_horizontal_guide_index)

        self._moving_horizontal_guide_index = None
        self._temp_horizontal_guide_y = None
        self.redraw()

        if removed:
            self._set_status_message("Horizontal guide removed.")

        return removed

    def _on_global_guide_drag_motion(self, event: tk.Event) -> None:
        if self._active_guide_drag is None:
            return

        canvas_local_x = event.x_root - self.canvas.winfo_rootx()
        canvas_local_y = event.y_root - self.canvas.winfo_rooty()

        self._auto_scroll_during_guide_drag(canvas_local_x, canvas_local_y)

        # Recompute after any auto-scroll so world coords stay current.
        canvas_local_x = event.x_root - self.canvas.winfo_rootx()
        canvas_local_y = event.y_root - self.canvas.winfo_rooty()

        world_x = self.canvas.canvasx(canvas_local_x)
        world_y = self.canvas.canvasy(canvas_local_y)

        if self._active_guide_drag in ("vertical", "vertical_move"):
            self._temp_vertical_guide_x = world_x
            self.redraw()
        elif self._active_guide_drag in ("horizontal", "horizontal_move"):
            self._temp_horizontal_guide_y = world_y
            self.redraw()

    def _on_global_guide_drag_release(self, event: tk.Event) -> None:
        if self._active_guide_drag == "vertical":
            self.commit_vertical_guide_drag()

        elif self._active_guide_drag == "horizontal":
            self.commit_horizontal_guide_drag()

        elif self._active_guide_drag == "vertical_move":
            removed = self._remove_vertical_guide_if_released_over_ruler(
                event.x_root,
                event.y_root,
            )
            if not removed:
                self._commit_vertical_guide_move()

        elif self._active_guide_drag == "horizontal_move":
            removed = self._remove_horizontal_guide_if_released_over_ruler(
                event.x_root,
                event.y_root,
            )
            if not removed:
                self._commit_horizontal_guide_move()

        self._end_active_guide_drag()

    def begin_vertical_guide_drag(self, world_x: float) -> None:
        self._dragging_new_vertical_guide = True
        self._temp_vertical_guide_x = world_x
        self.redraw()

    def update_vertical_guide_drag(self, world_x: float) -> None:
        if not self._dragging_new_vertical_guide:
            return
        self._temp_vertical_guide_x = world_x
        self.redraw()

    def commit_vertical_guide_drag(self) -> bool:
        if not self._dragging_new_vertical_guide or self._temp_vertical_guide_x is None:
            return False

        if not self.guides.can_add_vertical():
            self._dragging_new_vertical_guide = False
            self._temp_vertical_guide_x = None
            self.redraw()
            self._set_status_message("Maximum vertical guides reached.")
            return False

        added = self.guides.add_vertical(self._temp_vertical_guide_x)

        self._dragging_new_vertical_guide = False
        self._temp_vertical_guide_x = None
        self.redraw()

        if added:
            self._set_status_message("Vertical guide added.")

        return added

    def cancel_vertical_guide_drag(self) -> None:
        self._dragging_new_vertical_guide = False
        self._temp_vertical_guide_x = None
        self.redraw()

    def begin_horizontal_guide_drag(self, world_y: float) -> None:
        self._dragging_new_horizontal_guide = True
        self._temp_horizontal_guide_y = world_y
        self.redraw()

    def clear_vertical_guides(self) -> None:
        self.guides.clear_vertical()
        self.redraw()
        self._set_status_message("Vertical guides cleared.")

    def clear_horizontal_guides(self) -> None:
        self.guides.clear_horizontal()
        self.redraw()
        self._set_status_message("Horizontal guides cleared.")

    def clear_all_guides(self) -> None:
        self.guides.clear()
        self.redraw()
        self._set_status_message("All guides cleared.")

    def update_horizontal_guide_drag(self, world_y: float) -> None:
        if not self._dragging_new_horizontal_guide:
            return
        self._temp_horizontal_guide_y = world_y
        self.redraw()

    def commit_horizontal_guide_drag(self) -> bool:
        if (
            not self._dragging_new_horizontal_guide
            or self._temp_horizontal_guide_y is None
        ):
            return False

        if not self.guides.can_add_horizontal():
            self._dragging_new_horizontal_guide = False
            self._temp_horizontal_guide_y = None
            self.redraw()
            self._set_status_message("Maximum horizontal guides reached.")
            return False

        added = self.guides.add_horizontal(self._temp_horizontal_guide_y)

        self._dragging_new_horizontal_guide = False
        self._temp_horizontal_guide_y = None
        self.redraw()

        if added:
            self._set_status_message("Horizontal guide added.")

        return added

    def cancel_horizontal_guide_drag(self) -> None:
        self._dragging_new_horizontal_guide = False
        self._temp_horizontal_guide_y = None
        self.redraw()

    def _find_track_at_point(
        self,
        world_x: float,
        world_y: float,
    ) -> StraightTrackElement | None:
        hit_tolerance = 6.0

        for track in reversed(self._tracks):
            if self._point_near_segment(
                px=world_x,
                py=world_y,
                x1=track.x1,
                y1=track.y1,
                x2=track.x2,
                y2=track.y2,
                tolerance=hit_tolerance,
            ):
                return track

        return None

    def _find_turnout_at_point(
        self,
        world_x: float,
        world_y: float,
    ) -> TurnoutElement | None:
        import math

        hit_tolerance = 6.0

        for turnout in reversed(self._turnouts):
            x = turnout.x
            y = turnout.y

            base_angle_rad = math.radians(turnout.angle_degrees)
            diverge_delta_rad = math.radians(turnout.diverge_angle_degrees)

            if turnout.is_left_hand:
                diverge_angle_rad = base_angle_rad - diverge_delta_rad
            else:
                diverge_angle_rad = base_angle_rad + diverge_delta_rad

            trunk_length = turnout.length * 0.35

            trunk_end_x = x + (trunk_length * math.cos(base_angle_rad))
            trunk_end_y = y + (trunk_length * math.sin(base_angle_rad))

            straight_remaining = turnout.length - trunk_length
            straight_end_x = trunk_end_x + (
                straight_remaining * math.cos(base_angle_rad)
            )
            straight_end_y = trunk_end_y + (
                straight_remaining * math.sin(base_angle_rad)
            )

            diverge_end_x = trunk_end_x + (
                turnout.diverge_length * math.cos(diverge_angle_rad)
            )
            diverge_end_y = trunk_end_y + (
                turnout.diverge_length * math.sin(diverge_angle_rad)
            )

            if self._point_near_segment(
                px=world_x,
                py=world_y,
                x1=x,
                y1=y,
                x2=trunk_end_x,
                y2=trunk_end_y,
                tolerance=hit_tolerance,
            ):
                return turnout

            if self._point_near_segment(
                px=world_x,
                py=world_y,
                x1=trunk_end_x,
                y1=trunk_end_y,
                x2=straight_end_x,
                y2=straight_end_y,
                tolerance=hit_tolerance,
            ):
                return turnout

            if self._point_near_segment(
                px=world_x,
                py=world_y,
                x1=trunk_end_x,
                y1=trunk_end_y,
                x2=diverge_end_x,
                y2=diverge_end_y,
                tolerance=hit_tolerance,
            ):
                return turnout

        return None

    def _point_near_segment(
        self,
        *,
        px: float,
        py: float,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        tolerance: float,
    ) -> bool:
        dx = x2 - x1
        dy = y2 - y1

        if dx == 0 and dy == 0:
            dist_sq = ((px - x1) ** 2) + ((py - y1) ** 2)
            return dist_sq <= (tolerance**2)

        seg_len_sq = (dx * dx) + (dy * dy)
        t = ((px - x1) * dx + (py - y1) * dy) / seg_len_sq
        t = max(0.0, min(1.0, t))

        nearest_x = x1 + (t * dx)
        nearest_y = y1 + (t * dy)

        dist_sq = ((px - nearest_x) ** 2) + ((py - nearest_y) ** 2)
        return dist_sq <= (tolerance**2)

    def _get_selected_track(self) -> StraightTrackElement | None:
        if self._selected_track_id is None:
            return None

        return next(
            (track for track in self._tracks if track.id == self._selected_track_id),
            None,
        )

    def _get_selected_turnout(self) -> TurnoutElement | None:
        if self._selected_turnout_id is None:
            return None

        return next(
            (
                turnout
                for turnout in self._turnouts
                if turnout.id == self._selected_turnout_id
            ),
            None,
        )

    def _get_turnout_endpoint_positions(
        self,
        turnout: TurnoutElement,
    ) -> dict[str, tuple[float, float]]:
        import math

        x = turnout.x
        y = turnout.y

        base_angle_rad = math.radians(turnout.angle_degrees)
        diverge_delta_rad = math.radians(turnout.diverge_angle_degrees)

        if turnout.is_left_hand:
            diverge_angle_rad = base_angle_rad - diverge_delta_rad
        else:
            diverge_angle_rad = base_angle_rad + diverge_delta_rad

        trunk_length = turnout.length * 0.35

        trunk_end_x = x + (trunk_length * math.cos(base_angle_rad))
        trunk_end_y = y + (trunk_length * math.sin(base_angle_rad))

        straight_remaining = turnout.length - trunk_length
        straight_end_x = trunk_end_x + (straight_remaining * math.cos(base_angle_rad))
        straight_end_y = trunk_end_y + (straight_remaining * math.sin(base_angle_rad))

        diverge_end_x = trunk_end_x + (
            turnout.diverge_length * math.cos(diverge_angle_rad)
        )
        diverge_end_y = trunk_end_y + (
            turnout.diverge_length * math.sin(diverge_angle_rad)
        )

        return {
            "trunk": (x, y),
            "straight": (straight_end_x, straight_end_y),
            "diverging": (diverge_end_x, diverge_end_y),
        }

    def _find_nearest_canvas_endpoint(
        self,
        world_x: float,
        world_y: float,
        *,
        ignore_track: StraightTrackElement | None = None,
        ignore_turnout: TurnoutElement | None = None,
        ignore_turnout_endpoint_name: str | None = None,
    ) -> SnapCandidate | None:
        import math

        best_candidate: SnapCandidate | None = None
        best_distance = 12.0

        # straight-track endpoints
        for track in self._tracks:
            if ignore_track is not None and track is ignore_track:
                continue

            for endpoint_index, (endpoint_x, endpoint_y) in enumerate(
                (
                    (track.x1, track.y1),
                    (track.x2, track.y2),
                ),
                start=1,
            ):
                distance = math.hypot(world_x - endpoint_x, world_y - endpoint_y)
                if distance <= best_distance:
                    is_valid = not self._canvas_endpoint_is_occupied(
                        endpoint_x,
                        endpoint_y,
                        target_track=track,
                        target_track_endpoint_index=endpoint_index,
                        ignore_track=ignore_track,
                        ignore_turnout=ignore_turnout,
                        ignore_turnout_endpoint_name=ignore_turnout_endpoint_name,
                    )
                    best_distance = distance
                    best_candidate = SnapCandidate(
                        x=endpoint_x,
                        y=endpoint_y,
                        is_valid=is_valid,
                        endpoint=None,  # type: ignore[arg-type]
                    )

        # turnout endpoints
        for turnout in self._turnouts:
            if ignore_turnout is not None and turnout is ignore_turnout:
                continue

            endpoints = self._get_turnout_endpoint_positions(turnout)
            for endpoint_name in ("trunk", "straight", "diverging"):
                if (
                    ignore_turnout is turnout
                    and ignore_turnout_endpoint_name == endpoint_name
                ):
                    continue

                endpoint_x, endpoint_y = endpoints[endpoint_name]
                distance = math.hypot(world_x - endpoint_x, world_y - endpoint_y)
                if distance <= best_distance:
                    is_valid = not self._canvas_endpoint_is_occupied(
                        endpoint_x,
                        endpoint_y,
                        target_turnout=turnout,
                        target_turnout_endpoint_name=endpoint_name,
                        ignore_track=ignore_track,
                        ignore_turnout=ignore_turnout,
                        ignore_turnout_endpoint_name=ignore_turnout_endpoint_name,
                    )
                    best_distance = distance
                    best_candidate = SnapCandidate(
                        x=endpoint_x,
                        y=endpoint_y,
                        is_valid=is_valid,
                        endpoint=None,  # type: ignore[arg-type]
                    )

        return best_candidate

    def _canvas_endpoint_is_occupied(
        self,
        endpoint_x: float,
        endpoint_y: float,
        *,
        target_track: StraightTrackElement | None = None,
        target_track_endpoint_index: int | None = None,
        target_turnout: TurnoutElement | None = None,
        target_turnout_endpoint_name: str | None = None,
        ignore_track: StraightTrackElement | None = None,
        ignore_turnout: TurnoutElement | None = None,
        ignore_turnout_endpoint_name: str | None = None,
    ) -> bool:
        tolerance = 1.0

        # check straight-track endpoints
        for track in self._tracks:
            if ignore_track is not None and track is ignore_track:
                continue

            for endpoint_index, (other_x, other_y) in enumerate(
                (
                    (track.x1, track.y1),
                    (track.x2, track.y2),
                ),
                start=1,
            ):
                if (
                    target_track is track
                    and target_track_endpoint_index == endpoint_index
                ):
                    continue

                dx = endpoint_x - other_x
                dy = endpoint_y - other_y
                if (dx * dx + dy * dy) <= (tolerance * tolerance):
                    return True

        # check turnout endpoints
        for turnout in self._turnouts:
            if ignore_turnout is not None and turnout is ignore_turnout:
                continue

            endpoints = self._get_turnout_endpoint_positions(turnout)
            for endpoint_name in ("trunk", "straight", "diverging"):
                if (
                    target_turnout is turnout
                    and target_turnout_endpoint_name == endpoint_name
                ):
                    continue

                if (
                    ignore_turnout is turnout
                    and ignore_turnout_endpoint_name == endpoint_name
                ):
                    continue

                other_x, other_y = endpoints[endpoint_name]
                dx = endpoint_x - other_x
                dy = endpoint_y - other_y
                if (dx * dx + dy * dy) <= (tolerance * tolerance):
                    return True

        return False

    def _find_selected_turnout_endpoint_at_point(
        self,
        world_x: float,
        world_y: float,
    ) -> str | None:
        selected_turnout = self._get_selected_turnout()
        if selected_turnout is None:
            return None

        hit_radius = 8.0
        endpoints = self._get_turnout_endpoint_positions(selected_turnout)

        for endpoint_name in ("trunk", "straight", "diverging"):
            endpoint_x, endpoint_y = endpoints[endpoint_name]
            if self._point_within_radius(
                px=world_x,
                py=world_y,
                cx=endpoint_x,
                cy=endpoint_y,
                radius=hit_radius,
            ):
                return endpoint_name

        return None

    def _endpoint_is_coincident(
        self,
        track: StraightTrackElement,
        endpoint_index: int,
    ) -> bool:
        if endpoint_index == 1:
            x, y = track.x1, track.y1
        else:
            x, y = track.x2, track.y2

        tolerance = 1.0

        for other in self._tracks:
            if other is track:
                continue

            for ox, oy in (
                (other.x1, other.y1),
                (other.x2, other.y2),
            ):
                dx = x - ox
                dy = y - oy
                if (dx * dx + dy * dy) <= (tolerance * tolerance):
                    return True

        return False

    def _get_active_drag_track(self) -> StraightTrackElement | None:
        if self._active_track_drag_id is None:
            return None

        return next(
            (track for track in self._tracks if track.id == self._active_track_drag_id),
            None,
        )

    def _get_active_drag_turnout(self) -> TurnoutElement | None:
        if self._active_turnout_drag_id is None:
            return None

        return next(
            (
                turnout
                for turnout in self._turnouts
                if turnout.id == self._active_turnout_drag_id
            ),
            None,
        )

    def _move_track_endpoint(
        self,
        track: StraightTrackElement,
        endpoint_index: int,
        world_x: float,
        world_y: float,
    ) -> None:
        if endpoint_index == 1:
            track.x1 = world_x
            track.y1 = world_y
            return

        if endpoint_index == 2:
            track.x2 = world_x
            track.y2 = world_y

    def _move_track_body(
        self,
        track: StraightTrackElement,
        dx: float,
        dy: float,
    ) -> None:
        track.move(dx, dy)

    def _move_turnout_body(
        self,
        turnout: TurnoutElement,
        dx: float,
        dy: float,
    ) -> None:
        turnout.move(dx, dy)

    def _move_turnout_endpoint(
        self,
        turnout: TurnoutElement,
        endpoint_name: str,
        world_x: float,
        world_y: float,
    ) -> None:
        import math

        # trunk endpoint drag = move the whole turnout while keeping the
        # trunk endpoint directly under the mouse
        if endpoint_name == "trunk":
            turnout.x = world_x
            turnout.y = world_y
            return

        trunk_x = turnout.x
        trunk_y = turnout.y

        base_angle_rad = math.radians(turnout.angle_degrees)
        trunk_length = turnout.length * 0.35

        split_x = trunk_x + (trunk_length * math.cos(base_angle_rad))
        split_y = trunk_y + (trunk_length * math.sin(base_angle_rad))

        if endpoint_name == "straight":
            dx = world_x - split_x
            dy = world_y - split_y

            straight_length = max(20.0, math.hypot(dx, dy))
            new_base_angle_deg = math.degrees(math.atan2(dy, dx))

            turnout.angle_degrees = new_base_angle_deg
            turnout.length = trunk_length + straight_length
            return

        if endpoint_name == "diverging":
            dx = world_x - split_x
            dy = world_y - split_y

            turnout.diverge_length = max(20.0, math.hypot(dx, dy))

            diverge_angle_rad = math.atan2(dy, dx)
            base_angle_rad = math.radians(turnout.angle_degrees)
            delta_degrees = math.degrees(diverge_angle_rad - base_angle_rad)

            turnout.diverge_angle_degrees = max(1.0, abs(delta_degrees))

    def _move_turnout_endpoint_to_snap_candidate(
        self,
        turnout: TurnoutElement,
        endpoint_name: str,
        candidate: SnapCandidate,
    ) -> None:
        self._move_turnout_endpoint(
            turnout,
            endpoint_name,
            candidate.x,
            candidate.y,
        )

    def _commit_turnout_body_snap(
        self,
        turnout: TurnoutElement,
        endpoint_name: str,
        candidate: SnapCandidate,
    ) -> None:
        endpoints = self._get_turnout_endpoint_positions(turnout)
        endpoint_x, endpoint_y = endpoints[endpoint_name]

        dx = candidate.x - endpoint_x
        dy = candidate.y - endpoint_y

        turnout.move(dx, dy)

    def _mouse_world_position(self, event: tk.Event) -> tuple[float, float]:
        return (
            self.canvas.canvasx(event.x),
            self.canvas.canvasy(event.y),
        )

    def _clear_endpoint_snap_candidate(self) -> None:
        self._endpoint_snap_candidate = None

    def _set_endpoint_snap_status_message(self) -> None:
        candidate = self._endpoint_snap_candidate
        if candidate is None:
            return

        if candidate.is_valid:
            self._set_status_message("Snap candidate found")
        else:
            self._set_status_message("Snap blocked: endpoint already connected.")

    def _find_body_drag_snap_candidate(
        self,
        drag_track: StraightTrackElement,
    ) -> tuple[int, SnapCandidate] | None:
        import math

        candidates: list[tuple[float, int, SnapCandidate]] = []

        endpoint_1_candidate = self._find_nearest_canvas_endpoint(
            drag_track.x1,
            drag_track.y1,
            ignore_track=drag_track,
        )
        if endpoint_1_candidate is not None:
            distance_1 = math.hypot(
                drag_track.x1 - endpoint_1_candidate.x,
                drag_track.y1 - endpoint_1_candidate.y,
            )
            candidates.append((distance_1, 1, endpoint_1_candidate))

        endpoint_2_candidate = self._find_nearest_canvas_endpoint(
            drag_track.x2,
            drag_track.y2,
            ignore_track=drag_track,
        )
        if endpoint_2_candidate is not None:
            distance_2 = math.hypot(
                drag_track.x2 - endpoint_2_candidate.x,
                drag_track.y2 - endpoint_2_candidate.y,
            )
            candidates.append((distance_2, 2, endpoint_2_candidate))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item[0])
        _, endpoint_index, candidate = candidates[0]
        return endpoint_index, candidate

    def _find_turnout_body_drag_snap_candidate(
        self,
        drag_turnout: TurnoutElement,
    ) -> tuple[str, SnapCandidate] | None:
        import math

        endpoints = self._get_turnout_endpoint_positions(drag_turnout)
        candidates: list[tuple[float, str, SnapCandidate]] = []

        for endpoint_name in ("trunk", "straight", "diverging"):
            endpoint_x, endpoint_y = endpoints[endpoint_name]

            candidate = self._find_nearest_canvas_endpoint(
                endpoint_x,
                endpoint_y,
                ignore_turnout=drag_turnout,
                ignore_turnout_endpoint_name=endpoint_name,
            )
            if candidate is None:
                continue

            distance = math.hypot(endpoint_x - candidate.x, endpoint_y - candidate.y)
            candidates.append((distance, endpoint_name, candidate))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item[0])
        _, endpoint_name, candidate = candidates[0]
        return endpoint_name, candidate

    def _commit_body_drag_snap(
        self,
        drag_track: StraightTrackElement,
        endpoint_index: int,
        candidate,
    ) -> None:
        if endpoint_index == 1:
            dx = candidate.x - drag_track.x1
            dy = candidate.y - drag_track.y1
        else:
            dx = candidate.x - drag_track.x2
            dy = candidate.y - drag_track.y2

        self._move_track_body(drag_track, dx, dy)

    def _find_selected_track_endpoint_at_point(
        self,
        world_x: float,
        world_y: float,
    ) -> int | None:
        selected_track = self._get_selected_track()
        if selected_track is None:
            return None

        hit_radius = 8.0

        if self._point_within_radius(
            px=world_x,
            py=world_y,
            cx=selected_track.x1,
            cy=selected_track.y1,
            radius=hit_radius,
        ):
            return 1

        if self._point_within_radius(
            px=world_x,
            py=world_y,
            cx=selected_track.x2,
            cy=selected_track.y2,
            radius=hit_radius,
        ):
            return 2

        return None

    def _is_point_on_selected_track_body(
        self,
        world_x: float,
        world_y: float,
    ) -> bool:
        selected_track = self._get_selected_track()
        if selected_track is None:
            return False

        return self._point_near_segment(
            px=world_x,
            py=world_y,
            x1=selected_track.x1,
            y1=selected_track.y1,
            x2=selected_track.x2,
            y2=selected_track.y2,
            tolerance=6.0,
        )

    def _is_point_on_selected_turnout(
        self,
        world_x: float,
        world_y: float,
    ) -> bool:
        if self._selected_turnout_id is None:
            return False

        turnout = next(
            (t for t in self._turnouts if t.id == self._selected_turnout_id),
            None,
        )
        if turnout is None:
            return False

        return self._find_turnout_at_point(world_x, world_y) is not None

    def _update_track_hover_cursor(self) -> None:
        if self._creating_track:
            self.canvas.configure(cursor=self.CURSOR_DEFAULT)
            return

        if self._last_mouse_canvas_x is None or self._last_mouse_canvas_y is None:
            self.canvas.configure(cursor=self.CURSOR_DEFAULT)
            return

        world_x = self.canvas.canvasx(self._last_mouse_canvas_x)
        world_y = self.canvas.canvasy(self._last_mouse_canvas_y)

        if self._is_point_on_group_selected_track_body(world_x, world_y):
            self.canvas.configure(cursor=self.CURSOR_SELECTABLE)
            return

        if self._is_point_on_group_selected_turnout(world_x, world_y):
            self.canvas.configure(cursor=self.CURSOR_SELECTABLE)
            return

        if self._find_selected_track_endpoint_at_point(world_x, world_y) is not None:
            self.canvas.configure(cursor=self.CURSOR_SELECTABLE)
            return

        if self._find_selected_turnout_endpoint_at_point(world_x, world_y) is not None:
            self.canvas.configure(cursor=self.CURSOR_SELECTABLE)
            return

        if self._is_point_on_selected_track_body(world_x, world_y):
            self.canvas.configure(cursor=self.CURSOR_SELECTABLE)
            return

        if self._is_point_on_selected_turnout(world_x, world_y):
            self.canvas.configure(cursor=self.CURSOR_SELECTABLE)
            return

        if self._find_track_at_point(world_x, world_y) is not None:
            self.canvas.configure(cursor=self.CURSOR_SELECTABLE)
            return

        if self._find_turnout_at_point(world_x, world_y) is not None:
            self.canvas.configure(cursor=self.CURSOR_SELECTABLE)
            return

        self.canvas.configure(cursor=self.CURSOR_DEFAULT)

    def _point_within_radius(
        self,
        *,
        px: float,
        py: float,
        cx: float,
        cy: float,
        radius: float,
    ) -> bool:
        dx = px - cx
        dy = py - cy
        return (dx * dx) + (dy * dy) <= (radius * radius)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def redraw(self) -> None:
        self.canvas.delete("all")
        self._draw_background()
        self._draw_grid_if_enabled()
        self._draw_tracks()
        self._draw_turnouts()
        self._draw_guides()
        self._draw_selected_track_handles()
        self._draw_selected_turnout_handles()
        self._draw_endpoint_snap_preview()
        self._draw_endpoint_snap_flash()
        self._draw_track_snap_preview()
        self._draw_marquee_selection()
        self._redraw_rulers()

    def _draw_background(self) -> None:
        self.canvas.create_rectangle(
            0,
            0,
            self.world_width,
            self.world_height,
            fill="white",
            outline="",
        )

    def _draw_grid_if_enabled(self) -> None:

        if not self._show_grid:
            return

        spacing = self.grid_spacing
        color = "#efefef"

        x = 0
        while x <= self.world_width:
            self.canvas.create_line(
                x,
                0,
                x,
                self.world_height,
                fill=color,
                tags=("grid",),
            )
            x += spacing

        y = 0
        while y <= self.world_height:
            self.canvas.create_line(
                0,
                y,
                self.world_width,
                y,
                fill=color,
                tags=("grid",),
            )
            y += spacing

    def _draw_tracks(self) -> None:
        for track in self._tracks:
            is_selected = (
                track.id == self._selected_track_id
                or track.id in self._selected_track_ids
            )
            if is_selected:
                self.canvas.create_line(
                    track.x1,
                    track.y1,
                    track.x2,
                    track.y2,
                    fill="#ff9900",
                    width=8,
                    capstyle=tk.ROUND,
                    tags=("track_selection", track.id),
                )

            self.canvas.create_line(
                track.x1,
                track.y1,
                track.x2,
                track.y2,
                fill="#444",
                width=4,
                capstyle=tk.ROUND,
                tags=("track", track.id),
            )

            # default endpoint dots for all committed tracks
            endpoint_radius = 4
            self.canvas.create_oval(
                track.x1 - endpoint_radius,
                track.y1 - endpoint_radius,
                track.x1 + endpoint_radius,
                track.y1 + endpoint_radius,
                fill="#222",
                outline="",
                tags=("track_endpoint", track.id, f"{track.id}:endpoint1"),
            )
            self.canvas.create_oval(
                track.x2 - endpoint_radius,
                track.y2 - endpoint_radius,
                track.x2 + endpoint_radius,
                track.y2 + endpoint_radius,
                fill="#222",
                outline="",
                tags=("track_endpoint", track.id, f"{track.id}:endpoint2"),
            )

        if self._temp_track is not None:
            t = self._temp_track
            self.canvas.create_line(
                t.x1,
                t.y1,
                t.x2,
                t.y2,
                fill="#888",
                width=4,
                dash=(4, 2),
            )

            endpoint_radius = 4
            self.canvas.create_oval(
                t.x1 - endpoint_radius,
                t.y1 - endpoint_radius,
                t.x1 + endpoint_radius,
                t.y1 + endpoint_radius,
                fill="#555",
                outline="",
                tags=("temp_track_endpoint",),
            )
            self.canvas.create_oval(
                t.x2 - endpoint_radius,
                t.y2 - endpoint_radius,
                t.x2 + endpoint_radius,
                t.y2 + endpoint_radius,
                fill="#555",
                outline="",
                tags=("temp_track_endpoint",),
            )

    def _draw_turnouts(self) -> None:
        import math

        for turnout in self._turnouts:
            x = turnout.x
            y = turnout.y

            base_angle_rad = math.radians(turnout.angle_degrees)
            diverge_delta_rad = math.radians(turnout.diverge_angle_degrees)

            if turnout.is_left_hand:
                diverge_angle_rad = base_angle_rad - diverge_delta_rad
            else:
                diverge_angle_rad = base_angle_rad + diverge_delta_rad

            trunk_length = turnout.length * 0.35

            trunk_end_x = x + (trunk_length * math.cos(base_angle_rad))
            trunk_end_y = y + (trunk_length * math.sin(base_angle_rad))

            straight_remaining = turnout.length - trunk_length
            straight_end_x = trunk_end_x + (
                straight_remaining * math.cos(base_angle_rad)
            )
            straight_end_y = trunk_end_y + (
                straight_remaining * math.sin(base_angle_rad)
            )

            diverge_end_x = trunk_end_x + (
                turnout.diverge_length * math.cos(diverge_angle_rad)
            )
            diverge_end_y = trunk_end_y + (
                turnout.diverge_length * math.sin(diverge_angle_rad)
            )

            is_selected = (
                turnout.id == self._selected_turnout_id
                or turnout.id in self._selected_turnout_ids
            )
            if is_selected:
                self.canvas.create_line(
                    x,
                    y,
                    trunk_end_x,
                    trunk_end_y,
                    fill="#ff9900",
                    width=8,
                    capstyle=tk.ROUND,
                    tags=("turnout_selection", turnout.id),
                )
                self.canvas.create_line(
                    trunk_end_x,
                    trunk_end_y,
                    straight_end_x,
                    straight_end_y,
                    fill="#ff9900",
                    width=8,
                    capstyle=tk.ROUND,
                    tags=("turnout_selection", turnout.id),
                )
                self.canvas.create_line(
                    trunk_end_x,
                    trunk_end_y,
                    diverge_end_x,
                    diverge_end_y,
                    fill="#ff9900",
                    width=8,
                    capstyle=tk.ROUND,
                    tags=("turnout_selection", turnout.id),
                )

            # trunk
            self.canvas.create_line(
                x,
                y,
                trunk_end_x,
                trunk_end_y,
                fill="#444",
                width=4,
                capstyle=tk.ROUND,
                tags=("turnout", turnout.id),
            )

            # straight route
            self.canvas.create_line(
                trunk_end_x,
                trunk_end_y,
                straight_end_x,
                straight_end_y,
                fill="#444",
                width=4,
                capstyle=tk.ROUND,
                tags=("turnout", turnout.id),
            )

            # diverging route
            self.canvas.create_line(
                trunk_end_x,
                trunk_end_y,
                diverge_end_x,
                diverge_end_y,
                fill="#444",
                width=4,
                capstyle=tk.ROUND,
                tags=("turnout", turnout.id),
            )

            r = 4

            # trunk start endpoint
            self.canvas.create_oval(
                x - r,
                y - r,
                x + r,
                y + r,
                fill="#222",
                outline="",
                tags=("turnout_endpoint", turnout.id, f"{turnout.id}:trunk"),
            )

            # split point marker
            self.canvas.create_oval(
                trunk_end_x - r,
                trunk_end_y - r,
                trunk_end_x + r,
                trunk_end_y + r,
                fill="#222",
                outline="",
                tags=("turnout_joint", turnout.id),
            )

            # straight endpoint
            self.canvas.create_oval(
                straight_end_x - r,
                straight_end_y - r,
                straight_end_x + r,
                straight_end_y + r,
                fill="#222",
                outline="",
                tags=("turnout_endpoint", turnout.id, f"{turnout.id}:straight"),
            )

            # diverging endpoint
            self.canvas.create_oval(
                diverge_end_x - r,
                diverge_end_y - r,
                diverge_end_x + r,
                diverge_end_y + r,
                fill="#222",
                outline="",
                tags=("turnout_endpoint", turnout.id, f"{turnout.id}:diverging"),
            )

    def _draw_track_snap_preview(self) -> None:
        if not self._creating_track or self._temp_track is None:
            return

        if self._track_snap_preview_x is None or self._track_snap_preview_y is None:
            return

        x = self._track_snap_preview_x
        y = self._track_snap_preview_y

        preview_color = self.GUIDE_COLOR

        if self._track_snap_preview_show_vertical:
            self.canvas.create_line(
                x,
                0,
                x,
                self.world_height,
                fill=preview_color,
                width=2,
                dash=(4, 2),
                tags=("track_snap_preview", "track_snap_preview_vertical"),
            )

        if self._track_snap_preview_show_horizontal:
            self.canvas.create_line(
                0,
                y,
                self.world_width,
                y,
                fill=preview_color,
                width=2,
                dash=(4, 2),
                tags=("track_snap_preview", "track_snap_preview_horizontal"),
            )

        if (
            self._track_snap_preview_show_vertical
            and self._track_snap_preview_show_horizontal
        ):
            self.canvas.create_line(
                x - 8,
                y,
                x + 8,
                y,
                fill=preview_color,
                width=2,
                tags=("track_snap_preview", "track_snap_preview_marker"),
            )
            self.canvas.create_line(
                x,
                y - 8,
                x,
                y + 8,
                fill=preview_color,
                width=2,
                tags=("track_snap_preview", "track_snap_preview_marker"),
            )
            self.canvas.create_oval(
                x - 5,
                y - 5,
                x + 5,
                y + 5,
                outline=preview_color,
                width=2,
                tags=("track_snap_preview", "track_snap_preview_marker"),
            )
        elif (
            self._track_snap_preview_show_vertical
            or self._track_snap_preview_show_horizontal
        ):
            self.canvas.create_oval(
                x - 5,
                y - 5,
                x + 5,
                y + 5,
                outline=preview_color,
                width=2,
                tags=("track_snap_preview", "track_snap_preview_marker"),
            )

    def _draw_marquee_selection(self) -> None:
        if (
            not self._marquee_selecting
            or self._marquee_start_world_x is None
            or self._marquee_start_world_y is None
            or self._marquee_current_world_x is None
            or self._marquee_current_world_y is None
        ):
            return

        self.canvas.create_rectangle(
            self._marquee_start_world_x,
            self._marquee_start_world_y,
            self._marquee_current_world_x,
            self._marquee_current_world_y,
            outline="#2f7fff",
            width=1,
            dash=(4, 2),
            fill="",
            tags=("marquee_selection",),
        )

    def _draw_endpoint_snap_preview(self) -> None:
        candidate = self._endpoint_snap_candidate
        if candidate is None:
            return

        x = candidate.x
        y = candidate.y

        if candidate.is_valid:
            color = "#00cc66"  # green
        else:
            color = "#ff4444"  # red

        self.canvas.create_oval(
            x - 6,
            y - 6,
            x + 6,
            y + 6,
            outline=color,
            width=2,
            tags=("endpoint_snap_preview",),
        )

    def _draw_endpoint_snap_flash(self) -> None:
        if self._endpoint_snap_flash is None:
            return

        x, y = self._endpoint_snap_flash

        self.canvas.create_oval(
            x - 6,
            y - 6,
            x + 6,
            y + 6,
            fill="#00cc66",
            outline="",
            tags=("endpoint_snap_flash",),
        )

    def _draw_selected_track_handles(self) -> None:
        if self._has_group_selection():
            return

        if self._selected_track_id is None:
            return

        selected_track = next(
            (track for track in self._tracks if track.id == self._selected_track_id),
            None,
        )
        if selected_track is None:
            return

        outer_radius = 7
        center_radius = 3

        for x, y in (
            (selected_track.x1, selected_track.y1),
            (selected_track.x2, selected_track.y2),
        ):
            # orange outer ring
            self.canvas.create_oval(
                x - outer_radius,
                y - outer_radius,
                x + outer_radius,
                y + outer_radius,
                fill="white",
                outline="#ff9900",
                width=2,
                tags=("track_handle", selected_track.id),
            )

            # black center dot to preserve the endpoint visually
            self.canvas.create_oval(
                x - center_radius,
                y - center_radius,
                x + center_radius,
                y + center_radius,
                fill="#222",
                outline="",
                tags=("track_handle_center", selected_track.id),
            )

    def _draw_selected_turnout_handles(self) -> None:
        import math

        if self._has_group_selection():
            return

        if self._selected_turnout_id is None:
            return

        selected_turnout = next(
            (
                turnout
                for turnout in self._turnouts
                if turnout.id == self._selected_turnout_id
            ),
            None,
        )
        if selected_turnout is None:
            return

        x = selected_turnout.x
        y = selected_turnout.y

        base_angle_rad = math.radians(selected_turnout.angle_degrees)
        diverge_delta_rad = math.radians(selected_turnout.diverge_angle_degrees)

        if selected_turnout.is_left_hand:
            diverge_angle_rad = base_angle_rad - diverge_delta_rad
        else:
            diverge_angle_rad = base_angle_rad + diverge_delta_rad

        trunk_length = selected_turnout.length * 0.35

        trunk_end_x = x + (trunk_length * math.cos(base_angle_rad))
        trunk_end_y = y + (trunk_length * math.sin(base_angle_rad))

        straight_remaining = selected_turnout.length - trunk_length
        straight_end_x = trunk_end_x + (straight_remaining * math.cos(base_angle_rad))
        straight_end_y = trunk_end_y + (straight_remaining * math.sin(base_angle_rad))

        diverge_end_x = trunk_end_x + (
            selected_turnout.diverge_length * math.cos(diverge_angle_rad)
        )
        diverge_end_y = trunk_end_y + (
            selected_turnout.diverge_length * math.sin(diverge_angle_rad)
        )

        outer_radius = 7
        center_radius = 3

        for handle_x, handle_y in (
            (x, y),  # trunk endpoint
            (straight_end_x, straight_end_y),  # straight endpoint
            (diverge_end_x, diverge_end_y),  # diverging endpoint
        ):
            self.canvas.create_oval(
                handle_x - outer_radius,
                handle_y - outer_radius,
                handle_x + outer_radius,
                handle_y + outer_radius,
                fill="white",
                outline="#ff9900",
                width=2,
                tags=("turnout_handle", selected_turnout.id),
            )

            self.canvas.create_oval(
                handle_x - center_radius,
                handle_y - center_radius,
                handle_x + center_radius,
                handle_y + center_radius,
                fill="#222",
                outline="",
                tags=("turnout_handle_center", selected_turnout.id),
            )

    def _draw_guides(self) -> None:
        if not self._show_rulers:
            return

        guide_color = self.GUIDE_COLOR

        # committed vertical guides
        for x in self.guides.vertical_guides:
            self.canvas.create_line(
                x,
                0,
                x,
                self.world_height,
                fill=guide_color,
                width=1,
                tags=("guide", "guide_vertical"),
            )

        # committed horizontal guides
        for y in self.guides.horizontal_guides:
            self.canvas.create_line(
                0,
                y,
                self.world_width,
                y,
                fill=guide_color,
                width=1,
                tags=("guide", "guide_horizontal"),
            )

        # temporary drag guide: vertical
        if self._temp_vertical_guide_x is not None:
            self.canvas.create_line(
                self._temp_vertical_guide_x,
                0,
                self._temp_vertical_guide_x,
                self.world_height,
                fill=guide_color,
                width=1,
                dash=(4, 2),
                tags=("guide", "guide_vertical_temp"),
            )

        # temporary drag guide: horizontal
        if self._temp_horizontal_guide_y is not None:
            self.canvas.create_line(
                0,
                self._temp_horizontal_guide_y,
                self.world_width,
                self._temp_horizontal_guide_y,
                fill=guide_color,
                width=1,
                dash=(4, 2),
                tags=("guide", "guide_horizontal_temp"),
            )

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------
    def _notify_mouse_position(self) -> None:
        if self.on_mouse_move is None:
            return

        if self._last_mouse_canvas_x is None or self._last_mouse_canvas_y is None:
            self.on_mouse_move(None, None)
            return

        world_x = self.canvas.canvasx(self._last_mouse_canvas_x)
        world_y = self.canvas.canvasy(self._last_mouse_canvas_y)
        self.on_mouse_move(world_x, world_y)

    def _set_status_message(self, message: str) -> None:
        if self.on_status_message is None:
            return
        self.on_status_message(message)

    def _on_canvas_release(self, event: tk.Event) -> None:
        # ------------------------------------------------------------------
        # Marquee selection release
        # Finalize the marquee rectangle into a real selected-ID set.
        # ------------------------------------------------------------------
        if self._marquee_selecting:
            self._marquee_current_world_x = self.canvas.canvasx(event.x)
            self._marquee_current_world_y = self.canvas.canvasy(event.y)
            self._commit_marquee_selection()

            self._marquee_selecting = False
            self._marquee_start_world_x = None
            self._marquee_start_world_y = None
            self._marquee_current_world_x = None
            self._marquee_current_world_y = None

            self.redraw()

            total_selected = len(self._selected_track_ids) + len(
                self._selected_turnout_ids
            )
            self._set_status_message(f"Selected {total_selected} piece(s).")
            return

        # ------------------------------------------------------------------
        # Group drag release
        # End multi-selection movement.
        # Option B first pass:
        # - snap selected group to grid on release
        # - only when Snap is enabled from the toolbar
        # ------------------------------------------------------------------
        if self._group_dragging:
            if self._show_snap:
                pivot = self._get_selected_group_rotation_pivot()
                if pivot is not None:
                    pivot_x, pivot_y = pivot
                    snapped_x, snapped_y = self._snap_point_to_grid(pivot_x, pivot_y)

                    dx = snapped_x - pivot_x
                    dy = snapped_y - pivot_y

                    if abs(dx) > 1e-6 or abs(dy) > 1e-6:
                        self._move_selected_group(dx, dy)

            self._group_dragging = False
            self._drag_start_world_x = None
            self._drag_start_world_y = None
            self.redraw()

            if self._show_snap:
                self._set_status_message("Selected group moved (grid snapped).")
            else:
                self._set_status_message("Selected group moved.")

            return

        # ------------------------------------------------------------------
        # Track creation release
        # Commit the temporary track, optionally snapping endpoint 2 first.
        # ------------------------------------------------------------------
        if self._creating_track and self._temp_track is not None:
            if (
                self._show_snap
                and self._endpoint_snap_candidate is not None
                and self._endpoint_snap_candidate.is_valid
            ):
                snap = self._endpoint_snap_candidate
                self._temp_track.set_endpoint_2(snap.x, snap.y)

                self._endpoint_snap_flash = (snap.x, snap.y)
                self.after(150, self._clear_snap_flash)

                self._set_status_message("Track snapped to endpoint")
            else:
                self._set_status_message("Track created")

            self._tracks.append(self._temp_track)
            self._temp_track = None
            self._creating_track = False
            self._clear_endpoint_snap_candidate()

            self.redraw()
            self._update_canvas_cursor_for_mode()

        # ------------------------------------------------------------------
        # Straight-track drag release
        # Handles either:
        # - endpoint snap/move completion
        # - body-drag dock/move completion
        # ------------------------------------------------------------------
        elif self._active_endpoint_drag is not None:
            if (
                self._show_snap
                and self._endpoint_snap_candidate is not None
                and self._endpoint_snap_candidate.is_valid
            ):
                snap = self._endpoint_snap_candidate
                drag_track = self._get_active_drag_track()
                if drag_track is not None:
                    self._move_track_endpoint(
                        drag_track,
                        self._active_endpoint_drag,
                        snap.x,
                        snap.y,
                    )

                self._endpoint_snap_flash = (snap.x, snap.y)
                self.after(150, self._clear_snap_flash)

                self._set_status_message(
                    f"Endpoint {self._active_endpoint_drag} snapped."
                )
            else:
                self._set_status_message(
                    f"Endpoint {self._active_endpoint_drag} moved."
                )

            self._body_drag_snap_endpoint_index = None
            self._clear_endpoint_snap_candidate()
            self.redraw()

        elif self._active_track_drag_id is not None:
            drag_track = self._get_active_drag_track()
            if (
                self._show_snap
                and drag_track is not None
                and self._body_drag_snap_endpoint_index is not None
                and self._endpoint_snap_candidate is not None
                and self._endpoint_snap_candidate.is_valid
            ):
                snap = self._endpoint_snap_candidate
                self._commit_body_drag_snap(
                    drag_track,
                    self._body_drag_snap_endpoint_index,
                    snap,
                )

                self._endpoint_snap_flash = (snap.x, snap.y)
                self.after(150, self._clear_snap_flash)

                self._set_status_message("Track docked to endpoint.")
            else:
                if self._show_snap and drag_track is not None:
                    midpoint_x = (drag_track.x1 + drag_track.x2) / 2.0
                    midpoint_y = (drag_track.y1 + drag_track.y2) / 2.0
                    snapped_x, snapped_y = self._snap_point_to_grid(
                        midpoint_x,
                        midpoint_y,
                    )

                    dx = snapped_x - midpoint_x
                    dy = snapped_y - midpoint_y

                    if abs(dx) > 1e-6 or abs(dy) > 1e-6:
                        self._move_track_body(drag_track, dx, dy)

                    self._set_status_message("Track moved (grid snapped).")
                else:
                    self._set_status_message("Track moved.")

            self._body_drag_snap_endpoint_index = None
            self._clear_endpoint_snap_candidate()
            self.redraw()

        # ------------------------------------------------------------------
        # Turnout drag release
        # Handles either:
        # - turnout endpoint snap/move completion
        # - turnout body dock/move completion
        # ------------------------------------------------------------------
        elif self._active_turnout_drag_id is not None:
            drag_turnout = self._get_active_drag_turnout()

            if self._active_turnout_endpoint_drag is not None:
                if (
                    self._show_snap
                    and drag_turnout is not None
                    and self._endpoint_snap_candidate is not None
                    and self._endpoint_snap_candidate.is_valid
                ):
                    snap = self._endpoint_snap_candidate
                    self._move_turnout_endpoint_to_snap_candidate(
                        drag_turnout,
                        self._active_turnout_endpoint_drag,
                        snap,
                    )

                    self._endpoint_snap_flash = (snap.x, snap.y)
                    self.after(150, self._clear_snap_flash)

                    self._set_status_message(
                        f"Turnout endpoint snapped: {self._active_turnout_endpoint_drag}."
                    )
                else:
                    self._set_status_message(
                        f"Turnout endpoint moved: {self._active_turnout_endpoint_drag}."
                    )

                self._clear_endpoint_snap_candidate()

            else:
                if (
                    self._show_snap
                    and drag_turnout is not None
                    and self._turnout_body_drag_snap_endpoint_name is not None
                    and self._endpoint_snap_candidate is not None
                    and self._endpoint_snap_candidate.is_valid
                ):
                    snap = self._endpoint_snap_candidate
                    self._commit_turnout_body_snap(
                        drag_turnout,
                        self._turnout_body_drag_snap_endpoint_name,
                        snap,
                    )

                    self._endpoint_snap_flash = (snap.x, snap.y)
                    self.after(150, self._clear_snap_flash)

                    self._set_status_message("Turnout docked to endpoint.")
                else:
                    if self._show_snap and drag_turnout is not None:
                        snapped_x, snapped_y = self._snap_point_to_grid(
                            drag_turnout.x,
                            drag_turnout.y,
                        )

                        dx = snapped_x - drag_turnout.x
                        dy = snapped_y - drag_turnout.y

                        if abs(dx) > 1e-6 or abs(dy) > 1e-6:
                            self._move_turnout_body(drag_turnout, dx, dy)

                        self._set_status_message("Turnout moved (grid snapped).")
                    else:
                        self._set_status_message("Turnout moved.")

                self._turnout_body_drag_snap_endpoint_name = None
                self._clear_endpoint_snap_candidate()

            self.redraw()

        # ------------------------------------------------------------------
        # Common drag-state cleanup
        # ------------------------------------------------------------------
        self._active_track_drag_id = None
        self._active_turnout_drag_id = None
        self._active_endpoint_drag = None
        self._active_turnout_endpoint_drag = None
        self._turnout_body_drag_snap_endpoint_name = None
        self._group_dragging = False
        self._drag_start_world_x = None
        self._drag_start_world_y = None

    def _clear_snap_flash(self) -> None:
        self._endpoint_snap_flash = None
        self.redraw()

    def _on_canvas_motion(self, event: tk.Event) -> None:
        # ------------------------------------------------------------------
        # Mouse position / cursor refresh
        # ------------------------------------------------------------------
        self._last_mouse_canvas_x = event.x
        self._last_mouse_canvas_y = event.y
        self._notify_mouse_position()
        self._update_guide_hover_cursor()
        self._update_canvas_cursor_for_mode()

        world_x = self.canvas.canvasx(event.x)
        world_y = self.canvas.canvasy(event.y)

        # ------------------------------------------------------------------
        # Marquee selection preview
        # While Ctrl-marquee is active, the drag rectangle owns motion.
        # ------------------------------------------------------------------
        if self._marquee_selecting:
            self._marquee_current_world_x = world_x
            self._marquee_current_world_y = world_y
            self.redraw()
            return

        # ------------------------------------------------------------------
        # Group drag
        # Move all currently selected pieces together.
        # This pass does NOT do group snap docking.
        # ------------------------------------------------------------------
        if self._group_dragging:
            if (
                self._drag_start_world_x is not None
                and self._drag_start_world_y is not None
            ):
                dx = world_x - self._drag_start_world_x
                dy = world_y - self._drag_start_world_y
                self._move_selected_group(dx, dy)
                self._drag_start_world_x = world_x
                self._drag_start_world_y = world_y
                self.redraw()
            return

        # ------------------------------------------------------------------
        # Active straight-track drag
        # Handles either:
        # - endpoint drag
        # - whole-track body drag
        # ------------------------------------------------------------------
        if self._active_track_drag_id is not None:
            drag_track = self._get_active_drag_track()
            if drag_track is not None:
                # ----------------------------------------------------------
                # Straight-track endpoint drag
                # ----------------------------------------------------------
                if self._active_endpoint_drag is not None:
                    if self._show_snap:
                        candidate = self._find_nearest_canvas_endpoint(
                            world_x,
                            world_y,
                            ignore_track=drag_track,
                        )
                        self._endpoint_snap_candidate = candidate

                        if candidate is not None and candidate.is_valid:
                            move_x = candidate.x
                            move_y = candidate.y
                            self._set_endpoint_snap_status_message()
                        elif candidate is not None:
                            move_x = world_x
                            move_y = world_y
                            self._set_endpoint_snap_status_message()
                        else:
                            self._clear_endpoint_snap_candidate()
                            move_x = world_x
                            move_y = world_y
                    else:
                        self._clear_endpoint_snap_candidate()
                        move_x = world_x
                        move_y = world_y

                    self._clear_track_snap_preview()
                    self._move_track_endpoint(
                        drag_track,
                        self._active_endpoint_drag,
                        move_x,
                        move_y,
                    )

                # ----------------------------------------------------------
                # Straight-track body drag
                # ----------------------------------------------------------
                elif (
                    self._drag_start_world_x is not None
                    and self._drag_start_world_y is not None
                ):
                    dx = world_x - self._drag_start_world_x
                    dy = world_y - self._drag_start_world_y

                    self._move_track_body(drag_track, dx, dy)

                    self._drag_start_world_x = world_x
                    self._drag_start_world_y = world_y

                    if self._show_snap:
                        body_drag_result = self._find_body_drag_snap_candidate(
                            drag_track
                        )
                        if body_drag_result is not None:
                            endpoint_index, candidate = body_drag_result
                            self._body_drag_snap_endpoint_index = endpoint_index
                            self._endpoint_snap_candidate = candidate
                            self._set_endpoint_snap_status_message()
                        else:
                            self._body_drag_snap_endpoint_index = None
                            self._clear_endpoint_snap_candidate()
                    else:
                        self._body_drag_snap_endpoint_index = None
                        self._clear_endpoint_snap_candidate()

                self.redraw()
            return

        # ------------------------------------------------------------------
        # Active turnout drag
        # Handles either:
        # - turnout endpoint drag
        # - whole-turnout body drag
        # ------------------------------------------------------------------
        if self._active_turnout_drag_id is not None:
            drag_turnout = self._get_active_drag_turnout()
            if drag_turnout is not None:
                # ----------------------------------------------------------
                # Turnout endpoint drag
                # ----------------------------------------------------------
                if self._active_turnout_endpoint_drag is not None:
                    if self._show_snap:
                        candidate = self._find_nearest_canvas_endpoint(
                            world_x,
                            world_y,
                            ignore_turnout=drag_turnout,
                            ignore_turnout_endpoint_name=self._active_turnout_endpoint_drag,
                        )
                        self._endpoint_snap_candidate = candidate

                        if candidate is not None and candidate.is_valid:
                            move_x = candidate.x
                            move_y = candidate.y
                            self._set_endpoint_snap_status_message()
                        elif candidate is not None:
                            move_x = world_x
                            move_y = world_y
                            self._set_endpoint_snap_status_message()
                        else:
                            self._clear_endpoint_snap_candidate()
                            move_x = world_x
                            move_y = world_y
                    else:
                        self._clear_endpoint_snap_candidate()
                        move_x = world_x
                        move_y = world_y

                    self._move_turnout_endpoint(
                        drag_turnout,
                        self._active_turnout_endpoint_drag,
                        move_x,
                        move_y,
                    )

                # ----------------------------------------------------------
                # Turnout body drag
                # ----------------------------------------------------------
                elif (
                    self._drag_start_world_x is not None
                    and self._drag_start_world_y is not None
                ):
                    dx = world_x - self._drag_start_world_x
                    dy = world_y - self._drag_start_world_y

                    self._move_turnout_body(drag_turnout, dx, dy)

                    self._drag_start_world_x = world_x
                    self._drag_start_world_y = world_y

                    if self._show_snap:
                        body_drag_result = self._find_turnout_body_drag_snap_candidate(
                            drag_turnout
                        )
                        if body_drag_result is not None:
                            endpoint_name, candidate = body_drag_result
                            self._turnout_body_drag_snap_endpoint_name = endpoint_name
                            self._endpoint_snap_candidate = candidate
                            self._set_endpoint_snap_status_message()
                        else:
                            self._turnout_body_drag_snap_endpoint_name = None
                            self._clear_endpoint_snap_candidate()
                    else:
                        self._turnout_body_drag_snap_endpoint_name = None
                        self._clear_endpoint_snap_candidate()

                self.redraw()
            return

        # ------------------------------------------------------------------
        # Track creation preview
        # This is the temporary drag preview while creating a new track.
        # ------------------------------------------------------------------
        if self._creating_track and self._temp_track is not None:
            if self._show_snap:
                candidate = self._find_nearest_canvas_endpoint(
                    world_x,
                    world_y,
                )

                self._endpoint_snap_candidate = candidate

                if candidate is not None and candidate.is_valid:
                    snapped_x = candidate.x
                    snapped_y = candidate.y
                    self._set_endpoint_snap_status_message()
                elif candidate is not None:
                    snapped_x = world_x
                    snapped_y = world_y
                    self._set_endpoint_snap_status_message()
                else:
                    snapped_x, snapped_y = self._update_track_snap_preview(
                        world_x,
                        world_y,
                    )
            else:
                self._endpoint_snap_candidate = None
                snapped_x = world_x
                snapped_y = world_y

            self._temp_track.set_endpoint_2(snapped_x, snapped_y)
            self.redraw()

    def _on_canvas_button_press(self, event: tk.Event) -> None:
        state = event.state
        if not isinstance(state, int):
            return

        world_x = self.canvas.canvasx(event.x)
        world_y = self.canvas.canvasy(event.y)

        # ------------------------------------------------------------------
        # Modifier state
        # ------------------------------------------------------------------
        ctrl_pressed = bool(state & 0x0004)

        # ------------------------------------------------------------------
        # Ctrl + click = begin marquee selection
        # This takes priority over normal object interaction.
        # ------------------------------------------------------------------

        if ctrl_pressed:
            # --------------------------------------------------------------
            # Ctrl + click toggle selection (track / turnout)
            # --------------------------------------------------------------
            clicked_track = self._find_track_at_point(world_x, world_y)
            if clicked_track is not None:
                if clicked_track.id in self._selected_track_ids:
                    self._selected_track_ids.remove(clicked_track.id)
                    self._set_status_message("Track removed from selection.")
                else:
                    self._selected_track_ids.add(clicked_track.id)
                    self._set_status_message("Track added to selection.")

                self._selected_track_id = None
                self._selected_turnout_id = None
                self.redraw()
                return

            clicked_turnout = self._find_turnout_at_point(world_x, world_y)
            if clicked_turnout is not None:
                if clicked_turnout.id in self._selected_turnout_ids:
                    self._selected_turnout_ids.remove(clicked_turnout.id)
                    self._set_status_message("Turnout removed from selection.")
                else:
                    self._selected_turnout_ids.add(clicked_turnout.id)
                    self._set_status_message("Turnout added to selection.")

                self._selected_track_id = None
                self._selected_turnout_id = None
                self.redraw()
                return

            # --------------------------------------------------------------
            # Ctrl + drag fallback → marquee selection
            # (only when clicking empty canvas)
            # --------------------------------------------------------------
            self._pending_trackwork_add = False
            self._active_track_drag_id = None
            self._active_turnout_drag_id = None
            self._active_endpoint_drag = None
            self._active_turnout_endpoint_drag = None
            self._drag_start_world_x = None
            self._drag_start_world_y = None
            self._group_dragging = False
            self._clear_endpoint_snap_candidate()

            self._marquee_selecting = True
            self._marquee_start_world_x = world_x
            self._marquee_start_world_y = world_y
            self._marquee_current_world_x = world_x
            self._marquee_current_world_y = world_y
            self.redraw()
            self._set_status_message("Marquee selecting...")
            return

        # ------------------------------------------------------------------
        # Armed Add mode
        # Toolbar Add button arms placement; next canvas click uses the
        # currently selected Trackwork element.
        # ------------------------------------------------------------------
        if self._pending_trackwork_add:
            self._pending_trackwork_add = False
            self._clear_group_selection()
            self._selected_track_id = None
            self._selected_turnout_id = None
            self._active_track_drag_id = None
            self._active_turnout_drag_id = None
            self._active_endpoint_drag = None
            self._active_turnout_endpoint_drag = None
            self._drag_start_world_x = None
            self._drag_start_world_y = None

            if self._current_trackwork_element == "Turnout":
                turnout = TurnoutElement.create(world_x, world_y)
                self._turnouts.append(turnout)
                self.redraw()
                self._update_canvas_cursor_for_mode()
                self._set_status_message("Turnout placed.")
                return

            self._creating_track = True
            self._temp_track = StraightTrackElement.create(
                world_x,
                world_y,
                world_x,
                world_y,
            )
            self._clear_track_snap_preview()
            self._set_status_message("Creating track... drag to set endpoint")
            self.redraw()
            return

        # ------------------------------------------------------------------
        # Group-selection interaction
        # If a multi-selection exists and the user clicks on any selected
        # track/turnout body, begin dragging the whole selected group.
        # Ctrl+click toggle selection is handled earlier.
        # ------------------------------------------------------------------
        if self._has_group_selection():
            if self._is_point_on_group_selected_track_body(
                world_x, world_y
            ) or self._is_point_on_group_selected_turnout(world_x, world_y):
                self._group_dragging = True
                self._drag_start_world_x = world_x
                self._drag_start_world_y = world_y
                self._active_track_drag_id = None
                self._active_turnout_drag_id = None
                self._active_endpoint_drag = None
                self._active_turnout_endpoint_drag = None
                self._clear_endpoint_snap_candidate()
                self._set_status_message("Dragging selected group.")
                return

        # ------------------------------------------------------------------
        # Single-selection endpoint interaction
        # Endpoint drag has priority over body drag when a selected object
        # endpoint is clicked.
        # ------------------------------------------------------------------
        clicked_endpoint = self._find_selected_track_endpoint_at_point(world_x, world_y)

        if clicked_endpoint is not None:
            self._clear_group_selection()
            self._active_track_drag_id = self._selected_track_id
            self._active_turnout_drag_id = None
            self._active_endpoint_drag = clicked_endpoint
            self._active_turnout_endpoint_drag = None
            self._drag_start_world_x = world_x
            self._drag_start_world_y = world_y
            self._body_drag_snap_endpoint_index = None
            self._clear_endpoint_snap_candidate()

            track = self._get_selected_track()
            if track is not None and self._endpoint_is_coincident(
                track, clicked_endpoint
            ):
                self._set_status_message("Endpoint disconnected.")
            else:
                self._set_status_message(f"Dragging endpoint {clicked_endpoint}.")

            return

        clicked_turnout_endpoint = self._find_selected_turnout_endpoint_at_point(
            world_x,
            world_y,
        )
        if clicked_turnout_endpoint is not None:
            self._clear_group_selection()
            self._active_turnout_drag_id = self._selected_turnout_id
            self._active_track_drag_id = None
            self._active_turnout_endpoint_drag = clicked_turnout_endpoint
            self._active_endpoint_drag = None
            self._drag_start_world_x = world_x
            self._drag_start_world_y = world_y
            self._body_drag_snap_endpoint_index = None
            self._turnout_body_drag_snap_endpoint_name = None
            self._clear_endpoint_snap_candidate()
            self._set_status_message(
                f"Turnout endpoint selected: {clicked_turnout_endpoint}."
            )
            return

        # ------------------------------------------------------------------
        # Single-selection body drag
        # ------------------------------------------------------------------
        if self._is_point_on_selected_track_body(world_x, world_y):
            self._clear_group_selection()
            self._active_track_drag_id = self._selected_track_id
            self._active_turnout_drag_id = None
            self._active_endpoint_drag = None
            self._active_turnout_endpoint_drag = None
            self._drag_start_world_x = world_x
            self._drag_start_world_y = world_y
            self._body_drag_snap_endpoint_index = None
            self._clear_endpoint_snap_candidate()
            self._set_status_message("Dragging track.")
            return

        # ------------------------------------------------------------------
        # Hit test committed objects for single selection / turnout body drag
        # ------------------------------------------------------------------
        clicked_track = self._find_track_at_point(world_x, world_y)
        if clicked_track is not None:
            self._clear_group_selection()
            self._selected_track_id = clicked_track.id
            self._selected_turnout_id = None
            self.redraw()
            self._set_status_message("Track selected.")
            return

        clicked_turnout = self._find_turnout_at_point(world_x, world_y)
        if clicked_turnout is not None:
            self._clear_group_selection()
            if self._selected_turnout_id == clicked_turnout.id:
                self._active_turnout_drag_id = clicked_turnout.id
                self._active_track_drag_id = None
                self._active_endpoint_drag = None
                self._active_turnout_endpoint_drag = None
                self._drag_start_world_x = world_x
                self._drag_start_world_y = world_y
                self._turnout_body_drag_snap_endpoint_name = None
                self._clear_endpoint_snap_candidate()
                self._set_status_message("Dragging turnout.")
                return

            self._selected_turnout_id = clicked_turnout.id
            self._selected_track_id = None
            self.redraw()
            self._set_status_message("Turnout selected.")
            return

        # ------------------------------------------------------------------
        # Shift + click placement shortcut
        # This preserves the existing quick-add path alongside toolbar Add.
        # ------------------------------------------------------------------
        if state & 0x0001:  # Shift
            self._clear_group_selection()
            self._selected_track_id = None
            self._selected_turnout_id = None
            self._active_track_drag_id = None
            self._active_turnout_drag_id = None
            self._active_endpoint_drag = None
            self._active_turnout_endpoint_drag = None
            self._drag_start_world_x = None
            self._drag_start_world_y = None

            if self._current_trackwork_element == "Turnout":
                turnout = TurnoutElement.create(world_x, world_y)
                self._turnouts.append(turnout)
                self.redraw()
                self._set_status_message("Turnout placed.")
                return

            self._creating_track = True
            self._temp_track = StraightTrackElement.create(
                world_x,
                world_y,
                world_x,
                world_y,
            )
            self._clear_track_snap_preview()
            self._set_status_message("Creating track... drag to set endpoint")
            self.redraw()
            return

        # ------------------------------------------------------------------
        # Plain click on empty canvas = clear selection / active drag state
        # ------------------------------------------------------------------
        selection_was_cleared = (
            self._has_group_selection()
            or self._selected_track_id is not None
            or self._selected_turnout_id is not None
        )

        self._clear_group_selection()
        self._selected_track_id = None
        self._selected_turnout_id = None
        self._active_track_drag_id = None
        self._active_turnout_drag_id = None
        self._active_endpoint_drag = None
        self._active_turnout_endpoint_drag = None
        self._group_dragging = False
        self._drag_start_world_x = None
        self._drag_start_world_y = None

        if selection_was_cleared:
            self.redraw()
            self._set_status_message("Selection cleared.")

        # ------------------------------------------------------------------
        # Alt + click guide interaction
        # Only applies when nothing else above handled the click.
        # ------------------------------------------------------------------
        if not self._show_rulers:
            return

        if not (state & 0x0008):  # Alt
            return

        vertical_index = self.guides.find_nearest_vertical(
            world_x,
            self._guide_hit_tolerance,
        )
        if vertical_index is not None:
            self.start_vertical_guide_move(vertical_index, world_x)
            return

        horizontal_index = self.guides.find_nearest_horizontal(
            world_y,
            self._guide_hit_tolerance,
        )
        if horizontal_index is not None:
            self.start_horizontal_guide_move(horizontal_index, world_y)
            return

    def _on_canvas_leave_status(self, _event: tk.Event) -> None:
        self._last_mouse_canvas_x = None
        self._last_mouse_canvas_y = None

        if self.on_mouse_move is None:
            return

        self.on_mouse_move(None, None)

    def _on_alt_press(self, _event: tk.Event) -> None:
        self._alt_pressed = True
        self._update_guide_hover_cursor()

    def _on_alt_release(self, _event: tk.Event) -> None:
        self._alt_pressed = False
        self._update_guide_hover_cursor()

    def _on_canvas_leave_hover(self, _event: tk.Event) -> None:
        if self._active_guide_drag is None:
            self._reset_guide_cursor()

    def _on_canvas_enter(self, _event: tk.Event) -> None:
        self.canvas.focus_set()  # <-- key fix
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel_vertical)

    def _on_canvas_leave(self, _event: tk.Event) -> None:
        self.canvas.unbind_all("<MouseWheel>")
        if self._active_guide_drag is None:
            self._reset_guide_cursor()

    def _on_mousewheel_vertical(self, event: tk.Event) -> None:
        if event.delta == 0:
            return

        direction = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(direction * self.SCROLL_UNITS_PER_TICK, "units")
        self._redraw_rulers()
        self._notify_mouse_position()

    def _on_mousewheel_linux_up(self, _event: tk.Event) -> None:
        self.canvas.yview_scroll(-self.SCROLL_UNITS_PER_TICK, "units")
        self._redraw_rulers()
        self._notify_mouse_position()

    def _on_mousewheel_linux_down(self, _event: tk.Event) -> None:
        self.canvas.yview_scroll(self.SCROLL_UNITS_PER_TICK, "units")
        self._redraw_rulers()
        self._notify_mouse_position()
