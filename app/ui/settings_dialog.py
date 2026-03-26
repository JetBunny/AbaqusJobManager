"""
Settings dialog for persistent preferences.
"""
from __future__ import annotations

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.job_runner import find_abaqus_executable


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(480)
        self._build_ui()
        self._load()

    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # --- Abaqus ---
        abq_group = QGroupBox("Abaqus")
        abq_form  = QFormLayout(abq_group)

        exe_row = QHBoxLayout()
        self._exe_edit = QLineEdit()
        self._exe_edit.setPlaceholderText("Path to abaqus or abaqus.bat")
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_exe)
        exe_row.addWidget(self._exe_edit, stretch=1)
        exe_row.addWidget(browse_btn)
        abq_form.addRow("Executable:", exe_row)

        detect_btn = QPushButton("Auto-detect")
        detect_btn.clicked.connect(self._auto_detect)
        abq_form.addRow("", detect_btn)

        layout.addWidget(abq_group)

        # --- File Viewer ---
        viewer_group = QGroupBox("File Viewer")
        viewer_form  = QFormLayout(viewer_group)

        self._head_spin = QSpinBox()
        self._head_spin.setRange(50, 5000)
        self._head_spin.setSingleStep(50)
        self._head_spin.setValue(500)
        viewer_form.addRow("Preview head lines:", self._head_spin)

        self._tail_spin = QSpinBox()
        self._tail_spin.setRange(50, 5000)
        self._tail_spin.setSingleStep(50)
        self._tail_spin.setValue(500)
        viewer_form.addRow("Preview tail lines:", self._tail_spin)

        layout.addWidget(viewer_group)

        # --- Buttons ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------ #

    def _browse_exe(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Abaqus Executable", "",
            "Executables (*.bat *.cmd *.exe);;All Files (*)"
        )
        if path:
            self._exe_edit.setText(path)

    def _auto_detect(self) -> None:
        exe = find_abaqus_executable()
        self._exe_edit.setText(exe)

    def _load(self) -> None:
        s = QSettings("AbaqusJobManager", "AJM")
        self._exe_edit.setText(str(s.value("abaqus/exe", find_abaqus_executable())))
        self._head_spin.setValue(int(s.value("viewer/head_lines", 500)))
        self._tail_spin.setValue(int(s.value("viewer/tail_lines", 500)))

    def _save_and_accept(self) -> None:
        s = QSettings("AbaqusJobManager", "AJM")
        s.setValue("abaqus/exe",         self._exe_edit.text().strip())
        s.setValue("viewer/head_lines",  self._head_spin.value())
        s.setValue("viewer/tail_lines",  self._tail_spin.value())
        self.accept()

    # ------------------------------------------------------------------ #
    # Accessors for MainWindow to use after accept()
    # ------------------------------------------------------------------ #

    @property
    def abaqus_exe(self) -> str:
        return self._exe_edit.text().strip()
