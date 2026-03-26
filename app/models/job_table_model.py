"""
QAbstractTableModel for the job list, with a sort/filter proxy.
"""
from __future__ import annotations

from typing import Any, List, Optional

from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
)
from PyQt6.QtGui import QColor, QFont

from app.core.models import AbaqusJob, JobStatus

# Column definitions: (header_label, attribute_name_or_callable)
_COLUMNS = [
    ("Job Number",  "job_number"),
    ("CAE",         "cae"),
    ("Model",       "model"),
    ("Job",         "job_local"),
    ("Status",      "status"),
    ("INP",         "inp_file"),
    ("STA",         "sta_file"),
    ("DAT",         "dat_file"),
    ("MSG",         "msg_file"),
    ("Folder",      "folder"),
]

_STATUS_COLORS = {
    JobStatus.COMPLETED:     QColor("#4CAF50"),   # green
    JobStatus.RUNNING:       QColor("#2196F3"),   # blue
    JobStatus.ABORTED:       QColor("#F44336"),   # red
    JobStatus.NOT_SUBMITTED: QColor("#9E9E9E"),   # grey
    JobStatus.UNKNOWN:       QColor("#9E9E9E"),
}


class JobTableModel(QAbstractTableModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._jobs: List[AbaqusJob] = []

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def refresh(self, jobs: List[AbaqusJob]) -> None:
        self.beginResetModel()
        self._jobs = jobs
        self.endResetModel()

    def job_at(self, row: int) -> Optional[AbaqusJob]:
        if 0 <= row < len(self._jobs):
            return self._jobs[row]
        return None

    def all_jobs(self) -> List[AbaqusJob]:
        return list(self._jobs)

    def update_job_status(self, job: AbaqusJob) -> None:
        """Refresh the status column for a single job."""
        try:
            row = self._jobs.index(job)
        except ValueError:
            return
        status_col = next(i for i, (_, a) in enumerate(_COLUMNS) if a == "status")
        idx = self.index(row, status_col)
        self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ForegroundRole])

    # ------------------------------------------------------------------ #
    # QAbstractTableModel interface
    # ------------------------------------------------------------------ #

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._jobs)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(_COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return _COLUMNS[section][0]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        job = self._jobs[index.row()]
        col_name = _COLUMNS[index.column()][1]

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_value(job, col_name)

        if role == Qt.ItemDataRole.ForegroundRole and col_name == "status":
            return _STATUS_COLORS.get(job.status, QColor("#9E9E9E"))

        if role == Qt.ItemDataRole.FontRole and col_name == "status":
            f = QFont()
            f.setBold(True)
            return f

        if role == Qt.ItemDataRole.UserRole:
            return job  # allows proxy to retrieve job object

        return None

    # ------------------------------------------------------------------ #

    @staticmethod
    def _display_value(job: AbaqusJob, attr: str) -> str:
        val = getattr(job, attr, None)
        if val is None:
            return ""
        if attr == "status":
            return val.name.replace("_", " ").title()
        if attr in ("inp_file", "sta_file", "dat_file", "msg_file", "cae_file"):
            return "Yes" if val else ""
        return str(val)


# ------------------------------------------------------------------ #
# Proxy model
# ------------------------------------------------------------------ #

class JobFilterProxyModel(QSortFilterProxyModel):
    """Case-insensitive filter across all text columns."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterKeyColumn(-1)  # search all columns

    def job_at_proxy_row(self, proxy_row: int) -> Optional[AbaqusJob]:
        source_index = self.mapToSource(self.index(proxy_row, 0))
        src_model: JobTableModel = self.sourceModel()
        return src_model.job_at(source_index.row())
