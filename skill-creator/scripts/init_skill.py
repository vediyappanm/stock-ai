"""Create a minimal skill folder with SKILL.md."""

from __future__ import annotations

from pathlib import Path
import sys


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python skill-creator/scripts/init_skill.py <skill-name>")
    name = sys.argv[1].strip()
    root = Path(name)
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text(f"# {name}\n\nDescribe this skill here.\n", encoding="utf-8")
    (root / "scripts").mkdir(exist_ok=True)
    (root / "references").mkdir(exist_ok=True)
    print(f"Initialized skill at {root}")


if __name__ == "__main__":
    main()

