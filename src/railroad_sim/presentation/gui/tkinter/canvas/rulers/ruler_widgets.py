from __future__ import annotations

import tkinter as tk


class BaseRuler(tk.Canvas):
    """
    Base ruler widget.

    Rulers are fixed UI widgets that reflect the visible portion of the
    scrollable design canvas. They do not scroll themselves; instead they
    redraw based on the canvas viewport position.
    """

    RULER_THICKNESS = 20
    MINOR_TICK_SPACING = 20
    MAJOR_TICK_EVERY = 5
    BACKGROUND_COLOR = "#f4f4f4"
    BORDER_COLOR = "#b8b8b8"
    TICK_COLOR = "#444444"
    LABEL_COLOR = "#222222"
    FONT = ("Arial", 8)

    def __init__(self, parent: tk.Misc, *, design_canvas: tk.Canvas | None) -> None:
        super().__init__(
            parent,
            background=self.BACKGROUND_COLOR,
            highlightthickness=1,
            highlightbackground=self.BORDER_COLOR,
            bd=0,
        )
        self.design_canvas = design_canvas

    def redraw(self) -> None:
        self.delete("all")
        self._draw_background()
        if self.design_canvas is None:
            return

        self._draw_ticks()

    def _draw_background(self) -> None:
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        self.create_rectangle(
            0,
            0,
            width,
            height,
            fill=self.BACKGROUND_COLOR,
            outline="",
        )

    def _draw_ticks(self) -> None:
        raise NotImplementedError

    def _canvas_world_x_from_ruler_event(self, event: tk.Event) -> float:
        if self.design_canvas is None:
            return 0.0
        return self.design_canvas.canvasx(event.x)

    def _canvas_world_y_from_ruler_event(self, event: tk.Event) -> float:
        if self.design_canvas is None:
            return 0.0
        return self.design_canvas.canvasy(event.y)


class HorizontalRuler(BaseRuler):
    """
    Top ruler.

    Shows X coordinates for the visible canvas viewport.
    """

    def __init__(self, parent: tk.Misc, *, design_canvas: tk.Canvas | None) -> None:
        super().__init__(parent, design_canvas=design_canvas)

        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Button-3>", self._on_context_menu)

    def _draw_ticks(self) -> None:
        if self.design_canvas is None:
            return

        canvas = self.design_canvas

        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())

        start_world_x = canvas.canvasx(0)
        end_world_x = canvas.canvasx(width)

        spacing = self.MINOR_TICK_SPACING
        major_every = self.MAJOR_TICK_EVERY

        first_tick = int(start_world_x // spacing) * spacing
        if first_tick > start_world_x:
            first_tick -= spacing

        x = first_tick
        while x <= end_world_x + spacing:
            screen_x = x - start_world_x
            tick_index = int(round(x / spacing))
            is_major = (tick_index % major_every) == 0

            tick_height = height - 2 if is_major else max(6, height // 2)

            self.create_line(
                screen_x,
                height,
                screen_x,
                height - tick_height,
                fill=self.TICK_COLOR,
            )

            if is_major:
                self.create_text(
                    screen_x + 2,
                    2,
                    anchor="nw",
                    text=str(int(x)),
                    fill=self.LABEL_COLOR,
                    font=self.FONT,
                )

            x += spacing

    def _on_press(self, event: tk.Event) -> None:
        if self.design_canvas is None:
            return

        parent = self.master
        if parent is None:
            return

        start_drag = getattr(parent, "start_vertical_guide_drag", None)
        if start_drag is None:
            return

        world_x = self._canvas_world_x_from_ruler_event(event)
        start_drag(world_x)

    def _on_drag(self, _event: tk.Event) -> None:
        # Drag tracking is owned by DesignCanvas once drag starts.
        return

    def _on_release(self, _event: tk.Event) -> None:
        # Release is owned by DesignCanvas once drag starts.
        return

    def _on_context_menu(self, event: tk.Event) -> None:
        parent = self.master
        if parent is None:
            return

        clear_vertical = getattr(parent, "clear_vertical_guides", None)
        clear_all = getattr(parent, "clear_all_guides", None)
        guides = getattr(parent, "guides", None)

        vertical_count = len(guides.vertical_guides) if guides is not None else 0
        horizontal_count = len(guides.horizontal_guides) if guides is not None else 0
        total_count = vertical_count + horizontal_count

        menu = tk.Menu(self, tearoff=0)

        menu.add_command(
            label="Clear Vertical Guides",
            command=clear_vertical if clear_vertical is not None else (lambda: None),
            state=tk.NORMAL
            if clear_vertical is not None and vertical_count > 0
            else tk.DISABLED,
        )

        menu.add_command(
            label="Clear All Guides",
            command=clear_all if clear_all is not None else (lambda: None),
            state=tk.NORMAL
            if clear_all is not None and total_count > 0
            else tk.DISABLED,
        )

        menu.tk_popup(event.x_root, event.y_root)


class VerticalRuler(BaseRuler):
    """
    Left ruler.

    Shows Y coordinates for the visible canvas viewport.
    """

    def __init__(self, parent: tk.Misc, *, design_canvas: tk.Canvas | None) -> None:
        super().__init__(parent, design_canvas=design_canvas)

        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Button-3>", self._on_context_menu)

    def _draw_ticks(self) -> None:
        if self.design_canvas is None:
            return

        canvas = self.design_canvas

        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())

        start_world_y = canvas.canvasy(0)
        end_world_y = canvas.canvasy(height)

        spacing = self.MINOR_TICK_SPACING
        major_every = self.MAJOR_TICK_EVERY

        first_tick = int(start_world_y // spacing) * spacing
        if first_tick > start_world_y:
            first_tick -= spacing

        y = first_tick
        while y <= end_world_y + spacing:
            screen_y = y - start_world_y
            tick_index = int(round(y / spacing))
            is_major = (tick_index % major_every) == 0

            tick_width = width - 2 if is_major else max(6, width // 2)

            self.create_line(
                width,
                screen_y,
                width - tick_width,
                screen_y,
                fill=self.TICK_COLOR,
            )

            if is_major:
                self.create_text(
                    2,
                    screen_y + 2,
                    anchor="nw",
                    text=str(int(y)),
                    fill=self.LABEL_COLOR,
                    font=self.FONT,
                )

            y += spacing

    def _on_press(self, event: tk.Event) -> None:
        if self.design_canvas is None:
            return

        parent = self.master
        if parent is None:
            return

        start_drag = getattr(parent, "start_horizontal_guide_drag", None)
        if start_drag is None:
            return

        world_y = self._canvas_world_y_from_ruler_event(event)
        start_drag(world_y)

    def _on_drag(self, _event: tk.Event) -> None:
        # Drag tracking is owned by DesignCanvas once drag starts.
        return

    def _on_release(self, _event: tk.Event) -> None:
        # Release is owned by DesignCanvas once drag starts.
        return

    def _on_context_menu(self, event: tk.Event) -> None:
        parent = self.master
        if parent is None:
            return

        clear_horizontal = getattr(parent, "clear_horizontal_guides", None)
        clear_all = getattr(parent, "clear_all_guides", None)
        guides = getattr(parent, "guides", None)

        vertical_count = len(guides.vertical_guides) if guides is not None else 0
        horizontal_count = len(guides.horizontal_guides) if guides is not None else 0
        total_count = vertical_count + horizontal_count

        menu = tk.Menu(self, tearoff=0)

        menu.add_command(
            label="Clear Horizontal Guides",
            command=clear_horizontal
            if clear_horizontal is not None
            else (lambda: None),
            state=tk.NORMAL
            if clear_horizontal is not None and horizontal_count > 0
            else tk.DISABLED,
        )

        menu.add_command(
            label="Clear All Guides",
            command=clear_all if clear_all is not None else (lambda: None),
            state=tk.NORMAL
            if clear_all is not None and total_count > 0
            else tk.DISABLED,
        )

        menu.tk_popup(event.x_root, event.y_root)
