"""
Tests for JobScanner.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from app.core.scanner import JobScanner
from app.core.models import JobStatus


def _make_files(tmp_path: Path, names: list[str]) -> None:
    for name in names:
        (tmp_path / name).write_text("dummy", encoding="utf-8")


def test_basic_discovery(tmp_path):
    _make_files(tmp_path, [
        "410123_C03_M02_J01.inp",
        "410123_C03_M02_J01.sta",
        "410123_C03_M02_J01.dat",
        "410123_C03_M02_J01.msg",
    ])
    jobs = JobScanner(tmp_path).scan()
    assert len(jobs) == 1
    job = jobs[0]
    assert job.job_number == "410123"
    assert job.cae == 3
    assert job.model == 2
    assert job.job_local == 1
    assert job.inp_file is not None
    assert job.sta_file is not None
    assert job.dat_file is not None
    assert job.msg_file is not None


def test_multiple_jobs(tmp_path):
    _make_files(tmp_path, [
        "410123_C01_M01_J01.inp",
        "410123_C01_M01_J02.inp",
        "410123_C02_M01_J01.inp",
    ])
    jobs = JobScanner(tmp_path).scan()
    assert len(jobs) == 3


def test_nested_folders(tmp_path):
    sub = tmp_path / "subproject"
    sub.mkdir()
    _make_files(sub, ["500001_C01_M01_J01.inp"])
    _make_files(tmp_path, ["410123_C01_M01_J01.inp"])
    jobs = JobScanner(tmp_path).scan()
    assert len(jobs) == 2


def test_non_matching_files_ignored(tmp_path):
    _make_files(tmp_path, [
        "random_file.inp",
        "410123_C01_M01_J01.inp",
        "notes.txt",
    ])
    jobs = JobScanner(tmp_path).scan()
    assert len(jobs) == 1


def test_sorting(tmp_path):
    _make_files(tmp_path, [
        "410123_C03_M01_J01.inp",
        "410123_C01_M01_J01.inp",
        "410123_C02_M01_J01.inp",
    ])
    jobs = JobScanner(tmp_path).scan()
    caes = [j.cae for j in jobs]
    assert caes == sorted(caes)


def test_status_completed(tmp_path):
    (tmp_path / "410123_C01_M01_J01.inp").write_text("dummy")
    sta = tmp_path / "410123_C01_M01_J01.sta"
    sta.write_text("THE ANALYSIS HAS COMPLETED SUCCESSFULLY\n")
    jobs = JobScanner(tmp_path).scan()
    assert jobs[0].status == JobStatus.COMPLETED
