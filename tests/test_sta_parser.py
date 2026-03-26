"""
Tests for StaParser.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from app.core.sta_parser import StaParser

FIXTURE_STA = Path(__file__).parent / "fixtures" / "410123_C03_M02_J01.sta"


def test_parse_fixture():
    parser = StaParser(FIXTURE_STA)
    records = parser.parse()
    assert len(records) == 6
    assert records[0].increment == 1
    assert records[-1].increment == 6
    assert records[-1].step_time == pytest.approx(1.0, rel=1e-4)
    assert records[-1].total_time == pytest.approx(1.0, rel=1e-4)


def test_last_record():
    parser = StaParser(FIXTURE_STA)
    last = parser.last_record()
    assert last is not None
    assert last.increment == 6


def test_missing_file():
    parser = StaParser(Path("/nonexistent/file.sta"))
    records = parser.parse()
    assert records == []


def test_increments_monotonic():
    parser = StaParser(FIXTURE_STA)
    records = parser.parse()
    increments = [r.increment for r in records]
    assert increments == sorted(increments)


def test_total_time_increasing():
    parser = StaParser(FIXTURE_STA)
    records = parser.parse()
    times = [r.total_time for r in records]
    for a, b in zip(times, times[1:]):
        assert b >= a
