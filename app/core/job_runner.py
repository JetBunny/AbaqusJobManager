"""
QProcess-based wrapper for running Abaqus jobs.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, QProcess, pyqtSignal


# Common Windows install locations for the abaqus executable
_WINDOWS_ABAQUS_CANDIDATES = [
    r"C:\SIMULIA\Commands\abaqus.bat",
    r"C:\SIMULIA\Commands\abaqus.cmd",
    r"C:\Program Files\Dassault Systemes\SIMULIA\Commands\abaqus.bat",
]


def find_abaqus_executable() -> str:
    """
    Attempt to locate the abaqus executable.
    Priority: environment variables -> known paths -> PATH fallback.
    """
    # Check SIMULIA environment variables
    for env_var in ("SIMULIA_CSE_HOME", "ABA_HOME"):
        base = os.environ.get(env_var)
        if base:
            candidate = Path(base) / "Commands" / "abaqus.bat"
            if candidate.exists():
                return str(candidate)

    # Check known paths
    for candidate in _WINDOWS_ABAQUS_CANDIDATES:
        if Path(candidate).exists():
            return candidate

    # Fall back to hoping it's on PATH
    return "abaqus"


class AbaqusJobRunner(QObject):
    """
    Wraps QProcess to run an Abaqus job asynchronously.

    Signals:
        output_received(str)  — new stdout/stderr text chunk
        job_finished(int)     — process exited with given code
        job_started()         — process has started
    """

    output_received = pyqtSignal(str)
    job_finished    = pyqtSignal(int)
    job_started     = pyqtSignal()

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent)
        self._process: Optional[QProcess] = None
        self._abaqus_exe: str = find_abaqus_executable()

    # ------------------------------------------------------------------ #

    @property
    def abaqus_exe(self) -> str:
        return self._abaqus_exe

    @abaqus_exe.setter
    def abaqus_exe(self, value: str) -> None:
        self._abaqus_exe = value

    @property
    def is_running(self) -> bool:
        return (
            self._process is not None
            and self._process.state() != QProcess.ProcessState.NotRunning
        )

    # ------------------------------------------------------------------ #

    def run(self, inp_path: Path, cpus: int, gpus: int) -> None:
        """
        Start an Abaqus job.  Working directory is set to inp_path.parent
        so all output files land in the job folder.
        """
        if self.is_running:
            self.output_received.emit("[AJM] A job is already running.\n")
            return

        job_stem = inp_path.stem
        args = [f"job={job_stem}", f"cpus={cpus}"]
        if gpus > 0:
            args.append(f"gpus={gpus}")
        args.append("interactive")

        self._process = QProcess(self)
        self._process.setWorkingDirectory(str(inp_path.parent))
        self._process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels
        )
        self._process.readyReadStandardOutput.connect(self._on_ready_read)
        self._process.finished.connect(self._on_finished)

        self.output_received.emit(
            f"[AJM] Starting: {self._abaqus_exe} {' '.join(args)}\n"
            f"[AJM] Working directory: {inp_path.parent}\n\n"
        )

        self._process.start(self._abaqus_exe, args)

        if not self._process.waitForStarted(5000):
            self.output_received.emit(
                f"[AJM] ERROR: Failed to start process. "
                f"Abaqus executable: '{self._abaqus_exe}'\n"
                f"[AJM] Check Settings > Abaqus Executable Path.\n"
            )
            self._process = None
            self.job_finished.emit(-1)
            return

        self.job_started.emit()

    def kill(self) -> None:
        """Terminate the running job and clean up lock files."""
        if self._process and self.is_running:
            working_dir = self._process.workingDirectory()
            self._process.kill()
            self.output_received.emit("\n[AJM] Job killed by user.\n")
            self._cleanup_lock_files(Path(working_dir))

    # ------------------------------------------------------------------ #

    def _on_ready_read(self) -> None:
        if self._process:
            raw = self._process.readAllStandardOutput()
            text = bytes(raw).decode("latin-1", errors="replace")
            self.output_received.emit(text)

    def _on_finished(self, exit_code: int, _exit_status) -> None:
        self.output_received.emit(f"\n[AJM] Process finished with exit code {exit_code}.\n")
        self.job_finished.emit(exit_code)

    @staticmethod
    def _cleanup_lock_files(folder: Path) -> None:
        """Remove Abaqus .lck files left behind after a killed job."""
        for lck in folder.glob("*.lck"):
            try:
                lck.unlink()
            except OSError:
                pass
