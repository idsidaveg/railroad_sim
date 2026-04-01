import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from railroad_sim.domain.consist import Consist
from railroad_sim.domain.enums import TrackType
from railroad_sim.domain.equipment.boxcar import BoxCar
from railroad_sim.domain.rolling_stock import RollingStock
from railroad_sim.domain.track import Track


class WorkbenchApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Railroad Simulator Workbench")
        self.root.geometry("1400x850")

        self._canvas_item_to_object: dict[int, object] = {}
        self.demo_consist: Consist | None = None
        self._selected_item_ids: set[int] = set()
        self.demo_track: Track | None = None
        self._object_to_primary_canvas_item: dict[int, int] = {}
        self._track_item_id: int | None = None
        self._track_label_item_id: int | None = None
        self._car_item_ids: list[int] = []
        self._consist_marker_item_id: int | None = None

        self._zoom_scale: float = 1.0
        self._min_zoom_scale: float = 0.50
        self._max_zoom_scale: float = 3.00
        self._zoom_step_in: float = 1.10
        self._zoom_step_out: float = 1 / 1.10

        self._theme_mode: str = "light"
        self._theme_var = tk.StringVar(value=self._theme_mode)
        self.hover_text = tk.StringVar(value="Hover: None")

        self._build_layout()
        self._build_main_menu()
        self._configure_initial_canvas_region()
        self._draw_demo_scene()
        if self._theme_mode == "light":
            self._set_light_mode()
        else:
            self._set_dark_mode()
        self.root.after(50, self._set_initial_top_pane_split)

    def _configure_initial_canvas_region(self) -> None:
        """
        Configure the initial logical workspace larger than the visible viewport.
        This gives the scrollbars meaningful range even before zoom is added
        """
        self.canvas.configure(scrollregion=(0, 0, 2400, 1800))
        self.canvas.xview_moveto(0.0)
        self.canvas.yview_moveto(0.0)

    def _set_initial_top_pane_split(self) -> None:
        """
        Set the initial top-pane split after the window has been laid out.
        Leave a narrower inspector on the right to give most width to the canvas
        """
        self.root.update_idletasks()

        total_width = self.top_pane.winfo_width()
        inspector_target_width = 320
        if total_width <= inspector_target_width + 200:
            return

        self.top_pane.sashpos(0, total_width - inspector_target_width)

    def _build_layout(self) -> None:
        main_pane = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        self.top_pane = ttk.PanedWindow(main_pane, orient=tk.HORIZONTAL)
        bottom_frame = ttk.Frame(main_pane, height=150)

        main_pane.add(self.top_pane, weight=4)
        main_pane.add(bottom_frame, weight=1)

        # scrollbar setup
        canvas_frame = ttk.Frame(self.top_pane)
        self.top_pane.add(canvas_frame, weight=7)

        canvas_bg = "snow" if self._theme_mode == "light" else "black"
        self.canvas = tk.Canvas(
            canvas_frame,
            bg=canvas_bg,
        )

        self.h_scrollbar = ttk.Scrollbar(
            canvas_frame,
            orient=tk.HORIZONTAL,
            command=self.canvas.xview,
        )
        self.v_scrollbar = ttk.Scrollbar(
            canvas_frame,
            orient=tk.VERTICAL,
            command=self.canvas.yview,
        )

        self.canvas.configure(
            xscrollcommand=self.h_scrollbar.set,
            yscrollcommand=self.v_scrollbar.set,
        )

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.h_scrollbar.grid(row=1, column=0, sticky="ew")

        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)
        # end of scrollbar

        inspector_frame = ttk.Frame(self.top_pane, width=220)
        self.top_pane.add(inspector_frame, weight=1)

        self._build_inspector(inspector_frame)
        self._build_log(bottom_frame)

        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.canvas.bind("<MouseWheel>", self._on_canvas_mousewheel)
        self.canvas.bind("<Button-4>", self._on_canvas_mousewheel_linux)
        self.canvas.bind("<Button-5>", self._on_canvas_mousewheel_linux)

    def _build_main_menu(self) -> None:
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Exit", command=self.root.destroy)
        menubar.add_cascade(label="File", menu=file_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_radiobutton(
            label="Light Mode",
            variable=self._theme_var,
            value="light",
            command=self._set_light_mode,
        )
        view_menu.add_radiobutton(
            label="Dark Mode",
            variable=self._theme_var,
            value="dark",
            command=self._set_dark_mode,
        )
        menubar.add_cascade(label="View", menu=view_menu)

        self.root.config(menu=menubar)

    def _set_light_mode(self) -> None:
        self._theme_mode = "light"
        self._theme_var.set("light")
        self.canvas.configure(bg="snow")
        if self._track_item_id is not None:
            self.canvas.itemconfigure(self._track_item_id, fill="black")
        if self._track_label_item_id is not None:
            self.canvas.itemconfigure(self._track_label_item_id, fill="black")
        for item_id in self._car_item_ids:
            self.canvas.itemconfigure(item_id, outline="black")
        if self._consist_marker_item_id is not None:
            self.canvas.itemconfigure(self._consist_marker_item_id, outline="gray40")

    def _set_dark_mode(self) -> None:
        self._theme_mode = "dark"
        self._theme_var.set("dark")
        self.canvas.configure(bg="black")
        if self._track_item_id is not None:
            self.canvas.itemconfigure(self._track_item_id, fill="white")
        if self._track_label_item_id is not None:
            self.canvas.itemconfigure(self._track_label_item_id, fill="white")
        for item_id in self._car_item_ids:
            self.canvas.itemconfigure(item_id, outline="white")
        if self._consist_marker_item_id is not None:
            self.canvas.itemconfigure(self._consist_marker_item_id, outline="gray60")

    def _on_canvas_click(self, event) -> None:
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        item_ids = self.canvas.find_overlapping(
            canvas_x,
            canvas_y,
            canvas_x,
            canvas_y,
        )

        ctrl_pressed = (event.state & 0x4) != 0

        if not item_ids:
            if not ctrl_pressed:
                self._clear_all_selection_highlights()
                self._update_inspector("Unknown selection")
            return

        selected_item_id = None

        for item_id in reversed(item_ids):
            tags = self.canvas.gettags(item_id)
            if (
                "car" in tags
                or "consist" in tags
                or "coupler" in tags
                or "track" in tags
            ):
                selected_item_id = item_id
                break

        if selected_item_id is None:
            if not ctrl_pressed:
                self._clear_all_selection_highlights()
                self._update_inspector("Unknown selection")
            return

        selected_obj = self._canvas_item_to_object.get(selected_item_id)
        highlight_item_id = selected_item_id
        if selected_obj is not None:
            primary_item_id = self._object_to_primary_canvas_item.get(id(selected_obj))
            if primary_item_id is not None:
                highlight_item_id = primary_item_id

        if not ctrl_pressed:
            self._clear_all_selection_highlights()
            self._apply_highlight_to_item(highlight_item_id)
            self._selected_item_ids.add(highlight_item_id)
        else:
            self._toggle_item_selection(highlight_item_id)

        self._update_inspector_for_selection()

    def _on_mouse_move(self, event) -> None:
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        item_ids = self.canvas.find_overlapping(
            canvas_x,
            canvas_y,
            canvas_x,
            canvas_y,
        )

        if not item_ids:
            self.canvas.config(cursor="")
            return

        hovered_obj = None
        is_clickable = False

        for item_id in reversed(item_ids):
            tags = self.canvas.gettags(item_id)
            if (
                "car" in tags
                or "consist" in tags
                or "coupler" in tags
                or "track" in tags
            ):
                is_clickable = True
                hovered_obj = self._canvas_item_to_object.get(item_id)
                break

        if is_clickable:
            self.canvas.config(cursor="hand2")
        else:
            self.canvas.config(cursor="")

        self._update_hover_status(hovered_obj)

    def _on_canvas_mousewheel(self, event) -> None:
        if event.delta > 0:
            scale_factor = self._zoom_step_in
        elif event.delta < 0:
            scale_factor = self._zoom_step_out
        else:
            return

        proposed_scale = self._zoom_scale * scale_factor
        if proposed_scale < self._min_zoom_scale:
            scale_factor = self._min_zoom_scale / self._zoom_scale
            proposed_scale = self._min_zoom_scale
        elif proposed_scale > self._max_zoom_scale:
            scale_factor = self._max_zoom_scale / self._zoom_scale
            proposed_scale = self._max_zoom_scale

        if proposed_scale == self._zoom_scale:
            return

        anchor_x, anchor_y = self._get_zoom_anchor(event)

        self.canvas.scale("all", anchor_x, anchor_y, scale_factor, scale_factor)
        self._zoom_scale = proposed_scale

        self._refresh_canvas_scrollregion()
        self._update_zoom_dependent_visibility()

    def _on_canvas_mousewheel_linux(self, event) -> None:
        if event.num == 4:
            scale_factor = self._zoom_step_in
        elif event.num == 5:
            scale_factor = self._zoom_step_out
        else:
            return

        proposed_scale = self._zoom_scale * scale_factor
        if proposed_scale < self._min_zoom_scale:
            scale_factor = self._min_zoom_scale / self._zoom_scale
            proposed_scale = self._min_zoom_scale
        elif proposed_scale > self._max_zoom_scale:
            scale_factor = self._max_zoom_scale / self._zoom_scale
            proposed_scale = self._max_zoom_scale

        if proposed_scale == self._zoom_scale:
            return

        anchor_x, anchor_y = self._get_zoom_anchor(event)

        self.canvas.scale("all", anchor_x, anchor_y, scale_factor, scale_factor)
        self._zoom_scale = proposed_scale

        self._refresh_canvas_scrollregion()
        self._update_zoom_dependent_visibility()

    def _get_zoom_anchor(self, event) -> tuple[float, float]:
        """
        Zoom around the selected object when one exists.
        Otherwise zoom around the mouse position.
        """
        if self._selected_item_ids:
            item_id = next(iter(self._selected_item_ids))
            bbox = self.canvas.bbox(item_id)
            if bbox is not None:
                x1, y1, x2, y2 = bbox
                return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

        return (
            self.canvas.canvasx(event.x),
            self.canvas.canvasy(event.y),
        )

    def _update_zoom_dependent_visibility(self) -> None:
        if self._track_label_item_id is None:
            return

        if self._zoom_scale < 0.75:
            self.canvas.itemconfigure(self._track_label_item_id, state="hidden")
        else:
            self.canvas.itemconfigure(self._track_label_item_id, state="normal")

    def _refresh_canvas_scrollregion(self) -> None:
        bbox = self.canvas.bbox("all")
        if bbox is None:
            return

        x1, y1, x2, y2 = bbox
        padding = 200
        self.canvas.configure(
            scrollregion=(x1 - padding, y1 - padding, x2 + padding, y2 + padding)
        )

    def _clear_all_selection_highlights(self) -> None:
        for item_id in list(self._selected_item_ids):
            self._remove_highlight_from_item(item_id)
        self._selected_item_ids.clear()

    def _remove_highlight_from_item(self, item_id: int) -> None:
        tags = self.canvas.gettags(item_id)

        if self._theme_mode == "light":
            car_outline = "black"
            track_color = "black"
            consist_outline = "gray40"
        else:
            car_outline = "white"
            track_color = "white"
            consist_outline = "gray60"

        if "car" in tags:
            self.canvas.itemconfigure(item_id, outline=car_outline, width=2)
        elif "coupler" in tags:
            self.canvas.itemconfigure(item_id, fill="yellow", width=4)
        elif "consist" in tags:
            self.canvas.itemconfigure(item_id, outline=consist_outline, width=1)
        elif "track" in tags:
            self.canvas.itemconfigure(item_id, fill=track_color, width=4)

    def _apply_highlight_to_item(self, item_id: int) -> None:
        tags = self.canvas.gettags(item_id)

        if "car" in tags:
            self.canvas.itemconfigure(item_id, outline="yellow", width=3)
        elif "coupler" in tags:
            self.canvas.itemconfigure(item_id, fill="orange", width=5)
        elif "consist" in tags:
            self.canvas.itemconfigure(item_id, outline="yellow", width=2)
        elif "track" in tags:
            self.canvas.itemconfigure(item_id, fill="cyan", width=5)

    def _format_selected_object_details(
        self, selected_obj: object, index: int | None = None
    ) -> list[str]:
        prefix = f"[{index}] " if index is not None else ""

        if isinstance(selected_obj, Consist):
            return [
                f"{prefix}Type: Consist",
                f"    Cars: {len(selected_obj.ordered_equipment())}",
                f"    Length: {selected_obj.operational_length_ft:.1f} ft",
                f"    Weight: {selected_obj.gross_weight_lb:.0f} lb",
            ]

        if isinstance(selected_obj, RollingStock):
            return [
                f"{prefix}Type: Car",
                f"    Equipment ID: {selected_obj.equipment_id}",
                f"    Class: {selected_obj.equipment_class}",
                f"    Length: {selected_obj.operational_length_ft:.1f} ft",
                f"    Weight: {selected_obj.gross_weight_lb:.0f} lb",
            ]

        if isinstance(selected_obj, Track):
            return [
                f"{prefix}Type: Track",
                f"    Name: {selected_obj.name}",
                f"    Track Type: {selected_obj.track_type.value}",
                f"    Length: {selected_obj.length_ft:.1f} ft",
            ]

        if (
            isinstance(selected_obj, tuple)
            and selected_obj
            and selected_obj[0] == "coupler"
        ):
            return [
                f"{prefix}Type: Coupler",
                "    Connected: Yes",
            ]

        return [f"{prefix}Unknown selection"]

    def _format_multi_selection_details(self) -> str:
        lines = [
            f"Selected items: {len(self._selected_item_ids)}",
            "Mode: Multi-select",
            "",
        ]

        for index, item_id in enumerate(sorted(self._selected_item_ids), start=1):
            selected_obj = self._canvas_item_to_object.get(item_id)
            lines.extend(
                self._format_selected_object_details(selected_obj, index=index)
            )
            lines.append("")

        return "\n".join(lines).rstrip()

    def _update_inspector_for_selection(self) -> None:
        if not self._selected_item_ids:
            self._update_inspector("Unknown selection")
            return

        if len(self._selected_item_ids) > 1:
            self._update_inspector(self._format_multi_selection_details())
            return

        item_id = next(iter(self._selected_item_ids))
        selected_obj = self._canvas_item_to_object.get(item_id)

        self._update_inspector(
            "\n".join(self._format_selected_object_details(selected_obj))
        )

    def _toggle_item_selection(self, item_id: int) -> None:
        if item_id in self._selected_item_ids:
            self._remove_highlight_from_item(item_id)
            self._selected_item_ids.remove(item_id)
        else:
            self._apply_highlight_to_item(item_id)
            self._selected_item_ids.add(item_id)

    def _update_inspector(self, text: str) -> None:
        self.inspector_text.delete("1.0", tk.END)
        self.inspector_text.insert(tk.END, text)

    def _build_inspector(self, parent: ttk.Frame) -> None:
        label = ttk.Label(parent, text="Inspector", font=("Arial", 12, "bold"))
        label.pack(anchor="nw", padx=10, pady=10)

        inspector_text_frame = ttk.Frame(parent)
        inspector_text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.inspector_text = tk.Text(
            inspector_text_frame,
            height=20,
            wrap="word",
            font=("Arial", 10),
        )
        self.inspector_scrollbar = ttk.Scrollbar(
            inspector_text_frame,
            orient=tk.VERTICAL,
            command=self.inspector_text.yview,
        )

        self.inspector_text.configure(yscrollcommand=self.inspector_scrollbar.set)

        self.inspector_text.grid(row=0, column=0, sticky="nsew")
        self.inspector_scrollbar.grid(row=0, column=1, sticky="ns")

        inspector_text_frame.rowconfigure(0, weight=1)
        inspector_text_frame.columnconfigure(0, weight=1)

    def _build_log(self, parent: ttk.Frame) -> None:
        hover_label = ttk.Label(
            parent,
            textvariable=self.hover_text,
            font=("Arial", 10),
        )
        hover_label.pack(anchor="nw", padx=19, pady=(5, 0))

        label = ttk.Label(parent, text="Event Log", font=("Arial", 12, "bold"))
        label.pack(anchor="nw", padx=10, pady=5)

        self.log_text = tk.Text(parent, height=8)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    def _update_hover_status(self, obj: object | None) -> None:
        if isinstance(obj, Consist):
            self.hover_text.set(
                f"Hover: Consist | Cars: {len(obj.ordered_equipment())} | "
                f"Length: {obj.operational_length_ft:.1f} ft"
            )
        elif isinstance(obj, RollingStock):
            self.hover_text.set(
                f"Hover: Car | {obj.equipment_id} | Class: {obj.equipment_class}"
            )
        elif isinstance(obj, tuple) and obj and obj[0] == "coupler":
            self.hover_text.set("Hover: Coupler | Connected")
        elif isinstance(obj, Track):
            self.hover_text.set(
                f"Hover: Track | {obj.name} | Length: {obj.length_ft:.1f} ft"
            )
        else:
            self.hover_text.set("Hover: None")

    def _draw_demo_scene(self) -> None:
        # self.canvas.create_line(80, 120, 500, 120, fill="white", width=4)
        self.demo_track = Track(
            name="Main Track", track_type=TrackType.MAINLINE, length_ft=500.0
        )

        track_item = self.canvas.create_line(
            200,
            180,
            620,
            180,
            fill="white",
            width=4,
            tags=("track",),
        )
        self._canvas_item_to_object[track_item] = self.demo_track
        self._object_to_primary_canvas_item[id(self.demo_track)] = track_item
        self._track_item_id = track_item

        track_label_item = self.canvas.create_text(
            200,
            155,
            text="Main Track",
            anchor="w",
            fill="white",
            font=("Arial", 10, "bold"),
            tags=("track",),
        )
        self._canvas_item_to_object[track_label_item] = self.demo_track
        self._track_label_item_id = track_label_item

        car1 = BoxCar(reporting_mark="DBG", road_number="0001")
        car2 = BoxCar(reporting_mark="DBG", road_number="0002")
        car1.rear_coupler.connect(car2.front_coupler)

        self.demo_consist = Consist(anchor=car1)

        car1_item = self.canvas.create_rectangle(
            300,
            160,
            360,
            200,
            fill="steelblue",
            outline="white",
            width=2,
            tags=("car",),
        )

        car2_item = self.canvas.create_rectangle(
            364,
            160,
            424,
            200,
            fill="steelblue",
            outline="white",
            width=2,
            tags=("car",),
        )

        self._car_item_ids = [car1_item, car2_item]

        coupler_item = self.canvas.create_line(
            360,
            180,
            364,
            180,
            fill="yellow",
            width=4,
            tags=("coupler",),
        )

        coupler_hitbox_item = self.canvas.create_rectangle(
            356,
            172,
            368,
            188,
            outline="",
            fill="",
            tags=("coupler",),
        )

        consist_marker_item = self.canvas.create_rectangle(
            296,
            156,
            428,
            204,
            outline="gray60",
            width=1,
            dash=(4, 2),
            tags=("consist",),
        )
        self._consist_marker_item_id = consist_marker_item

        self._canvas_item_to_object[car1_item] = car1
        self._canvas_item_to_object[car2_item] = car2

        coupler_obj = ("coupler", car1, car2)
        self._canvas_item_to_object[coupler_item] = coupler_obj
        self._canvas_item_to_object[coupler_hitbox_item] = coupler_obj
        self._object_to_primary_canvas_item[id(coupler_obj)] = coupler_item

        self._canvas_item_to_object[consist_marker_item] = self.demo_consist

        self._object_to_primary_canvas_item[id(car1)] = car1_item
        self._object_to_primary_canvas_item[id(car2)] = car2_item
        self._object_to_primary_canvas_item[id(self.demo_consist)] = consist_marker_item

        self._refresh_canvas_scrollregion()
        self._update_zoom_dependent_visibility()


def main() -> None:
    root = tk.Tk()
    WorkbenchApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
