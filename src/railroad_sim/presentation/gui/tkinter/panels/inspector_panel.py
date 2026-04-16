from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class InspectorPanel(ttk.Frame):
    """
    Standalone inspector panel shell.

    This first pass is intentionally presentation-only. It provides a sectioned
    structure that can later display and edit different object types without
    coupling the panel to the application shell, canvas, or domain objects.
    """

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, padding=0)

        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_header()
        self._build_body()

    def _build_header(self) -> None:
        header = ttk.Frame(self, padding=(0, 0, 0, 8))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        ttk.Label(
            header,
            text="Inspector",
            font=("Arial", 11, "bold"),
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(
            header,
            text="No Selection",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

    def _build_body(self) -> None:
        body = ttk.Frame(self)
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)

        self._build_general_section(body)
        self._build_object_section(body)
        self._build_status_section(body)

    def _build_general_section(self, parent: ttk.Frame) -> None:
        section = ttk.LabelFrame(parent, text="General", padding=8)
        section.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        section.columnconfigure(1, weight=1)

        ttk.Label(section, text="Type:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Label(section, text="—").grid(row=0, column=1, sticky="w")

        ttk.Label(section, text="Name:").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=(6, 0)
        )
        ttk.Label(section, text="—").grid(row=1, column=1, sticky="w", pady=(6, 0))

        ttk.Label(section, text="ID:").grid(
            row=2, column=0, sticky="w", padx=(0, 8), pady=(6, 0)
        )
        ttk.Label(section, text="—").grid(row=2, column=1, sticky="w", pady=(6, 0))

    def _build_object_section(self, parent: ttk.Frame) -> None:
        section = ttk.LabelFrame(parent, text="Object Details", padding=8)
        section.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        section.columnconfigure(0, weight=1)

        ttk.Label(
            section,
            text=(
                "Object-specific controls and values will appear here.\n"
                "Examples: track geometry, turnout hand, switch parameters, etc."
            ),
            justify="left",
        ).grid(row=0, column=0, sticky="w")

    def _build_status_section(self, parent: ttk.Frame) -> None:
        section = ttk.LabelFrame(parent, text="Status / Diagnostics", padding=8)
        section.grid(row=2, column=0, sticky="nsew")
        section.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)

        text = tk.Text(
            section,
            height=10,
            wrap="word",
            state="normal",
            font=("Arial", 10),
        )
        text.grid(row=0, column=0, sticky="nsew")
        section.rowconfigure(0, weight=1)

        text.insert(
            "1.0",
            (
                "Inspector diagnostics placeholder.\n\n"
                "Later this area can show validation notes, connection details, "
                "runtime feedback, and other read-only information."
            ),
        )
        text.config(state="disabled")
