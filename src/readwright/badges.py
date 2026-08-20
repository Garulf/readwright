"""Badge presets and shields.io URL building."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import quote, urlencode

from readwright.config import BadgeSpec, Config, CustomBadge

SHIELDS = "https://img.shields.io"


def _escape_static(text: str) -> str:
    return quote(text.replace("-", "--").replace("_", "__"), safe="")


def badge_markdown(alt: str, image_url: str, link: str | None) -> str:
    image = f"![{alt}]({image_url})"
    return f"[{image}]({link})" if link else image


def shield(
    label: str,
    message: str,
    color: str = "blue",
    link: str | None = None,
    logo: str | None = None,
    style: str | None = None,
) -> str:
    url = f"{SHIELDS}/badge/{_escape_static(label)}-{_escape_static(message)}-{color}"
    params = {k: v for k, v in (("logo", logo), ("style", style)) if v}
    if params:
        url += "?" + urlencode(params)
    return badge_markdown(label, url, link)


IMAGE_URL = re.compile(r"!\[[^\]]*\]\((https://img\.shields\.io/[^)\s]+)\)")


def apply_style(markdown: str, style: str | None) -> str:
    if not style:
        return markdown

    def add(match: re.Match[str]) -> str:
        url = match.group(1)
        if "style=" in url:
            return match.group(0)
        joiner = "&" if "?" in url else "?"
        return match.group(0).replace(url, f"{url}{joiner}style={style}")

    return IMAGE_URL.sub(add, markdown)


@dataclass
class BadgeContext:
    config: Config
    options: dict[str, object]

    def require(self, *fields: str) -> list[str]:
        values = []
        for name in fields:
            value = self.options.get(name) or getattr(self.config.project, name, None)
            if not value:
                raise ValueError(f"badge needs project.{name}; set it in readme.yaml")
            values.append(str(value))
        return values

    def handle(self, preset: str) -> str:
        value = self.options.get("handle") or self.config.donate_handles.get(preset)
        if not value:
            raise ValueError(f"badge '{preset}' needs donate_handles.{preset} in readme.yaml")
        return str(value)


Preset = Callable[[BadgeContext], str]


def _pypi(ctx: BadgeContext) -> str:
    (pypi,) = ctx.require("pypi")
    return badge_markdown("PyPI", f"{SHIELDS}/pypi/v/{pypi}", f"https://pypi.org/project/{pypi}/")


def _pypi_downloads(ctx: BadgeContext) -> str:
    (pypi,) = ctx.require("pypi")
    return badge_markdown(
        "Downloads", f"{SHIELDS}/pypi/dm/{pypi}", f"https://pypi.org/project/{pypi}/"
    )


def _python(ctx: BadgeContext) -> str:
    (pypi,) = ctx.require("pypi")
    return badge_markdown(
        "Python", f"{SHIELDS}/pypi/pyversions/{pypi}", f"https://pypi.org/project/{pypi}/"
    )


def _license(ctx: BadgeContext) -> str:
    owner, repo = ctx.require("owner", "repo")
    return badge_markdown(
        "License",
        f"{SHIELDS}/github/license/{owner}/{repo}",
        f"https://github.com/{owner}/{repo}/blob/main/LICENSE",
    )


def _ci(ctx: BadgeContext) -> str:
    owner, repo = ctx.require("owner", "repo")
    workflow = str(ctx.options.get("workflow") or ctx.config.project.ci_workflow or "ci.yml")
    return badge_markdown(
        "CI",
        f"{SHIELDS}/github/actions/workflow/status/{owner}/{repo}/{workflow}",
        f"https://github.com/{owner}/{repo}/actions/workflows/{workflow}",
    )


def _codecov(ctx: BadgeContext) -> str:
    owner, repo = ctx.require("owner", "repo")
    return badge_markdown(
        "Coverage",
        f"{SHIELDS}/codecov/c/github/{owner}/{repo}",
        f"https://codecov.io/gh/{owner}/{repo}",
    )


def _npm(ctx: BadgeContext) -> str:
    (npm,) = ctx.require("npm")
    return badge_markdown(
        "npm", f"{SHIELDS}/npm/v/{quote(npm, safe='')}", f"https://www.npmjs.com/package/{npm}"
    )


def _github_release(ctx: BadgeContext) -> str:
    owner, repo = ctx.require("owner", "repo")
    return badge_markdown(
        "Release",
        f"{SHIELDS}/github/v/release/{owner}/{repo}",
        f"https://github.com/{owner}/{repo}/releases/latest",
    )


def _github_stars(ctx: BadgeContext) -> str:
    owner, repo = ctx.require("owner", "repo")
    return badge_markdown(
        "Stars",
        f"{SHIELDS}/github/stars/{owner}/{repo}",
        f"https://github.com/{owner}/{repo}/stargazers",
    )


def _pre_commit(ctx: BadgeContext) -> str:
    return shield(
        "pre-commit",
        "enabled",
        "brightgreen",
        logo="pre-commit",
        link="https://github.com/pre-commit/pre-commit",
    )


def _ruff(ctx: BadgeContext) -> str:
    url = (
        f"{SHIELDS}/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/"
        "assets/badge/v2.json"
    )
    return badge_markdown("Ruff", url, "https://github.com/astral-sh/ruff")


def _modrinth(ctx: BadgeContext) -> str:
    slug = str(ctx.options.get("slug") or ctx.config.project.modrinth or "")
    if not slug:
        raise ValueError("badge 'modrinth' needs project.modrinth (the project slug)")
    return badge_markdown(
        "Modrinth",
        f"{SHIELDS}/modrinth/dt/{slug}?logo=modrinth",
        f"https://modrinth.com/mod/{slug}",
    )


def _curseforge(ctx: BadgeContext) -> str:
    project_id = str(ctx.options.get("id") or ctx.config.project.curseforge or "")
    if not project_id:
        raise ValueError("badge 'curseforge' needs project.curseforge (the numeric project id)")
    return badge_markdown(
        "CurseForge",
        f"{SHIELDS}/curseforge/dt/{project_id}?logo=curseforge",
        f"https://www.curseforge.com/projects/{project_id}",
    )


def _hacs(ctx: BadgeContext) -> str:
    kind = str(ctx.options.get("kind") or "Custom")
    return shield("HACS", kind, "41BDF5", logo="homeassistant", link="https://hacs.xyz")


def _ha_version(ctx: BadgeContext) -> str:
    version = str(ctx.options.get("version") or ctx.config.project.ha_min_version or "")
    if not version:
        raise ValueError("badge 'ha-version' needs project.ha_min_version (from hacs.json)")
    return shield(
        "Home Assistant",
        f"{version}+",
        "03A9F4",
        logo="homeassistant",
        link="https://www.home-assistant.io",
    )


def _version(ctx: BadgeContext) -> str:
    (version,) = ctx.require("version")
    return shield("version", version, "informational", link=ctx.config.project.url)


def _kofi(ctx: BadgeContext) -> str:
    handle = ctx.handle("kofi")
    return shield("Ko-fi", "support", "FF5E5B", logo="ko-fi", link=f"https://ko-fi.com/{handle}")


def _buymeacoffee(ctx: BadgeContext) -> str:
    handle = ctx.handle("buymeacoffee")
    return shield(
        "Buy Me a Coffee",
        "support",
        "FFDD00",
        logo="buy-me-a-coffee",
        link=f"https://www.buymeacoffee.com/{handle}",
    )


def _github_sponsors(ctx: BadgeContext) -> str:
    handle = ctx.handle("github-sponsors")
    return badge_markdown(
        "Sponsor",
        f"{SHIELDS}/github/sponsors/{handle}?logo=githubsponsors",
        f"https://github.com/sponsors/{handle}",
    )


def _patreon(ctx: BadgeContext) -> str:
    handle = ctx.handle("patreon")
    return shield(
        "Patreon", "support", "F96854", logo="patreon", link=f"https://patreon.com/{handle}"
    )


def _paypal(ctx: BadgeContext) -> str:
    handle = ctx.handle("paypal")
    return shield("PayPal", "donate", "00457C", logo="paypal", link=f"https://paypal.me/{handle}")


BUILTIN_PRESETS: dict[str, Preset] = {
    "pypi": _pypi,
    "pypi-downloads": _pypi_downloads,
    "python": _python,
    "license": _license,
    "ci": _ci,
    "codecov": _codecov,
    "npm": _npm,
    "github-release": _github_release,
    "github-stars": _github_stars,
    "pre-commit": _pre_commit,
    "ruff": _ruff,
    "version": _version,
    "modrinth": _modrinth,
    "curseforge": _curseforge,
    "hacs": _hacs,
    "ha-version": _ha_version,
}

DONATION_PRESETS: dict[str, Preset] = {
    "kofi": _kofi,
    "buymeacoffee": _buymeacoffee,
    "github-sponsors": _github_sponsors,
    "patreon": _patreon,
    "paypal": _paypal,
}


def _custom_preset(spec: CustomBadge) -> Preset:
    def render(ctx: BadgeContext) -> str:
        return shield(
            spec.label, spec.message, spec.color, link=spec.link, logo=spec.logo, style=spec.style
        )

    return render


class BadgeRegistry:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.presets: dict[str, Preset] = {**BUILTIN_PRESETS, **DONATION_PRESETS}
        self.presets.update(
            {name: _custom_preset(spec) for name, spec in config.badges_custom.items()}
        )

    def names(self) -> list[str]:
        return list(self.presets)

    def render(self, preset: str, **options: object) -> str:
        try:
            fn = self.presets[preset]
        except KeyError:
            raise ValueError(
                f"unknown badge preset '{preset}'; run `readwright badges` to list presets"
            ) from None
        style = options.pop("style", None) or self.config.badges_style
        return apply_style(fn(BadgeContext(self.config, options)), style)

    def render_spec(self, spec: BadgeSpec, style: str | None = None) -> str:
        if spec.shield is not None:
            return apply_style(
                _custom_preset(spec.shield)(BadgeContext(self.config, {})),
                style or self.config.badges_style,
            )
        assert spec.preset is not None
        return self.render(spec.preset, **{"style": style, **spec.options})

    def render_all(self, style: str | None = None) -> str:
        return " ".join(self.render_spec(spec, style) for spec in self.config.badges)

    def render_donate(self, style: str | None = None) -> str:
        return " ".join(self.render_spec(spec, style) for spec in self.config.donate)
