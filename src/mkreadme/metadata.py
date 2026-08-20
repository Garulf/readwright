"""Autodetect repository metadata from git, pyproject.toml, package.json and LICENSE."""

from __future__ import annotations

import json
import re
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

GITHUB_REMOTE = re.compile(
    r"^(?:git@github\.com:|(?:https?|ssh)://(?:[\w.-]+@)?github\.com/)(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
)

LICENSE_SIGNATURES: list[tuple[str, str]] = [
    ("MIT License", "MIT"),
    ("Apache License", "Apache-2.0"),
    ("GNU GENERAL PUBLIC LICENSE\n                       Version 3", "GPL-3.0"),
    ("GNU General Public License", "GPL-3.0"),
    ("GNU LESSER GENERAL PUBLIC LICENSE", "LGPL-3.0"),
    ("GNU AFFERO GENERAL PUBLIC LICENSE", "AGPL-3.0"),
    ("BSD 3-Clause", "BSD-3-Clause"),
    ("BSD 2-Clause", "BSD-2-Clause"),
    ("Mozilla Public License", "MPL-2.0"),
    ("ISC License", "ISC"),
    ("The Unlicense", "Unlicense"),
]

PYTHON_CLASSIFIER = re.compile(r"Programming Language :: Python :: (\d+\.\d+)$")


@dataclass
class Metadata:
    name: str | None = None
    owner: str | None = None
    repo: str | None = None
    tagline: str | None = None
    version: str | None = None
    license: str | None = None
    pypi: str | None = None
    npm: str | None = None
    python_versions: list[str] = field(default_factory=list)
    project_type: str = "generic"

    @property
    def url(self) -> str | None:
        if self.owner and self.repo:
            return f"https://github.com/{self.owner}/{self.repo}"
        return None


def parse_github_remote(url: str) -> tuple[str, str] | None:
    match = GITHUB_REMOTE.match(url.strip())
    if not match:
        return None
    return match["owner"], match["repo"]


def git_remote_url(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    return result.stdout.strip() or None


def license_from_file(root: Path) -> str | None:
    for candidate in ("LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE", "COPYING"):
        path = root / candidate
        if path.is_file():
            text = path.read_text(errors="replace")
            for signature, spdx in LICENSE_SIGNATURES:
                if signature.lower() in text.lower():
                    return spdx
    return None


def _license_field(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        text = value.get("text")
        return text if isinstance(text, str) and len(text) < 40 else None
    return None


def _apply_pyproject(meta: Metadata, root: Path) -> bool:
    path = root / "pyproject.toml"
    if not path.is_file():
        return False
    data = tomllib.loads(path.read_text())
    project = data.get("project", {})
    meta.project_type = "python"
    meta.name = project.get("name") or meta.name
    meta.pypi = project.get("name")
    meta.version = project.get("version")
    meta.tagline = project.get("description")
    meta.license = _license_field(project.get("license"))
    meta.python_versions = [
        m.group(1) for c in project.get("classifiers", []) if (m := PYTHON_CLASSIFIER.search(c))
    ]
    return True


def _apply_package_json(meta: Metadata, root: Path) -> bool:
    path = root / "package.json"
    if not path.is_file():
        return False
    data = json.loads(path.read_text())
    meta.project_type = "node"
    meta.name = data.get("name") or meta.name
    meta.npm = data.get("name")
    meta.version = data.get("version")
    meta.tagline = data.get("description")
    meta.license = _license_field(data.get("license"))
    return True


def detect(root: Path) -> Metadata:
    root = Path(root)
    meta = Metadata(name=root.resolve().name)
    remote = git_remote_url(root)
    if remote and (parsed := parse_github_remote(remote)):
        meta.owner, meta.repo = parsed
    _apply_pyproject(meta, root) or _apply_package_json(meta, root)
    if not meta.license:
        meta.license = license_from_file(root)
    return meta
