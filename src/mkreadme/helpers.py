"""Miscellaneous template helpers: file inclusion, layout, links, project-specific bits."""

from __future__ import annotations

import html
import json
import os
import re
import shlex
import subprocess
import textwrap
import tomllib
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import yaml

from mkreadme.config import Config

LOGO_DIRS = ("", "docs", "assets", "docs/assets", "docs/images", "img", "images")
LOGO_EXTENSIONS = ("svg", "png", "webp", "jpg")
VIDEO_EXTENSIONS = ("mp4", "webm", "mov", "gif")
MODS_TOML_PATHS = (
    "src/main/resources/META-INF/neoforge.mods.toml",
    "src/main/resources/META-INF/mods.toml",
    "src/main/templates/META-INF/neoforge.mods.toml",
)
SPDX_URLS = "https://spdx.org/licenses/{id}.html"
MY_HA = "https://my.home-assistant.io"


def fenced(text: str, language: str = "") -> str:
    fence = "````" if "```" in text else "```"
    return f"{fence}{language}\n{text.rstrip()}\n{fence}"


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return ""
    escape = lambda s: str(s).replace("|", "\\|").replace("\n", " ")  # noqa: E731
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines += ["| " + " | ".join(escape(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def flatten(data: Any, prefix: str = "") -> list[tuple[str, str]]:
    if isinstance(data, dict):
        items: list[tuple[str, str]] = []
        for key, value in data.items():
            items += flatten(value, f"{prefix}{key}.")
        return items
    return [(prefix.rstrip("."), _scalar(data))]


def _scalar(value: Any) -> str:
    if isinstance(value, list | tuple):
        return ", ".join(_scalar(v) for v in value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return f"`{value}`"


class Helpers:
    def __init__(self, root: Path, config: Config, warn: Callable[[str], None] | None = None):
        self.root = Path(root)
        self.config = config
        self.warn = warn or (lambda message: None)

    # ---------------------------------------------------------------- files
    def _path(self, path: str) -> Path:
        return self.root / path

    def include_file(self, path: str) -> str:
        target = self._path(path)
        if not target.is_file():
            self.warn(f"include_file: '{path}' not found")
            return ""
        return target.read_text().rstrip("\n")

    def code_block(self, path: str, language: str | None = None) -> str:
        content = self.include_file(path)
        if not content:
            return ""
        lang = language if language is not None else self._path(path).suffix.lstrip(".")
        return fenced(content, lang)

    def snippet(
        self,
        path: str,
        start: str,
        end: str,
        language: str | None = None,
        dedent: bool = True,
    ) -> str:
        content = self.include_file(path)
        if not content:
            return ""
        lines = content.splitlines()
        try:
            first = next(i for i, line in enumerate(lines) if start in line) + 1
            last = next(i for i, line in enumerate(lines) if end in line and i >= first)
        except StopIteration:
            self.warn(f"snippet: markers '{start}'..'{end}' not found in {path}")
            return ""
        body = "\n".join(lines[first:last])
        if dedent:
            body = textwrap.dedent(body)
        if language is None:
            language = self._path(path).suffix.lstrip(".")
        return fenced(body, language) if language else body

    def cli_help(self, command: str, language: str = "text", strip_ansi: bool = True) -> str:
        if not self.config.allow_exec:
            raise PermissionError(
                f"cli_help({command!r}) needs `allow_exec: true` in readme.yaml "
                "(it runs the command during render)"
            )
        env = {**os.environ, "NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "80"}
        result = subprocess.run(
            shlex.split(command), capture_output=True, text=True, cwd=self.root, env=env
        )
        output = result.stdout or result.stderr
        if strip_ansi:
            output = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", output)
        return fenced(output, language)

    # --------------------------------------------------------------- tables
    def _load_data(self, path: str) -> Any:
        target = self._path(path)
        if not target.is_file():
            self.warn(f"'{path}' not found")
            return None
        suffix = target.suffix.lower()
        text = target.read_text()
        if suffix == ".toml":
            return tomllib.loads(text)
        if suffix == ".json":
            return json.loads(text)
        return yaml.safe_load(text)

    def config_table(
        self,
        path: str,
        section: str | None = None,
        headers: tuple[str, str] = ("Key", "Value"),
    ) -> str:
        data = self._load_data(path)
        if data is None:
            return ""
        for part in (section or "").split("."):
            if part:
                data = data.get(part, {}) if isinstance(data, dict) else {}
        if not isinstance(data, dict):
            self.warn(f"config_table: {path} section '{section}' is not a mapping")
            return ""
        return md_table(list(headers), [[k, v] for k, v in flatten(data)])

    def env_table(self, path: str = ".env.example") -> str:
        target = self._path(path)
        if not target.is_file():
            self.warn(f"env_table: '{path}' not found")
            return ""
        rows: list[list[str]] = []
        description: list[str] = []
        for raw in target.read_text().splitlines():
            line = raw.strip()
            if line.startswith("#"):
                description.append(line.lstrip("# ").strip())
            elif "=" in line:
                key, _, value = line.partition("=")
                rows.append(
                    [
                        f"`{key.strip()}`",
                        f"`{value.strip()}`" if value.strip() else "",
                        " ".join(description),
                    ]
                )
                description = []
            else:
                description = []
        return md_table(["Variable", "Default", "Description"], rows)

    # ---------------------------------------------------------------- links
    def gh_link(self, path: str = "", text: str | None = None) -> str:
        base = self.config.project.url
        if not base:
            raise ValueError("gh_link needs project.owner and project.repo")
        url = f"{base}/{path.lstrip('/')}" if path else base
        return f"[{text}]({url})" if text else url

    def spdx_link(self, license_id: str | None = None) -> str:
        spdx = license_id or self.config.project.license
        if not spdx:
            return ""
        return f"[{spdx}]({SPDX_URLS.format(id=spdx)})"

    def my_ha_link(self, redirect: str, text: str | None = None, **params: str) -> str:
        url = f"{MY_HA}/redirect/{redirect}/"
        if params:
            url += "?" + urlencode(params)
        if text:
            return f"[{text}]({url})"
        return f"[![Open your Home Assistant instance]({MY_HA}/badges/{redirect}.svg)]({url})"

    # --------------------------------------------------------------- layout
    @staticmethod
    def details(summary: str, body: str, open: bool = False) -> str:
        attr = " open" if open else ""
        return f"<details{attr}>\n<summary>{summary}</summary>\n\n{body.strip()}\n\n</details>"

    @staticmethod
    def callout(kind: str, text: str) -> str:
        kinds = {"note", "tip", "important", "warning", "caution"}
        if kind.lower() not in kinds:
            raise ValueError(f"callout kind must be one of {sorted(kinds)}")
        body = "\n".join(f"> {line}" if line else ">" for line in text.strip().splitlines())
        return f"> [!{kind.upper()}]\n{body}"

    @staticmethod
    def center(content: str) -> str:
        return f'<p align="center">\n{content.strip()}\n</p>'

    @staticmethod
    def columns(cells: list[str], align: str = "center") -> str:
        row = "\n".join(f'<td align="{align}">\n\n{c.strip()}\n\n</td>' for c in cells)
        return f"<table>\n<tr>\n{row}\n</tr>\n</table>"

    def _find_asset(self, stem: str, extensions: tuple[str, ...]) -> Path | None:
        for directory in LOGO_DIRS:
            for ext in extensions:
                candidate = self.root / directory / f"{stem}.{ext}"
                if candidate.is_file():
                    return candidate
        shots = self.root / self.config.screenshots.dir
        for ext in extensions:
            if (shots / f"{stem}.{ext}").is_file():
                return shots / f"{stem}.{ext}"
        return None

    def logo(self, width: int | None = 120, alt: str | None = None, name: str = "logo") -> str:
        alt = alt or self.config.project.name or "logo"
        dark = self._find_asset(f"{name}-dark", LOGO_EXTENSIONS)
        light = self._find_asset(f"{name}-light", LOGO_EXTENSIONS)
        single = self._find_asset(name, LOGO_EXTENSIONS)
        width_attr = f' width="{width}"' if width else ""
        rel = lambda p: p.relative_to(self.root).as_posix()  # noqa: E731
        if dark and light:
            return (
                "<picture>\n"
                f'  <source media="(prefers-color-scheme: dark)" srcset="{rel(dark)}">\n'
                f'  <source media="(prefers-color-scheme: light)" srcset="{rel(light)}">\n'
                f'  <img src="{rel(light)}" alt="{html.escape(alt)}"{width_attr}>\n'
                "</picture>"
            )
        src = single or light or dark
        if src is None:
            self.warn(f"logo: no {name}.{{svg,png,webp,jpg}} found")
            return ""
        return f'<img src="{rel(src)}" alt="{html.escape(alt)}"{width_attr}>'

    def video(self, name: str, width: int | None = None, alt: str | None = None) -> str:
        if "://" in name:
            src = name
        else:
            found = self._find_asset(name, VIDEO_EXTENSIONS)
            if found is None:
                self.warn(f"video '{name}' not found")
                return ""
            src = found.relative_to(self.root).as_posix()
        alt = alt or name
        width_attr = f' width="{width}"' if width else ""
        if src.lower().endswith(".gif"):
            return f'<img src="{src}" alt="{html.escape(alt)}"{width_attr}>'
        return f'<video src="{src}"{width_attr} controls muted loop></video>'

    def contributors(self, logins: list[str] | None = None, size: int = 64) -> str:
        if logins is None:
            rc = self.root / ".all-contributorsrc"
            if not rc.is_file():
                self.warn("contributors: pass a list or add .all-contributorsrc")
                return ""
            logins = [c["login"] for c in json.loads(rc.read_text()).get("contributors", [])]
        cells = [
            f'<a href="https://github.com/{login}">'
            f'<img src="https://github.com/{login}.png?size={size}" width="{size}" alt="{login}">'
            "</a>"
            for login in logins
        ]
        return '<p align="center">\n' + "\n".join(cells) + "\n</p>"

    # -------------------------------------------------------------- project
    def pyversions_list(self, sep: str = ", ") -> str:
        return sep.join(self.config.project.python_versions)

    def entry_points_table(self) -> str:
        path = self.root / "pyproject.toml"
        if not path.is_file():
            return ""
        scripts = tomllib.loads(path.read_text()).get("project", {}).get("scripts", {})
        return md_table(
            ["Command", "Entry point"], [[f"`{k}`", f"`{v}`"] for k, v in scripts.items()]
        )

    def flow_install_cmd(self) -> str:
        name = self.config.project.flow_plugin or self.config.project.name
        return fenced(f"pm install {name}", "text")

    def mc_versions(self) -> str:
        return self.config.project.minecraft_version or ""

    def mod_dependencies(self) -> str:
        for rel in MODS_TOML_PATHS:
            path = self.root / rel
            if path.is_file():
                break
        else:
            self.warn("mod_dependencies: no neoforge.mods.toml / mods.toml found")
            return ""
        data = tomllib.loads(path.read_text())
        rows = []
        for deps in data.get("dependencies", {}).values():
            for dep in deps:
                rows.append(
                    [
                        f"`{dep.get('modId', '')}`",
                        dep.get("type", "required" if dep.get("mandatory", True) else "optional"),
                        f"`{dep.get('versionRange', '*')}`",
                    ]
                )
        return md_table(["Mod", "Type", "Version"], rows)

    def related_repos(self) -> str:
        rows = []
        for item in self.config.related:
            url = item.url or (
                f"https://github.com/{item.repo}"
                if "/" in item.repo
                else f"https://github.com/{self.config.project.owner}/{item.repo}"
            )
            rows.append([f"[{item.repo}]({url})", item.description])
        return md_table(["Repository", "Description"], rows)

    # ----------------------------------------------------------------- meta
    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.root), *args], capture_output=True, text=True, check=False
        )
        return result.stdout.strip()

    def git_sha(self, short: bool = True) -> str:
        return self._git("rev-parse", "--short" if short else "HEAD", *(["HEAD"] if short else []))

    def git_tag(self) -> str:
        return self._git("describe", "--tags", "--abbrev=0")

    @staticmethod
    def today(fmt: str = "%Y-%m-%d") -> str:
        return date.today().strftime(fmt)

    def as_globals(self) -> dict[str, Any]:
        names = [
            "include_file", "code_block", "snippet", "cli_help", "config_table", "env_table",
            "gh_link", "spdx_link", "my_ha_link", "details", "callout", "center", "columns",
            "logo", "video", "contributors", "pyversions_list", "entry_points_table",
            "flow_install_cmd", "mc_versions", "mod_dependencies", "related_repos",
            "git_sha", "git_tag", "today",
        ]  # fmt: skip
        return {name: getattr(self, name) for name in names}
