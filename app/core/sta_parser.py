"""
Parser for Abaqus .sta (status) files.

Handles both implicit (standard) and explicit (dynamic/explicit) layouts.
The column layout is detected from the header rather than hardcoded.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class StaRecord:
    step: int
    increment: int
    total_time: float
    step_time: float
    fraction_complete: Optional[float] = None  # 0–1 if determinable


class StaParser:
    """Parse an Abaqus .sta file into a list of StaRecord objects."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._records: Optional[List[StaRecord]] = None

    # ------------------------------------------------------------------ #

    def parse(self) -> List[StaRecord]:
        """Return parsed records, re-reading the file each call."""
        self._records = []
        try:
            text = self.path.read_text(encoding="latin-1", errors="replace")
        except OSError:
            return []

        lines = text.splitlines()
        col_map = self._detect_columns(lines)
        if col_map is None:
            return []

        data_started = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Data rows start with an integer (STEP number)
            parts = stripped.split()
            if not parts:
                continue

            if not data_started:
                if parts[0].isdigit():
                    data_started = True
                else:
                    continue

            # Skip header / separator lines that sneak in
            if not parts[0].isdigit():
                continue

            try:
                rec = self._parse_row(parts, col_map)
                if rec is not None:
                    self._records.append(rec)
            except (IndexError, ValueError):
                continue

        return self._records

    # ------------------------------------------------------------------ #

    @staticmethod
    def _detect_columns(lines: List[str]) -> Optional[dict]:
        """
        Find the header line and build a column-name -> index map.

        Abaqus uses multi-word column headers like "STEP TIME" and "TOTAL TIME".
        We normalise these to single tokens (STEP_TIME, TOTAL_TIME) before
        indexing so they don't collide with the single-word STEP / TIME tokens.
        Returns None if no header found.
        """
        header_keywords = {"STEP", "INCREMENT", "TIME"}
        for line in lines:
            upper = line.upper()
            if all(kw in upper for kw in header_keywords):
                # Normalise multi-word column names first
                normalised = (
                    upper
                    .replace("TOTAL TIME", "TOTAL_TIME")
                    .replace("STEP TIME",  "STEP_TIME")
                )
                tokens = normalised.split()
                col_map: dict[str, int] = {}
                for i, tok in enumerate(tokens):
                    # Don't overwrite earlier (leftmost) occurrence
                    if tok not in col_map:
                        col_map[tok] = i
                return col_map
        return None

    @staticmethod
    def _parse_row(parts: List[str], col_map: dict) -> Optional[StaRecord]:
        """Extract a StaRecord from a data row."""
        step_idx = col_map.get("STEP", 0)
        inc_idx  = col_map.get("INCREMENT", 1)

        # Prefer the normalised multi-word names; fall back to single-word
        total_idx = col_map.get("TOTAL_TIME") or col_map.get("TOTAL")
        if total_idx is None:
            total_idx = len(parts) - 1

        time_idx = col_map.get("STEP_TIME")
        if time_idx is None:
            time_idx = max(0, total_idx - 1)

        if total_idx >= len(parts) or time_idx >= len(parts):
            return None

        return StaRecord(
            step=int(parts[step_idx]),
            increment=int(parts[inc_idx]),
            step_time=float(parts[time_idx]),
            total_time=float(parts[total_idx]),
        )

    # ------------------------------------------------------------------ #

    def last_record(self) -> Optional[StaRecord]:
        records = self.parse()
        return records[-1] if records else None
