"""Read the newest entries from a Keep-a-Changelog style CHANGELOG.md."""

from __future__ import annotations

import re
from pathlib import Path

ENTRY_HEADING = re.compile(r"^##\s+")
CANDIDATES = ("CHANGELOG.md", "CHANGES.md", "HISTORY.md", "changelog.md")


def find_changelog(root: Path) -> Path | None:
    return next((root / name for name in CANDIDATES if (root / name).is_file()), None)


def split_entries(text: str) -> list[str]:
    entries: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if ENTRY_HEADING.match(line):
            if current:
                entries.append("\n".join(current).strip())
            current = [line]
        elif current:
            current.append(line)
    if current:
        entries.append("\n".join(current).strip())
    return [e for e in entries if not e.lower().startswith("## [unreleased]")]


def latest_entries(root: Path, n: int = 1, path: str | None = None) -> str:
    file = root / path if path else find_changelog(root)
    if file is None or not file.is_file():
        return ""
    return "\n\n".join(split_entries(file.read_text())[:n])
