"""
Recursive folder scanner that discovers Abaqus job files.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from app.core.models import AbaqusJob, parse_job_name

# File extensions we care about
RELEVANT_EXTENSIONS = {".cae", ".sta", ".inp", ".dat", ".msg"}


class JobScanner:
    """
    Scans a root directory (recursively) for Abaqus job files and
    returns a list of AbaqusJob objects, one per unique job identity.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def scan(self) -> List[AbaqusJob]:
        """Walk the tree, group files by job identity, return sorted list."""
        # Key: (job_number, cae, model, job_local, folder_path)
        groups: dict[tuple, dict] = {}

        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in RELEVANT_EXTENSIONS:
                continue

            parsed = parse_job_name(path.stem)
            if parsed is None:
                continue

            key = (
                parsed["job_number"],
                parsed["cae"],
                parsed["model"],
                parsed["job_local"],
                path.parent,
            )

            if key not in groups:
                groups[key] = {
                    "job_number": parsed["job_number"],
                    "cae":        parsed["cae"],
                    "model":      parsed["model"],
                    "job_local":  parsed["job_local"],
                    "folder":     path.parent,
                    "inp_file":   None,
                    "cae_file":   None,
                    "sta_file":   None,
                    "dat_file":   None,
                    "msg_file":   None,
                }

            ext = path.suffix.lower()
            if ext == ".inp":
                groups[key]["inp_file"] = path
            elif ext == ".cae":
                groups[key]["cae_file"] = path
            elif ext == ".sta":
                groups[key]["sta_file"] = path
            elif ext == ".dat":
                groups[key]["dat_file"] = path
            elif ext == ".msg":
                groups[key]["msg_file"] = path

        jobs = []
        for data in groups.values():
            job = AbaqusJob(**data)
            job.refresh_status()
            jobs.append(job)

        jobs.sort(key=lambda j: j.sort_key())
        return jobs
