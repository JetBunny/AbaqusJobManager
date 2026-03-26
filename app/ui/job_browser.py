"""
Job browser panel — searchable, sortable table of all discovered jobs.
"""
from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.core.models import AbaqusJob
from app.models.job_table_model import JobFilterProxyModel, JobTableModel


class JobBrowserWidget(QWidget):
    """
    Left-pane widget showing all jobs in a sortable, filterable table.
    Emits job_selected(AbaqusJob) when the user clicks a row.
    """

    job_selected = pyqtSignal(object)   # AbaqusJob or None

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self._source_model = JobTableModel(self)
        self._proxy_model  = JobFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._source_model)

        self._build_ui()

    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Search bar
        search_row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search jobs…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._proxy_model.setFilterFixedString)
        search_row.addWidget(QLabel("Filter:"))
        search_row.addWidget(self._search, stretch=1)
        layout.addLayout(search_row)

        # Table view
        self._table = QTableView()
        self._table.setModel(self._proxy_model)
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        # Stretch the Folder column
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.sortByColumn(0, Qt.SortOrder.AscendingOrder)

        # Connect selection
        self._table.selectionModel().currentRowChanged.connect(
            self._on_row_changed
        )

        layout.addWidget(self._table, stretch=1)

        # Status bar
        self._status_label = QLabel("0 jobs")
        self._status_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._status_label)

    # ------------------------------------------------------------------ #

    def refresh(self, jobs: List[AbaqusJob]) -> None:
        self._source_model.refresh(jobs)
        count = len(jobs)
        self._status_label.setText(
            f"{count} job{'s' if count != 1 else ''} found"
        )
        self._table.resizeColumnsToContents()
        # Keep folder column wide
        self._table.horizontalHeader().setStretchLastSection(True)

    def refresh_job_status(self, job: AbaqusJob) -> None:
        job.refresh_status()
        self._source_model.update_job_status(job)

    def source_model(self) -> JobTableModel:
        return self._source_model

    # ------------------------------------------------------------------ #

    def _on_row_changed(self, current, _previous) -> None:
        if not current.isValid():
            self.job_selected.emit(None)
            return
        job = self._proxy_model.job_at_proxy_row(current.row())
        self.job_selected.emit(job)
