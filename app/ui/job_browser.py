"""
Job browser panel — cascading-filter table of all discovered jobs.

Filters: Project (job_number) → CAE → Model → Job
Each level repopulates based on what is selected above it.
Choosing "All" at any level shows everything beneath it.
"""
from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.core.models import AbaqusJob
from app.models.job_table_model import JobFilterProxyModel, JobTableModel


class JobBrowserWidget(QWidget):
    """
    Left-pane widget showing all jobs in a sortable, cascading-filter table.

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
        self._all_jobs: List[AbaqusJob] = []
        self._source_model = JobTableModel(self)
        self._proxy_model  = JobFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._source_model)

        self._build_ui()

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # ── Cascading filter grid ─────────────────────────────────────── #
        filter_grid = QGridLayout()
        filter_grid.setSpacing(4)
        filter_grid.setContentsMargins(0, 0, 0, 0)

        for col, text in enumerate(("Project", "CAE", "Model", "Job")):
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #888; font-size: 11px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            filter_grid.addWidget(lbl, 0, col)

        self._combo_project = QComboBox()
        self._combo_cae     = QComboBox()
        self._combo_model   = QComboBox()
        self._combo_job     = QComboBox()

        for col, combo in enumerate((
            self._combo_project, self._combo_cae,
            self._combo_model,   self._combo_job,
        )):
            combo.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
            combo.addItem("All", None)   # default "show everything" entry
            filter_grid.addWidget(combo, 1, col)

        # Project column gets proportionally more space for longer job numbers
        filter_grid.setColumnStretch(0, 3)
        filter_grid.setColumnStretch(1, 1)
        filter_grid.setColumnStretch(2, 1)
        filter_grid.setColumnStretch(3, 1)

        layout.addLayout(filter_grid)

        # ── Table view ────────────────────────────────────────────────── #
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

        self._table.selectionModel().currentRowChanged.connect(self._on_row_changed)
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)

        layout.addWidget(self._table, stretch=1)

        # ── Status bar ────────────────────────────────────────────────── #
        self._status_label = QLabel("0 jobs")
        self._status_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._status_label)

        # ── Wire combo signals (after table exists so _apply_filter is safe) #
        self._combo_project.currentIndexChanged.connect(self._on_project_changed)
        self._combo_cae.currentIndexChanged.connect(self._on_cae_changed)
        self._combo_model.currentIndexChanged.connect(self._on_model_changed)
        self._combo_job.currentIndexChanged.connect(self._on_job_changed)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def refresh(self, jobs: List[AbaqusJob], preserve_selection: bool = True) -> None:
        """
        Reload the model.  Repopulates filter combos (preserving selections
        where the value still exists) then re-applies the active filter.
        """
        stem_to_restore: Optional[str] = None
        if preserve_selection:
            current = self._table.currentIndex()
            if current.isValid():
                job = self._proxy_model.job_at_proxy_row(current.row())
                if job:
                    stem_to_restore = job.stem

        self._all_jobs = jobs
        self._source_model.refresh(jobs)

        # Repopulate combos without triggering cascade signals, then apply once
        self._populate_project_combo()
        self._populate_cae_combo()
        self._populate_model_combo()
        self._populate_job_combo()
        self._apply_filter()

        self._table.resizeColumnsToContents()
        self._table.horizontalHeader().setStretchLastSection(True)

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
    # Cascading combo population
    # ------------------------------------------------------------------ #

    def _populate_project_combo(self) -> None:
        combo = self._combo_project
        prev  = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("All", None)
        for val in sorted({j.job_number for j in self._all_jobs}):
            combo.addItem(val, val)
        idx = combo.findData(prev)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _populate_cae_combo(self) -> None:
        project = self._combo_project.currentData()
        pool    = [j for j in self._all_jobs
                   if project is None or j.job_number == project]
        combo   = self._combo_cae
        prev    = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("All", None)
        for val in sorted({j.cae for j in pool}):
            combo.addItem(f"C{val:02d}", val)
        idx = combo.findData(prev)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _populate_model_combo(self) -> None:
        project = self._combo_project.currentData()
        cae     = self._combo_cae.currentData()
        pool    = [j for j in self._all_jobs
                   if (project is None or j.job_number == project)
                   and (cae     is None or j.cae        == cae)]
        combo   = self._combo_model
        prev    = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("All", None)
        for val in sorted({j.model for j in pool}):
            combo.addItem(f"M{val:02d}", val)
        idx = combo.findData(prev)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _populate_job_combo(self) -> None:
        project = self._combo_project.currentData()
        cae     = self._combo_cae.currentData()
        model   = self._combo_model.currentData()
        pool    = [j for j in self._all_jobs
                   if (project is None or j.job_number == project)
                   and (cae     is None or j.cae        == cae)
                   and (model   is None or j.model      == model)]
        combo   = self._combo_job
        prev    = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("All", None)
        for val in sorted({j.job_local for j in pool}):
            combo.addItem(f"J{val:02d}", val)
        idx = combo.findData(prev)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    # ------------------------------------------------------------------ #
    # Combo signal handlers
    # ------------------------------------------------------------------ #

    def _on_project_changed(self) -> None:
        self._populate_cae_combo()
        self._populate_model_combo()
        self._populate_job_combo()
        self._apply_filter()

    def _on_cae_changed(self) -> None:
        self._populate_model_combo()
        self._populate_job_combo()
        self._apply_filter()

    def _on_model_changed(self) -> None:
        self._populate_job_combo()
        self._apply_filter()

    def _on_job_changed(self) -> None:
        self._apply_filter()

    def _apply_filter(self) -> None:
        self._proxy_model.set_filter(
            job_number=self._combo_project.currentData(),
            cae=self._combo_cae.currentData(),
            model=self._combo_model.currentData(),
            job_local=self._combo_job.currentData(),
        )
        visible = self._proxy_model.rowCount()
        total   = len(self._all_jobs)
        if visible == total:
            self._status_label.setText(
                f"{total} job{'s' if total != 1 else ''} found"
            )
        else:
            self._status_label.setText(
                f"{visible} of {total} job{'s' if total != 1 else ''}"
            )

    # ------------------------------------------------------------------ #
    # Table selection handlers
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
    # Context menu
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
