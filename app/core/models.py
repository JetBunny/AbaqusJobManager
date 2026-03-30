"""
Core data models for Abaqus Job Manager.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional

# Compiled once — single source of truth for the naming convention
JOB_NAME_RE = re.compile(
    r'^(\d+)_C(\d+)_M(\d+)_J(\d+)', re.IGNORECASE
)


class JobStatus(Enum):
    UNKNOWN = auto()
    NOT_SUBMITTED = auto()
    RUNNING = auto()
    COMPLETED = auto()
    ABORTED = auto()


def parse_job_name(stem: str) -> Optional[dict]:
    """
    Parse a filename stem matching the convention <num>_C<xx>_M<xx>_J<xx>.
    Returns a dict with keys: job_number, cae, model, job_local
    or None if the stem does not match.
    """
    m = JOB_NAME_RE.match(stem)
    if not m:
        return None
    return {
        "job_number": m.group(1),
        "cae":        int(m.group(2)),
        "model":      int(m.group(3)),
        "job_local":  int(m.group(4)),
    }


@dataclass
class AbaqusJob:
    job_number: str
    cae: int
    model: int
    job_local: int
    folder: Path

    # File references (None if not found)
    inp_file: Optional[Path] = None
    cae_file: Optional[Path] = None
    sta_file: Optional[Path] = None
    dat_file: Optional[Path] = None
    msg_file: Optional[Path] = None

    status: JobStatus = JobStatus.UNKNOWN

    # ------------------------------------------------------------------ #
    # Derived helpers
    # ------------------------------------------------------------------ #
    @property
    def stem(self) -> str:
        """Canonical job name stem, e.g. 410123_C03_M02_J01."""
        return f"{self.job_number}_C{self.cae:02d}_M{self.model:02d}_J{self.job_local:02d}"

    @property
    def display_name(self) -> str:
        return self.stem

    def infer_status(self) -> JobStatus:
        """
        Infer job status from file evidence.
        Call this after loading to populate the status field.
        """
        # Abaqus creates a .lck file for the duration of a run — most reliable signal
        lck_path = self.folder / f"{self.stem}.lck"
        if lck_path.exists():
            return JobStatus.RUNNING

        if self.sta_file and self.sta_file.exists():
            try:
                text = self.sta_file.read_text(encoding="latin-1", errors="replace")
                upper = text.upper()
                if "THE ANALYSIS HAS COMPLETED SUCCESSFULLY" in upper:
                    return JobStatus.COMPLETED
                if "ANALYSIS TERMINATED" in upper:
                    return JobStatus.ABORTED
            except OSError:
                pass

        if self.msg_file and self.msg_file.exists():
            try:
                text = self.msg_file.read_text(encoding="latin-1", errors="replace")
                upper = text.upper()
                if "ANALYSIS TERMINATED" in upper or "***ERROR" in upper:
                    return JobStatus.ABORTED
            except OSError:
                pass

        if self.sta_file and self.sta_file.exists():
            # sta exists but no completion/error phrase and no lock → killed or crashed mid-run
            return JobStatus.ABORTED

        if self.inp_file and self.inp_file.exists():
            return JobStatus.NOT_SUBMITTED

        return JobStatus.UNKNOWN

    def refresh_status(self) -> None:
        self.status = self.infer_status()

    def sort_key(self) -> tuple:
        return (self.job_number, self.cae, self.model, self.job_local)
