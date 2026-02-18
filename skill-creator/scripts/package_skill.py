"""Create a zip archive for a skill folder."""

from __future__ import annotations

from pathlib import Path
import shutil
import sys


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python skill-creator/scripts/package_skill.py <skill-dir>")
    skill_dir = Path(sys.argv[1]).resolve()
    if not skill_dir.exists():
        raise SystemExit(f"Skill directory not found: {skill_dir}")
    output = skill_dir.parent / f"{skill_dir.name}.zip"
    shutil.make_archive(str(output.with_suffix("")), "zip", root_dir=str(skill_dir))
    print(f"Packaged: {output}")


if __name__ == "__main__":
    main()

