"""Table-of-contents generation from rendered markdown headings."""

from __future__ import annotations

import re
from collections import Counter

TOC_TOKEN = "<!-- mkreadme:toc -->"
HEADING = re.compile(r"^(#{2,3})\s+(.+?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
SLUG_STRIP = re.compile(r"[^\w\- ]", re.UNICODE)


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


def build_toc(markdown: str) -> str:
    seen: Counter[str] = Counter()
    lines = []
    for level, title in _headings(markdown):
        slug = github_slug(title)
        count = seen[slug]
        seen[slug] += 1
        anchor = f"{slug}-{count}" if count else slug
        lines.append(f"{'  ' * (level - 2)}- [{title}](#{anchor})")
    return "\n".join(lines)


def insert_toc(markdown: str) -> str:
    if TOC_TOKEN not in markdown:
        return markdown
    before, after = markdown.split(TOC_TOKEN, 1)
    return before + build_toc(after) + after
