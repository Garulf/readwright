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

from readwright.config import Config

LOGO_DIRS = ("", "docs", "assets", "docs/assets", "docs/images", "img", "images")
LOGO_EXTENSIONS = ("svg", "png", "webp", "jpg")
VIDEO_EXTENSIONS = ("mp4", "webm", "mov", "gif")
MODS_TOML_PATHS = (
    "src/main/resources/META-INF/neoforge.mods.toml",
    "src/main/resources/META-INF/mods.toml",
    "src/main/templates/META-INF/neoforge.mods.toml",
)
SPDX_URLS = "https://spdx.org/licenses/{id}.html"
UNSPLASH_CDN = "https://images.unsplash.com"
UNSPLASH_PHOTO = re.compile(r"(?:photo-)?(?P<id>\d{10,}-[0-9a-f]{10,})")
MY_HA = "https://my.home-assistant.io"


def _escape(text: str) -> str:
    return html.escape(text, quote=True)


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
        try:
            result = subprocess.run(
                shlex.split(command), capture_output=True, text=True, cwd=self.root, env=env
            )
        except FileNotFoundError:
            message = f"cli_help: executable not found for {command!r}"
            if self.config.strict:
                raise FileNotFoundError(message) from None
            self.warn(message)
            return ""
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
        """Centered block; the blank lines let GitHub render markdown inside the div."""
        return f'<div align="center">\n\n{content.strip()}\n\n</div>'

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

    def logo(self, width: int | None = None, alt: str | None = None, name: str = "logo") -> str:
        alt = alt or self.config.project.name or "logo"
        dark = self._find_asset(f"{name}-dark", LOGO_EXTENSIONS)
        light = self._find_asset(f"{name}-light", LOGO_EXTENSIONS)
        single = self._find_asset(name, LOGO_EXTENSIONS)
        rel = lambda p: p.relative_to(self.root).as_posix()  # noqa: E731
        if dark and light:
            if width:
                return (
                    "<picture>\n"
                    f'  <source media="(prefers-color-scheme: dark)" srcset="{rel(dark)}">\n'
                    f'  <source media="(prefers-color-scheme: light)" srcset="{rel(light)}">\n'
                    f'  <img src="{rel(light)}" alt="{_escape(alt)}" width="{width}">\n'
                    "</picture>"
                )
            return (
                f"![{alt}]({rel(light)}#gh-light-mode-only)![{alt}]({rel(dark)}#gh-dark-mode-only)"
            )
        src = single or light or dark
        if src is None:
            self.warn(f"logo: no {name}.{{svg,png,webp,jpg}} found")
            return ""
        if width:
            return f'<img src="{rel(src)}" alt="{_escape(alt)}" width="{width}">'
        return f"![{alt}]({rel(src)})"

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
            return f'<img src="{src}" alt="{_escape(alt)}"{width_attr}>'
        return f'<video src="{src}"{width_attr} controls muted loop></video>'

    def contributors(self, logins: list[str] | None = None, size: int = 64) -> str:
        if logins is None:
            rc = self.root / ".all-contributorsrc"
            if not rc.is_file():
                self.warn("contributors: pass a list or add .all-contributorsrc")
                return ""
            logins = [c["login"] for c in json.loads(rc.read_text()).get("contributors", [])]
        return " ".join(
            f"[![{login}](https://github.com/{login}.png?size={size})](https://github.com/{login})"
            for login in logins
        )

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

    # ------------------------------------------------------------- unsplash
    def _utm(self) -> str:
        source = (self.config.project.repo or self.config.project.name or "readwright").replace(
            " ", "_"
        )
        return urlencode({"utm_source": source, "utm_medium": "referral"})

    def unsplash(
        self,
        photo: str,
        alt: str | None = None,
        width: int | None = 1200,
        height: int | None = None,
        credit: str | None = None,
        user: str | None = None,
        photo_id: str | None = None,
        link: str | None = None,
        quality: int = 80,
        html: bool = False,
    ) -> str:
        """Embed an Unsplash photo by CDN id or images.unsplash.com URL, with attribution.

        `width`/`height` are what the CDN is asked for; the image is plain markdown unless
        `html=True`, which also sets the <img> width attribute.
        """
        match = UNSPLASH_PHOTO.search(photo)
        if not match:
            raise ValueError(
                f"unsplash: {photo!r} is not a photo id like 'photo-1518770660439-4636190af475' "
                "or an images.unsplash.com URL (right-click the photo, copy image address)"
            )
        params: dict[str, object] = {"auto": "format", "fit": "crop", "q": quality}
        if width:
            params["w"] = width
        if height:
            params["h"] = height
        src = f"{UNSPLASH_CDN}/photo-{match['id']}?{urlencode(params)}"
        alt = alt or "Photo from Unsplash"
        page = link or (f"https://unsplash.com/photos/{photo_id}" if photo_id else None)
        if html:
            width_attr = f' width="{width}"' if width else ""
            image = f'<img src="{src}" alt="{_escape(alt)}"{width_attr}>'
            if page:
                image = f'<a href="{page}">{image}</a>'
        else:
            image = f"![{alt}]({src})"
            if page:
                image = f"[{image}]({page})"
        if not credit:
            self.warn(
                f"unsplash: no credit given for photo {match['id']}; "
                "Unsplash's license requires attribution (pass credit= and user=)"
            )
            return image
        profile = (
            f"https://unsplash.com/@{user}?{self._utm()}"
            if user
            else f"https://unsplash.com/?{self._utm()}"
        )
        site = f"https://unsplash.com/?{self._utm()}"
        if html:
            attribution = (
                f'Photo by <a href="{profile}">{_escape(credit)}</a> on '
                f'<a href="{site}">Unsplash</a>'
            )
            return f"{image}\n<br><sub>{attribution}</sub>"
        return f"{image}\n\n*Photo by [{credit}]({profile}) on [Unsplash]({site})*"

    def banner(self) -> str:
        cfg = self.config.banner
        if cfg is None:
            return ""
        if cfg.unsplash:
            rendered = self.unsplash(
                cfg.unsplash,
                alt=cfg.alt,
                width=cfg.width,
                height=cfg.height,
                credit=cfg.credit,
                user=cfg.user,
                photo_id=cfg.photo_id,
                link=cfg.link,
                html=cfg.html,
            )
        elif cfg.image:
            alt = cfg.alt or self.config.project.name or "banner"
            if "://" not in cfg.image and not (self.root / cfg.image).is_file():
                self.warn(f"banner image '{cfg.image}' not found")
            if cfg.html:
                width_attr = f' width="{cfg.width}"' if cfg.width else ""
                rendered = f'<img src="{cfg.image}" alt="{_escape(alt)}"{width_attr}>'
                if cfg.link:
                    rendered = f'<a href="{cfg.link}">{rendered}</a>'
            else:
                rendered = f"![{alt}]({cfg.image})"
                if cfg.link:
                    rendered = f"[{rendered}]({cfg.link})"
        else:
            self.warn("banner: set either 'unsplash' or 'image'")
            return ""
        return self.center(rendered) if cfg.html else rendered

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
            "git_sha", "git_tag", "today", "unsplash", "banner",
        ]  # fmt: skip
        return {name: getattr(self, name) for name in names}
