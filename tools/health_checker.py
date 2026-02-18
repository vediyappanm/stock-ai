"""System health checks for API readiness."""

from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from config.settings import settings


def _dependency_status() -> Dict[str, bool]:
    deps = {
        "yfinance": "yfinance",
        "ta": "ta",
        "sklearn": "sklearn",
        "torch": "torch",
    }
    return {name: importlib.util.find_spec(module) is not None for name, module in deps.items()}


def _directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for file in path.rglob("*"):
        if file.is_file():
            total += file.stat().st_size
    return total


def get_health_status() -> Dict[str, object]:
    dep = _dependency_status()
    all_ok = all(dep.values())

    cache_dir = Path(settings.cache_dir)
    models_dir = Path(settings.models_dir)
    model_files = list(models_dir.glob("*")) if models_dir.exists() else []

    return {
        "status": "healthy" if all_ok else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": dep,
        "cache": {
            "path": str(cache_dir),
            "size_bytes": _directory_size(cache_dir),
        },
        "models": {
            "path": str(models_dir),
            "artifact_count": len([f for f in model_files if f.is_file()]),
        },
        "disclaimer": settings.disclaimer,
    }
