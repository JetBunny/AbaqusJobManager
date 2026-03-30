"""
Live log tail widget — shows the last N lines of the .msg file,
auto-refreshing while a job is running.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.models import AbaqusJob

_TAIL_LINES   = 300
_POLL_INTERVAL_MS = 1000   # 1 second while running

# Keywords that get highlighted in the tail view
_WARN_KEYWORDS  = ("***WARNING", "WARNING")
_ERROR_KEYWORDS = ("***ERROR", "ERROR", "ANALYSIS TERMINATED")


def _read_tail(path: Path, n: int = _TAIL_LINES) -> str:
    """Return the last n lines of a file without loading it all."""
    try:
        with open(path, "r", encoding="latin-1", errors="replace") as f:
            lines = f.readlines()
        tail = lines[-n:] if len(lines) > n else lines
        skipped = len(lines) - len(tail)
        prefix = f"[... {skipped} earlier lines not shown ...]\n\n" if skipped else ""
        return prefix + "".join(tail)
    except OSError as e:
        return f"[Error reading file: {e}]"


class LogTailWidget(QWidget):
    """
    Shows a live-updating tail of the .msg file for the selected job.
    """

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self._current_job: Optional[AbaqusJob] = None
        self._is_monitoring = False
        self._last_size: int = -1

        self._timer = QTimer(self)
        self._timer.setInterval(_POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._poll)

        self._build_ui()

    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Header row
        hdr = QHBoxLayout()
        self._label = QLabel("No job selected")
        self._label.setStyleSheet("color: #888; font-size: 11px;")
        hdr.addWidget(self._label, stretch=1)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setFixedHeight(24)
        self._refresh_btn.clicked.connect(self._force_refresh)
        hdr.addWidget(self._refresh_btn)

        layout.addLayout(hdr)

        # Text area
        mono = QFont("Consolas", 9)
        mono.setStyleHint(QFont.StyleHint.Monospace)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(mono)
        self._log.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._log.setMaximumBlockCount(2000)
        layout.addWidget(self._log, stretch=1)

    # ------------------------------------------------------------------ #

    def set_job(self, job: Optional[AbaqusJob]) -> None:
        self._timer.stop()
        self._current_job = job
        self._last_size = -1
        self._is_monitoring = False

        if job is None:
            self._label.setText("No job selected")
            self._log.clear()
            return

        self._label.setText(f"MSG tail: {job.display_name}")
        self._force_refresh()

    def start_monitoring(self) -> None:
        """Begin live polling — called when a job starts running."""
        self._is_monitoring = True
        self._last_size = -1
        if not self._timer.isActive():
            self._timer.start()

    def on_job_finished(self) -> None:
        """Stop polling and do a final read."""
        self._timer.stop()
        self._is_monitoring = False
        self._force_refresh()

    # ------------------------------------------------------------------ #

    def _poll(self) -> None:
        if self._current_job is None:
            return

        msg_path = self._current_job.msg_file
        if not msg_path:
            # .msg might not be set at job creation time — try to find it
            candidate = self._current_job.folder / f"{self._current_job.stem}.msg"
            if candidate.exists():
                self._current_job.msg_file = candidate
                msg_path = candidate
            else:
                return

        try:
            current_size = msg_path.stat().st_size
        except OSError:
            return

        if current_size != self._last_size:
            self._last_size = current_size
            self._reload(msg_path)

    def _force_refresh(self) -> None:
        self._last_size = -1
        if self._current_job is None:
            return
        msg_path = self._current_job.msg_file
        if not msg_path:
            candidate = self._current_job.folder / f"{self._current_job.stem}.msg"
            if candidate.exists():
                self._current_job.msg_file = candidate
                msg_path = candidate
        if msg_path and msg_path.exists():
            self._reload(msg_path)
        else:
            self._log.setPlainText(
                "No .msg file found yet.\n"
                "It will appear once the job starts writing output."
            )

    def _reload(self, path: Path) -> None:
        text = _read_tail(path)
        self._log.setPlainText(text)
        # Scroll to bottom
        self._log.moveCursor(QTextCursor.MoveOperation.End)
        self._highlight_keywords()

    def _highlight_keywords(self) -> None:
        """Colour-highlight WARNING and ERROR lines after loading."""
        doc = self._log.document()

        warn_fmt = QTextCharFormat()
        warn_fmt.setForeground(QColor("#FFC107"))   # amber

        error_fmt = QTextCharFormat()
        error_fmt.setForeground(QColor("#F44336"))  # red
        error_fmt.setFontWeight(700)

        block = doc.begin()
        while block.isValid():
            text_upper = block.text().upper()
            fmt = None
            if any(kw in text_upper for kw in _ERROR_KEYWORDS):
                fmt = error_fmt
            elif any(kw in text_upper for kw in _WARN_KEYWORDS):
                fmt = warn_fmt

            if fmt:
                cursor = QTextCursor(block)
                cursor.select(QTextCursor.SelectionType.LineUnderCursor)
                cursor.setCharFormat(fmt)

            block = block.next()
