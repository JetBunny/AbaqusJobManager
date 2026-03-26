"""
Job runner panel — CPU/GPU controls, run/kill buttons, live output log.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QSettings, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.job_runner import AbaqusJobRunner
from app.core.models import AbaqusJob


class JobRunnerPanel(QWidget):
    """
    Panel that lets the user configure and launch an Abaqus job,
    view live output, and kill a running job.
    """

    job_started_signal  = pyqtSignal()
    job_finished_signal = pyqtSignal(int)

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self._current_job: Optional[AbaqusJob] = None
        self._runner = AbaqusJobRunner(self)
        self._runner.output_received.connect(self._append_output)
        self._runner.job_started.connect(self._on_job_started)
        self._runner.job_finished.connect(self._on_job_finished)

        self._build_ui()
        self._restore_settings()

    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # --- Job info header ---
        self._job_label = QLabel("No job selected")
        self._job_label.setStyleSheet(
            "font-weight: bold; font-size: 13px; color: #cccccc; padding: 4px;"
        )
        layout.addWidget(self._job_label)

        # --- Settings group ---
        settings_group = QGroupBox("Run Settings")
        form = QFormLayout(settings_group)

        self._cpu_spin = QSpinBox()
        self._cpu_spin.setRange(1, 256)
        self._cpu_spin.setValue(4)
        self._cpu_spin.setToolTip("Number of CPU cores to use")
        form.addRow("CPUs:", self._cpu_spin)

        self._gpu_spin = QSpinBox()
        self._gpu_spin.setRange(0, 16)
        self._gpu_spin.setValue(0)
        self._gpu_spin.setToolTip("Number of GPUs to use (0 = CPU only)")
        form.addRow("GPUs:", self._gpu_spin)

        layout.addWidget(settings_group)

        # --- Buttons ---
        btn_layout = QHBoxLayout()

        self._run_btn = QPushButton("Run Job")
        self._run_btn.setObjectName("runButton")
        self._run_btn.setFixedHeight(36)
        self._run_btn.clicked.connect(self._on_run_clicked)

        self._kill_btn = QPushButton("Kill Job")
        self._kill_btn.setObjectName("killButton")
        self._kill_btn.setFixedHeight(36)
        self._kill_btn.setEnabled(False)
        self._kill_btn.clicked.connect(self._on_kill_clicked)

        self._clear_btn = QPushButton("Clear Log")
        self._clear_btn.setFixedHeight(36)
        self._clear_btn.clicked.connect(self._output_log.clear if hasattr(self, "_output_log") else lambda: None)

        btn_layout.addWidget(self._run_btn)
        btn_layout.addWidget(self._kill_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self._clear_btn)
        layout.addLayout(btn_layout)

        # --- Output log ---
        log_label = QLabel("Output:")
        log_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(log_label)

        self._output_log = QPlainTextEdit()
        self._output_log.setReadOnly(True)
        mono = QFont("Consolas", 9)
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self._output_log.setFont(mono)
        self._output_log.setMaximumBlockCount(5000)  # keep last 5000 lines
        layout.addWidget(self._output_log, stretch=1)

        # Fix clear button now that _output_log exists
        self._clear_btn.clicked.disconnect()
        self._clear_btn.clicked.connect(self._output_log.clear)

    # ------------------------------------------------------------------ #

    def set_job(self, job: Optional[AbaqusJob]) -> None:
        self._current_job = job
        if job is None:
            self._job_label.setText("No job selected")
            self._run_btn.setEnabled(False)
        else:
            self._job_label.setText(job.display_name)
            has_inp = job.inp_file is not None and job.inp_file.exists()
            self._run_btn.setEnabled(has_inp and not self._runner.is_running)

    def set_abaqus_exe(self, path: str) -> None:
        self._runner.abaqus_exe = path

    @property
    def runner(self) -> AbaqusJobRunner:
        return self._runner

    # ------------------------------------------------------------------ #

    def _on_run_clicked(self) -> None:
        if self._current_job is None:
            return
        inp = self._current_job.inp_file
        if not inp or not inp.exists():
            self._append_output("[AJM] No .inp file found for this job.\n")
            return

        cpus = self._cpu_spin.value()
        gpus = self._gpu_spin.value()
        self._save_settings()
        self._runner.run(inp, cpus, gpus)

    def _on_kill_clicked(self) -> None:
        self._runner.kill()

    def _on_job_started(self) -> None:
        self._run_btn.setEnabled(False)
        self._kill_btn.setEnabled(True)
        self.job_started_signal.emit()

    def _on_job_finished(self, exit_code: int) -> None:
        self._kill_btn.setEnabled(False)
        if self._current_job is not None:
            has_inp = self._current_job.inp_file is not None
            self._run_btn.setEnabled(has_inp)
        self.job_finished_signal.emit(exit_code)

    def _append_output(self, text: str) -> None:
        self._output_log.moveCursor(self._output_log.textCursor().MoveOperation.End)
        self._output_log.insertPlainText(text)
        self._output_log.moveCursor(self._output_log.textCursor().MoveOperation.End)

    # ------------------------------------------------------------------ #

    def _save_settings(self) -> None:
        s = QSettings("AbaqusJobManager", "AJM")
        s.setValue("runner/cpus", self._cpu_spin.value())
        s.setValue("runner/gpus", self._gpu_spin.value())

    def _restore_settings(self) -> None:
        s = QSettings("AbaqusJobManager", "AJM")
        cpus = int(s.value("runner/cpus", 4))
        gpus = int(s.value("runner/gpus", 0))
        self._cpu_spin.setValue(cpus)
        self._gpu_spin.setValue(gpus)
