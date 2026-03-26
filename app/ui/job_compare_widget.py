"""
Job comparison widget — overlays .sta progress curves for multiple jobs.
"""
from __future__ import annotations

from typing import List

import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.core.models import AbaqusJob
from app.core.sta_parser import StaParser

# Distinct colour palette (up to 10 simultaneous jobs)
_PALETTE = [
    "#2196F3",  # blue
    "#FF9800",  # orange
    "#4CAF50",  # green
    "#E91E63",  # pink
    "#9C27B0",  # purple
    "#00BCD4",  # cyan
    "#FF5722",  # deep orange
    "#8BC34A",  # light green
    "#FFC107",  # amber
    "#607D8B",  # blue-grey
]


class JobCompareWidget(QWidget):
    """
    Plots total-time-vs-increment curves for every job in the provided list.
    Typically driven by the browser's multi-selection.
    """

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self._jobs: List[AbaqusJob] = []
        self._build_ui()

    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._label = QLabel(
            "Select multiple jobs (Ctrl+click or Shift+click) to compare"
        )
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("color: #888; padding: 4px;")
        layout.addWidget(self._label)

        pg.setConfigOption("background", "#1e1e1e")
        pg.setConfigOption("foreground", "#cccccc")

        self._plot_widget = pg.PlotWidget()
        self._plot_widget.setLabel("left",   "Total Time", units="s")
        self._plot_widget.setLabel("bottom", "Increment")
        self._plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self._legend = self._plot_widget.addLegend(offset=(10, 10))

        layout.addWidget(self._plot_widget)

    # ------------------------------------------------------------------ #

    def set_jobs(self, jobs: List[AbaqusJob]) -> None:
        self._jobs = jobs
        self._rebuild()

    def refresh(self) -> None:
        """Re-read all .sta files and redraw — call on auto-refresh."""
        self._rebuild()

    # ------------------------------------------------------------------ #

    def _rebuild(self) -> None:
        self._plot_widget.clear()
        # Re-add legend after clear (clear removes it)
        self._legend = self._plot_widget.addLegend(offset=(10, 10))

        jobs_with_sta = [j for j in self._jobs if j.sta_file and j.sta_file.exists()]

        if not self._jobs:
            self._label.setText(
                "Select multiple jobs (Ctrl+click or Shift+click) to compare"
            )
            return

        if not jobs_with_sta:
            self._label.setText(
                f"{len(self._jobs)} job(s) selected — none have a .sta file yet"
            )
            return

        self._label.setText(
            f"Comparing {len(jobs_with_sta)} job(s)"
            + (
                f"  ({len(self._jobs) - len(jobs_with_sta)} have no .sta)"
                if len(jobs_with_sta) < len(self._jobs)
                else ""
            )
        )

        for i, job in enumerate(jobs_with_sta):
            color = _PALETTE[i % len(_PALETTE)]
            records = StaParser(job.sta_file).parse()
            if not records:
                continue

            x = [r.increment  for r in records]
            y = [r.total_time for r in records]

            pen = pg.mkPen(color=color, width=2)
            self._plot_widget.plot(
                x, y,
                pen=pen,
                symbol="o",
                symbolBrush=color,
                symbolSize=5,
                name=job.stem,
            )
