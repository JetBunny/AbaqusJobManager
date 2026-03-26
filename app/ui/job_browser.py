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
    QMenu,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.core.models import AbaqusJob
from app.models.job_table_model import JobFilterProxyModel, JobTableModel


class JobBrowserWidget(QWidget):
    """
    Left-pane widget showing all jobs in a sortable, filterable table.

    Signals:
        job_selected(AbaqusJob | None)  — primary (last-clicked) job
        jobs_compare_selected(list)     — all currently selected jobs
        open_cae_requested(AbaqusJob)   — user chose "Open in CAE" from context menu
    """

    job_selected          = pyqtSignal(object)   # AbaqusJob or None
    jobs_compare_selected = pyqtSignal(list)      # list[AbaqusJob]
    open_cae_requested    = pyqtSignal(object)    # AbaqusJob

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

        # Table view — ExtendedSelection enables Ctrl/Shift multi-select
        self._table = QTableView()
        self._table.setModel(self._proxy_model)
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)

        # primary job (current row)
        self._table.selectionModel().currentRowChanged.connect(
            self._on_row_changed
        )
        # multi-select: fires whenever selection set changes
        self._table.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        )

        layout.addWidget(self._table, stretch=1)

        # Status bar
        self._status_label = QLabel("0 jobs")
        self._status_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._status_label)

    # ------------------------------------------------------------------ #

    def refresh(self, jobs: List[AbaqusJob], preserve_selection: bool = True) -> None:
        """
        Reload the model.  If preserve_selection is True, tries to re-select
        the previously selected job (by stem) after the reset.
        """
        # Remember what was selected
        stem_to_restore: Optional[str] = None
        if preserve_selection:
            current = self._table.currentIndex()
            if current.isValid():
                job = self._proxy_model.job_at_proxy_row(current.row())
                if job:
                    stem_to_restore = job.stem

        self._source_model.refresh(jobs)
        count = len(jobs)
        self._status_label.setText(
            f"{count} job{'s' if count != 1 else ''} found"
        )
        self._table.resizeColumnsToContents()
        self._table.horizontalHeader().setStretchLastSection(True)

        # Re-select by stem if possible
        if stem_to_restore:
            for row in range(self._proxy_model.rowCount()):
                job = self._proxy_model.job_at_proxy_row(row)
                if job and job.stem == stem_to_restore:
                    self._table.selectRow(row)
                    self._table.scrollTo(self._proxy_model.index(row, 0))
                    break

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

    def _on_selection_changed(self, _selected, _deselected) -> None:
        indexes = self._table.selectionModel().selectedRows()
        jobs = []
        for idx in indexes:
            job = self._proxy_model.job_at_proxy_row(idx.row())
            if job:
                jobs.append(job)
        self.jobs_compare_selected.emit(jobs)

    # ------------------------------------------------------------------ #

    def _show_context_menu(self, pos) -> None:
        index = self._table.indexAt(pos)
        if not index.isValid():
            return
        job = self._proxy_model.job_at_proxy_row(index.row())
        if job is None:
            return

        menu = QMenu(self)

        open_cae = menu.addAction("Open in Abaqus CAE")
        open_cae.setEnabled(bool(job.cae_file and job.cae_file.exists()))

        action = menu.exec(self._table.viewport().mapToGlobal(pos))
        if action == open_cae:
            self.open_cae_requested.emit(job)
