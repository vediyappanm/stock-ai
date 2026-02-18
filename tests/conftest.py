"""Pytest configuration for local sandbox-friendly temp paths."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


_TMP = Path(".tmp").resolve()
_TMP.mkdir(parents=True, exist_ok=True)
os.environ["TMPDIR"] = str(_TMP)
os.environ["TEMP"] = str(_TMP)
os.environ["TMP"] = str(_TMP)
tempfile.tempdir = str(_TMP)


def pytest_configure() -> None:
    # Keep explicit hook for clarity; module-level setup above applies first.
    tempfile.tempdir = str(_TMP)
