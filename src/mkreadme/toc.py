"""Table-of-contents generation from rendered markdown headings."""

from __future__ import annotations

import re
from collections import Counter

TOC_PREFIX = "<!-- mkreadme:toc"
TOC_TOKEN = f"{TOC_PREFIX} -->"
TOC_ANY = re.compile(r"<!-- mkreadme:toc(?: (?P<min>\d) (?P<max>\d))? -->")
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
SLUG_STRIP = re.compile(r"[^\w\- ]", re.UNICODE)


def toc_token(min_level: int = 2, max_level: int = 3) -> str:
    return f"{TOC_PREFIX} {min_level} {max_level} -->"


def github_slug(title: str) -> str:
    cleaned = SLUG_STRIP.sub("", title.strip().lower())
    return cleaned.replace(" ", "-")


def _headings(markdown: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    in_fence = False
    for line in markdown.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if match := HEADING.match(line):
            found.append((len(match.group(1)), match.group(2).strip()))
    return found


def build_toc(markdown: str, min_level: int = 2, max_level: int = 3) -> str:
    seen: Counter[str] = Counter()
    lines = []
    for level, title in _headings(markdown):
        if not min_level <= level <= max_level:
            continue
        slug = github_slug(title)
        count = seen[slug]
        seen[slug] += 1
        anchor = f"{slug}-{count}" if count else slug
        lines.append(f"{'  ' * (level - min_level)}- [{title}](#{anchor})")
    return "\n".join(lines)


def insert_toc(markdown: str) -> str:
    match = TOC_ANY.search(markdown)
    if not match:
        return markdown
    min_level = int(match["min"]) if match["min"] else 2
    max_level = int(match["max"]) if match["max"] else 3
    before, after = markdown[: match.start()], markdown[match.end() :]
    return before + build_toc(after, min_level, max_level) + after
