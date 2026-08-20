"""Autodetect repository metadata from git and common project manifests."""

from __future__ import annotations

import json
import re
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

GITHUB_REMOTE = re.compile(
    r"^(?:git@github\.com:|(?:https?|ssh)://(?:[\w.-]+@)?github\.com/)"
    r"(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
)

LICENSE_SIGNATURES: list[tuple[str, str]] = [
    ("MIT License", "MIT"),
    ("Apache License", "Apache-2.0"),
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
GO_MODULE = re.compile(r"^module\s+(\S+)", re.MULTILINE)
GRADLE_ROOT_NAME = re.compile(r"""rootProject\.name\s*=\s*['"]([^'"]+)['"]""")


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
    crate: str | None = None
    go_module: str | None = None
    nuget: str | None = None
    mod_id: str | None = None
    minecraft_version: str | None = None
    ha_min_version: str | None = None
    flow_plugin: str | None = None
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
            text = path.read_text(errors="replace").lower()
            for signature, spdx in LICENSE_SIGNATURES:
                if signature.lower() in text:
                    return spdx
    return None


def _license_field(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        text = value.get("text")
        return text if isinstance(text, str) and len(text) < 40 else None
    return None


def _set(meta: Metadata, **values: object) -> None:
    for key, value in values.items():
        if value:
            setattr(meta, key, value)


def _apply_pyproject(meta: Metadata, root: Path) -> bool:
    path = root / "pyproject.toml"
    if not path.is_file():
        return False
    project = tomllib.loads(path.read_text()).get("project", {})
    meta.project_type = "python"
    _set(
        meta,
        name=project.get("name"),
        pypi=project.get("name"),
        version=project.get("version"),
        tagline=project.get("description"),
        license=_license_field(project.get("license")),
        python_versions=[
            m.group(1) for c in project.get("classifiers", []) if (m := PYTHON_CLASSIFIER.search(c))
        ],
    )
    return True


def _apply_package_json(meta: Metadata, root: Path) -> bool:
    path = root / "package.json"
    if not path.is_file():
        return False
    data = json.loads(path.read_text())
    meta.project_type = "node"
    _set(
        meta,
        name=data.get("name"),
        npm=data.get("name"),
        version=data.get("version"),
        tagline=data.get("description"),
        license=_license_field(data.get("license")),
    )
    return True


def _apply_cargo(meta: Metadata, root: Path) -> bool:
    path = root / "Cargo.toml"
    if not path.is_file():
        return False
    package = tomllib.loads(path.read_text()).get("package", {})
    meta.project_type = "rust"
    _set(
        meta,
        name=package.get("name"),
        crate=package.get("name"),
        version=package.get("version"),
        tagline=package.get("description"),
        license=package.get("license"),
    )
    return True


def _apply_go(meta: Metadata, root: Path) -> bool:
    path = root / "go.mod"
    if not path.is_file():
        return False
    match = GO_MODULE.search(path.read_text())
    meta.project_type = "go"
    if match:
        module = match.group(1)
        _set(meta, go_module=module, name=module.rsplit("/", 1)[-1])
    return True


def _apply_dotnet(meta: Metadata, root: Path) -> bool:
    projects = sorted(root.glob("*.csproj")) or sorted(root.glob("*/*.csproj"))
    if not projects:
        return False
    path = projects[0]
    meta.project_type = "dotnet"
    try:
        tree = ElementTree.parse(path)
    except ElementTree.ParseError:
        _set(meta, name=path.stem)
        return True
    props = {el.tag: (el.text or "").strip() for pg in tree.iter("PropertyGroup") for el in pg}
    package_id = props.get("PackageId") or props.get("AssemblyName") or path.stem
    _set(
        meta,
        name=package_id,
        nuget=package_id if props.get("PackAsTool") or props.get("PackageId") else None,
        version=props.get("Version") or props.get("PackageVersion"),
        tagline=props.get("Description"),
        license=props.get("PackageLicenseExpression"),
    )
    return True


def _gradle_properties(root: Path) -> dict[str, str]:
    path = root / "gradle.properties"
    if not path.is_file():
        return {}
    props: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "!")) and "=" in line:
            key, value = line.split("=", 1)
            props[key.strip()] = value.strip()
    return props


def _apply_gradle(meta: Metadata, root: Path) -> bool:
    build = next(
        (root / n for n in ("build.gradle", "build.gradle.kts") if (root / n).is_file()), None
    )
    if build is None:
        return False
    props = _gradle_properties(root)
    if props.get("mod_id") or props.get("mod_name") or props.get("minecraft_version"):
        meta.project_type = "minecraft-mod"
        _set(
            meta,
            name=props.get("mod_name") or props.get("mod_id"),
            mod_id=props.get("mod_id"),
            version=props.get("mod_version") or props.get("version"),
            tagline=props.get("mod_description"),
            minecraft_version=props.get("minecraft_version"),
            license=props.get("mod_license"),
        )
        return True
    meta.project_type = "gradle"
    for settings in ("settings.gradle", "settings.gradle.kts"):
        path = root / settings
        if path.is_file() and (m := GRADLE_ROOT_NAME.search(path.read_text())):
            _set(meta, name=m.group(1))
    _set(meta, version=props.get("version"))
    return True


def _apply_hacs(meta: Metadata, root: Path) -> bool:
    path = root / "hacs.json"
    if not path.is_file():
        return False
    data = json.loads(path.read_text())
    _apply_package_json(meta, root)
    meta.project_type = "hacs"
    _set(meta, name=data.get("name"), ha_min_version=data.get("homeassistant"))
    return True


def _apply_flow_plugin(meta: Metadata, root: Path) -> bool:
    path = root / "plugin.json"
    if not path.is_file():
        return False
    data = json.loads(path.read_text())
    if "ActionKeyword" not in data and "ExecuteFileName" not in data:
        return False
    meta.project_type = "flow-plugin"
    _set(
        meta,
        name=data.get("Name"),
        flow_plugin=data.get("Name"),
        version=data.get("Version"),
        tagline=data.get("Description"),
    )
    return True


DETECTORS = (
    _apply_hacs,
    _apply_flow_plugin,
    _apply_pyproject,
    _apply_package_json,
    _apply_cargo,
    _apply_go,
    _apply_dotnet,
    _apply_gradle,
)


def detect(root: Path) -> Metadata:
    root = Path(root)
    meta = Metadata(name=root.resolve().name)
    remote = git_remote_url(root)
    if remote and (parsed := parse_github_remote(remote)):
        meta.owner, meta.repo = parsed
    for detector in DETECTORS:
        if detector(meta, root):
            break
    if not meta.license:
        meta.license = license_from_file(root)
    return meta
