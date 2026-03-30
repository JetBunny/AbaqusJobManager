"""
Main application window.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import QSettings, QSize, Qt, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QSplitter,
    QTabWidget,
    QToolBar,
    QWidget,
)

from app.core.models import AbaqusJob, JobStatus
from app.core.scanner import JobScanner
from app.ui.file_viewer import FileViewerWidget
from app.ui.job_browser import JobBrowserWidget
from app.ui.job_compare_widget import JobCompareWidget
from app.ui.job_runner_panel import JobRunnerPanel
from app.ui.log_tail_widget import LogTailWidget
from app.ui.progress_monitor import ProgressMonitorWidget
from app.ui.settings_dialog import SettingsDialog

_AUTO_REFRESH_INTERVAL_MS = 5_000   # 5 seconds


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._root_folder: Optional[Path] = None
        self._jobs: List[AbaqusJob] = []
        self._running_job_stem: Optional[str] = None

        self.setWindowTitle("Abaqus Job Manager")
        self.setMinimumSize(1100, 700)

        self._build_ui()
        self._build_toolbar()
        self._build_auto_refresh_timer()
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
        self._log_tail       = LogTailWidget()
        self._compare_widget = JobCompareWidget()

        self._right_tabs.addTab(self._runner_panel,   "Run")
        self._right_tabs.addTab(self._progress_panel, "Progress")
        self._right_tabs.addTab(self._file_viewer,    "Files")
        self._right_tabs.addTab(self._log_tail,       "MSG Tail")
        self._right_tabs.addTab(self._compare_widget, "Compare")

        # ── Left-side browser ─────────────────────────────────────── #
        self._browser = JobBrowserWidget()
        self._browser.job_selected.connect(self._on_job_selected)
        self._browser.jobs_compare_selected.connect(self._compare_widget.set_jobs)
        self._browser.open_cae_requested.connect(self._runner_panel.open_cae)

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
        refresh_action.setToolTip("Rescan the current folder (F5)")
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self._refresh)
        tb.addAction(refresh_action)

        tb.addSeparator()

        # Auto-refresh toggle
        self._auto_refresh_action = QAction("Auto-Refresh: ON", self)
        self._auto_refresh_action.setToolTip(
            "Toggle automatic folder rescan every 30 seconds"
        )
        self._auto_refresh_action.setCheckable(True)
        self._auto_refresh_action.setChecked(True)
        self._auto_refresh_action.toggled.connect(self._on_auto_refresh_toggled)
        tb.addAction(self._auto_refresh_action)

        tb.addSeparator()

        settings_action = QAction("Settings", self)
        settings_action.setToolTip("Application settings")
        settings_action.triggered.connect(self._open_settings)
        tb.addAction(settings_action)

    def _build_auto_refresh_timer(self) -> None:
        self._auto_refresh_timer = QTimer(self)
        self._auto_refresh_timer.setInterval(_AUTO_REFRESH_INTERVAL_MS)
        self._auto_refresh_timer.timeout.connect(self._auto_refresh)

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
            self._scan_and_refresh(notify_panels=True)
            self._save_state()
            # Start auto-refresh once a folder is open
            if self._auto_refresh_action.isChecked():
                self._auto_refresh_timer.start()

    def _refresh(self) -> None:
        if self._root_folder:
            self._scan_and_refresh(notify_panels=True)

    def _auto_refresh(self) -> None:
        """Background rescan — preserves selection, re-applies RUNNING status if needed."""
        if self._root_folder:
            self._scan_and_refresh(notify_panels=False)

    def _scan_and_refresh(self, notify_panels: bool = True) -> None:
        if not self._root_folder:
            return
        scanner = JobScanner(self._root_folder)
        self._jobs = scanner.scan()

        # If a job is actively running, the scanner may not see its .lck file
        # in time, or the new job objects won't carry the in-memory RUNNING flag.
        # Re-apply it here so the status column stays correct during the run.
        if self._running_job_stem:
            for job in self._jobs:
                if job.stem == self._running_job_stem:
                    job.status = JobStatus.RUNNING
                    break

        self._browser.refresh(self._jobs, preserve_selection=True)
        count = len(self._jobs)
        self._status_folder.setText(f"  {self._root_folder}")
        if notify_panels:
            self.statusBar().showMessage(
                f"Found {count} job{'s' if count != 1 else ''}"
            )

    def _on_auto_refresh_toggled(self, checked: bool) -> None:
        if checked:
            self._auto_refresh_action.setText("Auto-Refresh: ON")
            if self._root_folder:
                self._auto_refresh_timer.start()
        else:
            self._auto_refresh_action.setText("Auto-Refresh: OFF")
            self._auto_refresh_timer.stop()

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
        self._log_tail.set_job(job)

    # ------------------------------------------------------------------ #
    # Job runner lifecycle
    # ------------------------------------------------------------------ #

    def _on_job_started(self) -> None:
        self._progress_panel.start_monitoring()
        self._log_tail.start_monitoring()
        self.statusBar().showMessage("Job running…")
        # Track which job is running so rescans keep the RUNNING status correct
        job = self._runner_panel.current_job
        if job:
            self._running_job_stem = job.stem
            job.status = JobStatus.RUNNING
            self._browser.refresh_job_status(job)
            self._browser.source_model().set_running_stem(job.stem)
        # Switch to MSG Tail tab automatically so user sees live output
        self._right_tabs.setCurrentWidget(self._log_tail)

    def _on_job_finished(self, exit_code: int) -> None:
        self._running_job_stem = None
        self._browser.source_model().set_running_stem(None)
        self._progress_panel.on_job_finished()
        self._log_tail.on_job_finished()
        msg = "Job completed successfully." if exit_code == 0 else f"Job exited with code {exit_code}."
        self.statusBar().showMessage(msg)
        self._scan_and_refresh(notify_panels=True)

    # ------------------------------------------------------------------ #
    # Persistent state
    # ------------------------------------------------------------------ #

    def _save_state(self) -> None:
        s = QSettings("AbaqusJobManager", "AJM")
        s.setValue("window/geometry",     self.saveGeometry())
        s.setValue("window/state",        self.saveState())
        s.setValue("window/auto_refresh", self._auto_refresh_action.isChecked())
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

        auto = s.value("window/auto_refresh", True)
        auto_bool = auto if isinstance(auto, bool) else str(auto).lower() != "false"
        self._auto_refresh_action.setChecked(auto_bool)

        last = s.value("window/last_folder")
        if last:
            folder = Path(last)
            if folder.is_dir():
                self._root_folder = folder
                self._scan_and_refresh(notify_panels=True)
                if auto_bool:
                    self._auto_refresh_timer.start()

        exe = s.value("abaqus/exe", None)
        if exe:
            self._runner_panel.set_abaqus_exe(str(exe))

    def closeEvent(self, event) -> None:
        self._save_state()
        super().closeEvent(event)
