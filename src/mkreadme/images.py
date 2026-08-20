"""Screenshot discovery and image tag helpers."""

from __future__ import annotations

import html
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import yaml

from mkreadme.config import Config

EXTENSIONS = ("png", "jpg", "jpeg", "gif", "webp", "svg")
VARIANTS = ("dark", "light")


class MissingImageError(FileNotFoundError):
    pass


def titleize(stem: str) -> str:
    stem = stem.rsplit("/", 1)[-1]
    return " ".join(part.capitalize() for part in stem.replace("_", "-").split("-") if part)


def img_tag(src: str, alt: str, width: int | None) -> str:
    width_attr = f' width="{width}"' if width else ""
    return f'<img src="{src}" alt="{html.escape(alt, quote=True)}"{width_attr}>'


def md_image(src: str, alt: str) -> str:
    return f"![{alt}]({src})"


def md_pair(dark: str, light: str, alt: str) -> str:
    """GitHub-only trick: image fragments select light/dark variants in pure markdown."""
    return f"![{alt}]({light}#gh-light-mode-only)![{alt}]({dark}#gh-dark-mode-only)"


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
        html_mode = force_html or bool(width) or self.config.screenshots.style == "html"
        if shot.is_pair:
            dark, light = self._rel(shot.dark), self._rel(shot.light)
            return picture_tag(dark, light, alt, width) if html_mode else md_pair(dark, light, alt)
        src = shot.single or shot.light or shot.dark
        assert src is not None
        return img_tag(self._rel(src), alt, width) if html_mode else md_image(self._rel(src), alt)

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

    def _captions(self, directory: Path) -> dict[str, str]:
        path = directory / "captions.yaml"
        if not path.is_file():
            return {}
        data = yaml.safe_load(path.read_text()) or {}
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}

    def _discover(self, directory: Path) -> list[Shot]:
        if not directory.is_dir():
            self.warn(f"screenshots dir '{self._rel(directory)}' does not exist")
            return []
        files = sorted(p for p in directory.iterdir() if p.suffix.lstrip(".").lower() in EXTENSIONS)
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

    def screenshots(
        self,
        columns: int = 2,
        subdir: str | None = None,
        order: list[str] | None = None,
        captions: dict[str, str] | None = None,
        show_captions: bool = True,
    ) -> str:
        directory = self.shots_dir / subdir if subdir else self.shots_dir
        shots = self._discover(directory)
        if not shots:
            if directory.is_dir():
                self.warn(f"no screenshots found in {self._rel(directory)}")
            return ""
        all_captions = {**self._captions(directory), **(captions or {})}
        if order:
            by_name = {shot.name: shot for shot in shots}
            missing = [name for name in order if name not in by_name]
            if missing:
                self.warn(f"screenshots order lists unknown names: {', '.join(missing)}")
            ordered = [by_name[n] for n in order if n in by_name]
            shots = ordered + [s for s in shots if s.name not in order]
        columns = max(columns, 1)
        captioned = [(shot, all_captions.get(shot.name, titleize(shot.name))) for shot in shots]
        if self.config.screenshots.style == "html":
            return self._html_gallery(captioned, columns, show_captions)
        return self._markdown_gallery(captioned, columns, show_captions)

    def _markdown_gallery(
        self, shots: list[tuple[Shot, str]], columns: int, show_captions: bool
    ) -> str:
        def row(cells: list[str]) -> str:
            padded = cells + [""] * (columns - len(cells))
            return "| " + " | ".join(padded) + " |"

        lines: list[str] = []
        for i in range(0, len(shots), columns):
            chunk = shots[i : i + columns]
            lines.append(row([self._render_shot(s, c, None, False) for s, c in chunk]))
            if i == 0:
                lines.append(row([":---:"] * columns))
            if show_captions:
                lines.append(row([c.replace("|", "\\|") for _, c in chunk]))
        return "\n".join(lines)

    def _html_gallery(
        self, shots: list[tuple[Shot, str]], columns: int, show_captions: bool
    ) -> str:
        width = self.config.screenshots.width
        cells = []
        for shot, caption in shots:
            cell = self._render_shot(shot, caption, width, force_html=True)
            if show_captions:
                cell += f"<br><sub>{html.escape(caption)}</sub>"
            cells.append(f'<td align="center">{cell}</td>')
        rows = [
            "<tr>\n" + "\n".join(cells[i : i + columns]) + "\n</tr>"
            for i in range(0, len(cells), columns)
        ]
        return "<table>\n" + "\n".join(rows) + "\n</table>"
