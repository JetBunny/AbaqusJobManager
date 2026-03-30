"""
Progress monitor widget — plots .sta file data using pyqtgraph.
Auto-refreshes while a job is running.
"""
from __future__ import annotations

from typing import Optional

import pyqtgraph as pg
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.core.models import AbaqusJob
from app.core.sta_parser import StaParser

_POLL_INTERVAL_MS = 2000   # refresh every 2 seconds while running


class ProgressMonitorWidget(QWidget):
    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self._current_job: Optional[AbaqusJob] = None
        self._timer = QTimer(self)
        self._timer.setInterval(_POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._refresh_plot)

        self._build_ui()

    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._label = QLabel("No job selected")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("color: #888; padding: 4px;")
        layout.addWidget(self._label)

        # pyqtgraph plot widget
        pg.setConfigOption("background", "#1e1e1e")
        pg.setConfigOption("foreground", "#cccccc")

        self._plot_widget = pg.PlotWidget()
        self._plot_widget.setLabel("left",   "Total Time",   units="s")
        self._plot_widget.setLabel("bottom", "Increment",    units="")
        self._plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self._plot_widget.addLegend()

        pen = pg.mkPen(color="#2196F3", width=2)
        self._curve = self._plot_widget.plot(
            [], [], pen=pen, symbol="o",
            symbolBrush="#2196F3", symbolSize=5, name="Total Time"
        )

        # Step time secondary curve
        pen2 = pg.mkPen(color="#FF9800", width=1.5, style=Qt.PenStyle.DashLine)
        self._curve_step = self._plot_widget.plot(
            [], [], pen=pen2, name="Step Time"
        )

        layout.addWidget(self._plot_widget)

    # ------------------------------------------------------------------ #

    def set_job(self, job: Optional[AbaqusJob]) -> None:
        self._current_job = job
        self._timer.stop()

        if job is None:
            self._label.setText("No job selected")
            self._clear_plot()
            return

        self._label.setText(f"Progress: {job.display_name}")
        self._refresh_plot()

    def start_monitoring(self) -> None:
        """Call this when a job starts running to begin live polling."""
        if not self._timer.isActive():
            self._timer.start()

    def on_job_finished(self) -> None:
        """Call this when the job process exits."""
        self._timer.stop()
        self._refresh_plot()  # final update

    # ------------------------------------------------------------------ #

    def _refresh_plot(self) -> None:
        if self._current_job is None:
            return

        job = self._current_job
        # sta_file is set at scan time and may be None if the file was created
        # after the last scan.  Always derive the expected path from the job
        # folder so we pick it up as soon as Abaqus writes it.
        sta_path = job.sta_file or (job.folder / f"{job.stem}.sta")
        if not sta_path.exists():
            self._label.setText(
                f"Progress: {job.display_name}  —  No .sta file yet"
            )
            self._clear_plot()
            return

        parser = StaParser(sta_path)
        records = parser.parse()

        if not records:
            self._label.setText(
                f"Progress: {job.display_name}  —  .sta file empty"
            )
            self._clear_plot()
            return

        x = [r.increment for r in records]
        y_total = [r.total_time for r in records]
        y_step  = [r.step_time  for r in records]

        self._curve.setData(x, y_total)
        self._curve_step.setData(x, y_step)

        last = records[-1]
        self._label.setText(
            f"Progress: {job.display_name}  —  "
            f"Step {last.step}, Inc {last.increment}, "
            f"Total Time = {last.total_time:.4g} s"
        )

    def _clear_plot(self) -> None:
        self._curve.setData([], [])
        self._curve_step.setData([], [])
