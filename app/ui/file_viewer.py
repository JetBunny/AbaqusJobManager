"""
Tabbed file viewer for .inp, .sta, .dat, .msg files.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
)
from PyQt6.QtWidgets import (
    QLabel,
    QPlainTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.models import AbaqusJob

_HEAD_LINES = 500
_TAIL_LINES = 500
_MAX_LINES  = _HEAD_LINES + _TAIL_LINES


def read_file_preview(path: Path, head: int = _HEAD_LINES, tail: int = _TAIL_LINES) -> str:
    """
    Read up to head+tail lines from a file without loading it entirely.
    For large files a banner is inserted between head and tail.
    """
    try:
        with open(path, "r", encoding="latin-1", errors="replace") as f:
            all_lines = f.readlines()

        total = len(all_lines)
        if total <= head + tail:
            return "".join(all_lines)

        head_text = "".join(all_lines[:head])
        tail_text = "".join(all_lines[-tail:])
        banner = (
            f"\n{'─' * 60}\n"
            f"  [ File truncated — showing first {head} and last {tail} of {total} lines ]\n"
            f"{'─' * 60}\n\n"
        )
        return head_text + banner + tail_text

    except OSError as e:
        return f"[Error reading file: {e}]"


# ─────────────────────────────────────────────────────────────────────────────
# Syntax highlighter for .inp files
# ─────────────────────────────────────────────────────────────────────────────

class InpHighlighter(QSyntaxHighlighter):
    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)

        self._comment_fmt = QTextCharFormat()
        self._comment_fmt.setForeground(QColor("#6A9955"))  # muted green

        self._keyword_fmt = QTextCharFormat()
        self._keyword_fmt.setForeground(QColor("#CE9178"))  # orange/gold
        self._keyword_fmt.setFontWeight(700)

        self._number_fmt = QTextCharFormat()
        self._number_fmt.setForeground(QColor("#9CDCFE"))   # light blue

    def highlightBlock(self, text: str) -> None:
        stripped = text.lstrip()

        # Full-line comments (**) take priority
        if stripped.startswith("**"):
            self.setFormat(0, len(text), self._comment_fmt)
            return

        # Keywords: lines starting with * (but not **)
        if stripped.startswith("*"):
            # Highlight up to the first comma or end of line as keyword
            star_pos = text.index("*")
            end = len(text)
            comma = text.find(",", star_pos)
            if comma != -1:
                end = comma
            self.setFormat(star_pos, end - star_pos, self._keyword_fmt)

        # Numbers anywhere in the line
        import re
        for m in re.finditer(r'\b\d+(\.\d+)?([eE][+-]?\d+)?\b', text):
            self.setFormat(m.start(), m.end() - m.start(), self._number_fmt)


# ─────────────────────────────────────────────────────────────────────────────
# Widget
# ─────────────────────────────────────────────────────────────────────────────

class FileViewerWidget(QWidget):
    """
    Tabbed view with one tab per file type.
    Files are loaded lazily when the tab is first activated.
    """

    _TAB_DEFS = [
        ("INP", "inp_file"),
        ("STA", "sta_file"),
        ("DAT", "dat_file"),
        ("MSG", "msg_file"),
    ]

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self._current_job: Optional[AbaqusJob] = None
        self._loaded: dict[int, bool] = {}  # tab_index -> loaded?
        self._highlighter: Optional[InpHighlighter] = None

        self._build_ui()

    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._header = QLabel("No job selected")
        self._header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._header.setStyleSheet("color: #888; padding: 4px;")
        layout.addWidget(self._header)

        self._tabs = QTabWidget()
        self._editors: list[QPlainTextEdit] = []

        mono = QFont("Consolas", 9)
        mono.setStyleHint(QFont.StyleHint.Monospace)

        for label, _ in self._TAB_DEFS:
            editor = QPlainTextEdit()
            editor.setReadOnly(True)
            editor.setFont(mono)
            editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            editor.setPlaceholderText(f"No {label} file for this job.")
            self._editors.append(editor)
            self._tabs.addTab(editor, label)

        self._tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self._tabs)

    # ------------------------------------------------------------------ #

    def set_job(self, job: Optional[AbaqusJob]) -> None:
        self._current_job = job
        self._loaded = {}

        if job is None:
            self._header.setText("No job selected")
            for editor in self._editors:
                editor.clear()
            return

        self._header.setText(f"  {job.display_name}  —  {job.folder}")
        for editor in self._editors:
            editor.clear()

        # Load the currently active tab immediately
        self._load_tab(self._tabs.currentIndex())

    def reload_current(self) -> None:
        """Force-reload the active tab (e.g. while job is running)."""
        idx = self._tabs.currentIndex()
        self._loaded.pop(idx, None)
        self._load_tab(idx)

    # ------------------------------------------------------------------ #

    def _on_tab_changed(self, index: int) -> None:
        if self._current_job is not None and not self._loaded.get(index, False):
            self._load_tab(index)

    def _load_tab(self, index: int) -> None:
        if self._current_job is None:
            return

        _, attr = self._TAB_DEFS[index]
        file_path: Optional[Path] = getattr(self._current_job, attr, None)

        editor = self._editors[index]

        # Remove old highlighter
        if index == 0 and self._highlighter:
            self._highlighter.setDocument(None)
            self._highlighter = None

        if not file_path or not file_path.exists():
            editor.setPlainText(
                f"File not found: {file_path.name if file_path else 'N/A'}"
            )
            self._loaded[index] = True
            return

        text = read_file_preview(file_path)
        editor.setPlainText(text)

        # Attach syntax highlighter to INP tab
        if index == 0:
            self._highlighter = InpHighlighter(editor.document())

        self._loaded[index] = True
