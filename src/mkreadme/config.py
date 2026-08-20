"""Configuration models and loading (readme.yaml, [tool.readme], user-level config)."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from mkreadme.metadata import detect

DEFAULT_CONFIG_NAME = "readme.yaml"
DEFAULT_TEMPLATE = "README.md.j2"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectInfo(StrictModel):
    name: str | None = None
    owner: str | None = None
    repo: str | None = None
    tagline: str | None = None
    version: str | None = None
    pypi: str | None = None
    npm: str | None = None
    crate: str | None = None
    go_module: str | None = None
    nuget: str | None = None
    mod_id: str | None = None
    minecraft_version: str | None = None
    modrinth: str | None = None
    curseforge: str | None = None
    ha_min_version: str | None = None
    flow_plugin: str | None = None
    license: str | None = None
    ci_workflow: str | None = None
    python_versions: list[str] = Field(default_factory=list)
    project_type: str = "generic"

    @property
    def url(self) -> str | None:
        if self.owner and self.repo:
            return f"https://github.com/{self.owner}/{self.repo}"
        return None


class ScreenshotsConfig(StrictModel):
    dir: str = "docs/screenshots"
    width: int | None = 720
    style: Literal["markdown", "html"] = "markdown"


class BadgeSpec(StrictModel):
    preset: str
    options: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def coerce(cls, value: Any) -> Any:
        if isinstance(value, str):
            return {"preset": value}
        if isinstance(value, dict) and "options" not in value:
            value = dict(value)
            preset = value.pop("preset")
            return {"preset": preset, "options": value}
        return value


class CustomBadge(StrictModel):
    label: str
    message: str
    color: str = "blue"
    link: str | None = None
    logo: str | None = None
    style: str | None = None


class RelatedRepo(StrictModel):
    repo: str
    description: str = ""
    url: str | None = None


class Config(StrictModel):
    template: str = DEFAULT_TEMPLATE
    templates: list[str] = Field(default_factory=list)
    output: str = "README.md"
    strict: bool = False
    allow_exec: bool = False
    badges_style: str | None = None
    related: list[RelatedRepo] = Field(default_factory=list)
    screenshots: ScreenshotsConfig = Field(default_factory=ScreenshotsConfig)
    badges: list[BadgeSpec] = Field(default_factory=list)
    badges_custom: dict[str, CustomBadge] = Field(default_factory=dict)
    donate: list[str] = Field(default_factory=list)
    donate_handles: dict[str, str | None] = Field(default_factory=dict)
    project: ProjectInfo = Field(default_factory=ProjectInfo)
    vars: dict[str, Any] = Field(default_factory=dict)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _validate(data: dict[str, Any], source: str) -> Config:
    try:
        return Config.model_validate(data)
    except Exception as exc:
        raise ValueError(f"invalid config in {source}: {exc}") from exc


def _read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError(f"invalid config in {path}: expected a mapping")
    return data


def _read_tool_readme(root: Path) -> dict[str, Any] | None:
    path = root / "pyproject.toml"
    if not path.is_file():
        return None
    data = tomllib.loads(path.read_text())
    section = data.get("tool", {}).get("readme")
    return dict(section) if isinstance(section, dict) else None


def find_config_path(root: Path) -> Path | None:
    path = root / DEFAULT_CONFIG_NAME
    return path if path.is_file() else None


def config_sources(root: Path) -> list[str]:
    found = []
    if find_config_path(root) is not None:
        found.append(DEFAULT_CONFIG_NAME)
    if _read_tool_readme(root) is not None:
        found.append("pyproject.toml [tool.readme]")
    return found


def load_config_data(root: Path, config_path: Path | None = None) -> tuple[dict[str, Any], str]:
    if config_path is not None:
        return _read_yaml(config_path), str(config_path)
    if (path := find_config_path(root)) is not None:
        return _read_yaml(path), str(path)
    if (section := _read_tool_readme(root)) is not None:
        return section, str(root / "pyproject.toml [tool.readme]")
    return {}, "<defaults>"


def load_config(root: Path, config_path: Path | None = None) -> Config:
    data, source = load_config_data(root, config_path)
    return _validate(data, source)


def user_config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "mkreadme" / "config.yaml"


def user_templates_dir() -> Path:
    return user_config_path().parent / "templates"


def load_user_config() -> Config | None:
    path = user_config_path()
    if not path.is_file():
        return None
    return _validate(_read_yaml(path), str(path))


def _dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(exclude_defaults=True, exclude_none=True)


def resolve(
    root: Path,
    config_path: Path | None = None,
    use_user_config: bool = False,
) -> Config:
    detected = detect(root)
    layers: list[dict[str, Any]] = [{"project": _dump(ProjectInfo(**detected.__dict__))}]
    if use_user_config and (user := load_user_config()) is not None:
        layers.append(_dump(user))
    repo_data, source = load_config_data(root, config_path)
    _validate(repo_data, source)
    layers.append(repo_data)
    merged: dict[str, Any] = {}
    for layer in layers:
        merged = deep_merge(merged, layer)
    return _validate(merged, source)
