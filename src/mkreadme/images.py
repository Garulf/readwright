"""Screenshot discovery and image tag helpers."""

from __future__ import annotations

import html
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from mkreadme.config import Config

EXTENSIONS = ("png", "jpg", "jpeg", "gif", "webp", "svg")
VARIANTS = ("dark", "light")


class MissingImageError(FileNotFoundError):
    pass


def titleize(stem: str) -> str:
    return " ".join(part.capitalize() for part in stem.replace("_", "-").split("-") if part)


def img_tag(src: str, alt: str, width: int | None) -> str:
    width_attr = f' width="{width}"' if width else ""
    return f'<img src="{src}" alt="{html.escape(alt, quote=True)}"{width_attr}>'


def md_image(src: str, alt: str) -> str:
    return f"![{alt}]({src})"


def picture_tag(dark: str, light: str, alt: str, width: int | None) -> str:
    return (
        "<picture>\n"
        f'  <source media="(prefers-color-scheme: dark)" srcset="{dark}">\n'
        f'  <source media="(prefers-color-scheme: light)" srcset="{light}">\n'
        f"  {img_tag(light, alt, width)}\n"
        "</picture>"
    )


@dataclass
class Shot:
    name: str
    single: Path | None = None
    dark: Path | None = None
    light: Path | None = None

    @property
    def is_pair(self) -> bool:
        return self.dark is not None and self.light is not None


class ImageHelper:
    def __init__(
        self, root: Path, config: Config, warn: Callable[[str], None] | None = None
    ) -> None:
        self.root = Path(root)
        self.config = config
        self.warn = warn or (lambda message: None)

    @property
    def shots_dir(self) -> Path:
        return self.root / self.config.screenshots.dir

    def _rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def _find(self, stem: str) -> Path | None:
        for ext in EXTENSIONS:
            candidate = self.shots_dir / f"{stem}.{ext}"
            if candidate.is_file():
                return candidate
        return None

    def _lookup(self, name: str) -> Shot:
        return Shot(
            name=name,
            single=self._find(name),
            dark=self._find(f"{name}-dark"),
            light=self._find(f"{name}-light"),
        )

    def _render_shot(self, shot: Shot, alt: str, width: int | None, force_html: bool) -> str:
        if shot.is_pair:
            return picture_tag(self._rel(shot.dark), self._rel(shot.light), alt, width)
        src = shot.single or shot.light or shot.dark
        assert src is not None
        if force_html or width or self.config.screenshots.style == "html":
            return img_tag(self._rel(src), alt, width)
        return md_image(self._rel(src), alt)

    def _missing(self, message: str) -> str:
        if self.config.strict:
            raise MissingImageError(message)
        self.warn(message)
        return ""

    def screenshot(self, name: str, alt: str | None = None, width: int | None = None) -> str:
        shot = self._lookup(name)
        if not (shot.single or shot.dark or shot.light):
            return self._missing(
                f"screenshot '{name}' not found in {self.config.screenshots.dir} "
                f"(tried extensions {', '.join(EXTENSIONS)})"
            )
        force_html = width is not None
        width = width if width is not None else self._style_width()
        return self._render_shot(shot, alt or titleize(name), width, force_html)

    def _style_width(self) -> int | None:
        return self.config.screenshots.width if self.config.screenshots.style == "html" else None

    def image(self, path: str, alt: str = "", width: int | None = None) -> str:
        if "://" not in path and not (self.root / path).is_file():
            self.warn(f"image '{path}' not found")
        return img_tag(path, alt, width) if width else md_image(path, alt)

    def _discover(self) -> list[Shot]:
        if not self.shots_dir.is_dir():
            self.warn(f"screenshots dir '{self.config.screenshots.dir}' does not exist")
            return []
        files = sorted(
            p for p in self.shots_dir.iterdir() if p.suffix.lstrip(".").lower() in EXTENSIONS
        )
        shots: dict[str, Shot] = {}
        for path in files:
            stem, variant = path.stem, None
            for candidate in VARIANTS:
                if stem.endswith(f"-{candidate}"):
                    stem, variant = stem[: -len(candidate) - 1], candidate
                    break
            shot = shots.setdefault(stem, Shot(name=stem))
            if variant is None:
                shot.single = shot.single or path
            else:
                setattr(shot, variant, getattr(shot, variant) or path)
        return list(shots.values())

    def has_screenshots(self) -> bool:
        return self.shots_dir.is_dir() and any(
            p.suffix.lstrip(".").lower() in EXTENSIONS for p in self.shots_dir.iterdir()
        )

    def screenshots(self, columns: int = 2) -> str:
        shots = self._discover()
        if not shots:
            if self.shots_dir.is_dir():
                self.warn(f"no screenshots found in {self.config.screenshots.dir}")
            return ""
        width = self.config.screenshots.width
        cells = [
            '<td align="center">'
            + self._render_shot(shot, titleize(shot.name), width, force_html=True)
            + "</td>"
            for shot in shots
        ]
        rows = [
            "<tr>\n" + "\n".join(cells[i : i + columns]) + "\n</tr>"
            for i in range(0, len(cells), max(columns, 1))
        ]
        return "<table>\n" + "\n".join(rows) + "\n</table>"
