"""
Main application window.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import QSettings, QSize, Qt
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QSplitter,
    QTabWidget,
    QToolBar,
    QWidget,
)

from app.core.models import AbaqusJob
from app.core.scanner import JobScanner
from app.ui.file_viewer import FileViewerWidget
from app.ui.job_browser import JobBrowserWidget
from app.ui.job_runner_panel import JobRunnerPanel
from app.ui.progress_monitor import ProgressMonitorWidget
from app.ui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._root_folder: Optional[Path] = None
        self._jobs: List[AbaqusJob] = []

        self.setWindowTitle("Abaqus Job Manager")
        self.setMinimumSize(1100, 700)

        self._build_ui()
        self._build_toolbar()
        self._restore_state()

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        # ── Right-side tab widget ──────────────────────────────────── #
        self._right_tabs = QTabWidget()
        self._right_tabs.setTabPosition(QTabWidget.TabPosition.North)

        self._runner_panel   = JobRunnerPanel()
        self._progress_panel = ProgressMonitorWidget()
        self._file_viewer    = FileViewerWidget()

        self._right_tabs.addTab(self._runner_panel,   "Run")
        self._right_tabs.addTab(self._progress_panel, "Progress")
        self._right_tabs.addTab(self._file_viewer,    "Files")

        # ── Left-side browser ─────────────────────────────────────── #
        self._browser = JobBrowserWidget()
        self._browser.job_selected.connect(self._on_job_selected)

        # ── Splitter ──────────────────────────────────────────────── #
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._browser)
        splitter.addWidget(self._right_tabs)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([380, 720])

        self.setCentralWidget(splitter)

        # ── Status bar ────────────────────────────────────────────── #
        self._status_folder = QLabel("No folder open")
        self.statusBar().addPermanentWidget(self._status_folder)
        self.statusBar().showMessage("Ready")

        # ── Wire job runner signals ───────────────────────────────── #
        self._runner_panel.job_started_signal.connect(self._on_job_started)
        self._runner_panel.job_finished_signal.connect(self._on_job_finished)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        self.addToolBar(tb)

        open_action = QAction("Open Folder", self)
        open_action.setToolTip("Open a folder containing Abaqus jobs")
        open_action.triggered.connect(self._open_folder)
        tb.addAction(open_action)

        refresh_action = QAction("Refresh", self)
        refresh_action.setToolTip("Rescan the current folder")
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self._refresh)
        tb.addAction(refresh_action)

        tb.addSeparator()

        settings_action = QAction("Settings", self)
        settings_action.setToolTip("Application settings")
        settings_action.triggered.connect(self._open_settings)
        tb.addAction(settings_action)

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #

    def _open_folder(self) -> None:
        start = str(self._root_folder) if self._root_folder else ""
        folder = QFileDialog.getExistingDirectory(
            self, "Open Job Folder", start,
            QFileDialog.Option.ShowDirsOnly
        )
        if folder:
            self._root_folder = Path(folder)
            self._scan_and_refresh()
            self._save_state()

    def _refresh(self) -> None:
        if self._root_folder:
            self._scan_and_refresh()

    def _scan_and_refresh(self) -> None:
        if not self._root_folder:
            return
        self.statusBar().showMessage(f"Scanning {self._root_folder} …")
        scanner = JobScanner(self._root_folder)
        self._jobs = scanner.scan()
        self._browser.refresh(self._jobs)
        count = len(self._jobs)
        self._status_folder.setText(f"  {self._root_folder}")
        self.statusBar().showMessage(
            f"Found {count} job{'s' if count != 1 else ''}"
        )

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self)
        if dlg.exec():
            self._runner_panel.set_abaqus_exe(dlg.abaqus_exe)

    # ------------------------------------------------------------------ #
    # Job selection
    # ------------------------------------------------------------------ #

    def _on_job_selected(self, job: Optional[AbaqusJob]) -> None:
        self._runner_panel.set_job(job)
        self._progress_panel.set_job(job)
        self._file_viewer.set_job(job)

    # ------------------------------------------------------------------ #
    # Job runner lifecycle
    # ------------------------------------------------------------------ #

    def _on_job_started(self) -> None:
        self._progress_panel.start_monitoring()
        self.statusBar().showMessage("Job running…")

    def _on_job_finished(self, exit_code: int) -> None:
        self._progress_panel.on_job_finished()
        msg = "Job completed successfully." if exit_code == 0 else f"Job exited with code {exit_code}."
        self.statusBar().showMessage(msg)
        # Refresh status column for the currently selected job
        # Find the job that was running
        runner = self._runner_panel.runner
        # Re-scan to pick up new status files
        self._scan_and_refresh()

    # ------------------------------------------------------------------ #
    # Persistent state
    # ------------------------------------------------------------------ #

    def _save_state(self) -> None:
        s = QSettings("AbaqusJobManager", "AJM")
        s.setValue("window/geometry", self.saveGeometry())
        s.setValue("window/state",    self.saveState())
        if self._root_folder:
            s.setValue("window/last_folder", str(self._root_folder))

    def _restore_state(self) -> None:
        s = QSettings("AbaqusJobManager", "AJM")
        geom = s.value("window/geometry")
        if geom:
            self.restoreGeometry(geom)
        state = s.value("window/state")
        if state:
            self.restoreState(state)
        last = s.value("window/last_folder")
        if last:
            folder = Path(last)
            if folder.is_dir():
                self._root_folder = folder
                self._scan_and_refresh()

        # Apply abaqus exe from settings
        exe = s.value("abaqus/exe", None)
        if exe:
            self._runner_panel.set_abaqus_exe(str(exe))

    def closeEvent(self, event) -> None:
        self._save_state()
        super().closeEvent(event)
