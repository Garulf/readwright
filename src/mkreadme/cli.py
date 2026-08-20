"""mkreadme command line interface."""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.console import Console
from rich.table import Table

from mkreadme import __version__
from mkreadme.badges import BadgeRegistry
from mkreadme.config import (
    DEFAULT_CONFIG_NAME,
    DEFAULT_TEMPLATE,
    Config,
    ProjectInfo,
    deep_merge,
    load_user_config,
    resolve,
)
from mkreadme.renderer import MARKER_PREFIX, Renderer, RenderResult

app = typer.Typer(
    help="Render GitHub READMEs from Jinja2 templates.",
    no_args_is_help=True,
    add_completion=False,
)
out = Console()
err = Console(stderr=True)

RootOpt = Annotated[Path, typer.Option("--root", "-C", help="Repository root.")]
ConfigOpt = Annotated[Path | None, typer.Option("--config", "-c", help="Config file path.")]
UserConfigOpt = Annotated[
    bool,
    typer.Option(
        "--user-config", help="Merge ~/.config/mkreadme/config.yaml under the repo config."
    ),
]
StrictOpt = Annotated[bool, typer.Option("--strict", help="Missing screenshots are errors.")]


def version_callback(value: bool) -> None:
    if value:
        out.print(f"mkreadme {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool, typer.Option("--version", callback=version_callback, is_eager=True)
    ] = False,
) -> None:
    pass


def warn(message: str) -> None:
    err.print(f"[yellow]warning:[/] {message}")


def fail(message: str, code: int = 1) -> None:
    err.print(f"[red]error:[/] {message}")
    raise typer.Exit(code)


def _render(
    root: Path, config: Path | None, user_config: bool, strict: bool
) -> tuple[Config, RenderResult]:
    try:
        cfg = resolve(root, config_path=config, use_user_config=user_config)
    except ValueError as exc:
        fail(str(exc))
    if strict:
        cfg = cfg.model_copy(update={"strict": True})
    try:
        result = Renderer(root, cfg, warn=warn).render()
    except Exception as exc:
        fail(f"{type(exc).__name__}: {exc}")
    return cfg, result


@app.command()
def render(
    root: RootOpt = Path("."),
    config: ConfigOpt = None,
    user_config: UserConfigOpt = False,
    strict: StrictOpt = False,
) -> None:
    """Render the README template to the output file."""
    cfg, result = _render(root, config, user_config, strict)
    target = root / cfg.output
    if target.is_file() and target.read_text() == result.text:
        out.print(f"{cfg.output} unchanged")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(result.text)
    out.print(f"{cfg.output} updated from {result.template_name}")


@app.command()
def check(
    root: RootOpt = Path("."),
    config: ConfigOpt = None,
    user_config: UserConfigOpt = False,
    strict: StrictOpt = False,
) -> None:
    """Exit 1 if the output file is out of date with its template."""
    cfg, result = _render(root, config, user_config, strict)
    for name in result.user_templates:
        warn(f"user-level template '{name}' was used; CI renders will differ")
    target = root / cfg.output
    if not target.is_file():
        fail(f"{cfg.output} does not exist; run `mkreadme render`")
    current = target.read_text()
    if not current.startswith(MARKER_PREFIX):
        warn(f"{cfg.output} is not managed by mkreadme (no marker); skipping")
        return
    if current == result.text:
        out.print(f"{cfg.output} is up to date")
        return
    diff = difflib.unified_diff(
        current.splitlines(keepends=True),
        result.text.splitlines(keepends=True),
        fromfile=cfg.output,
        tofile=f"{cfg.output} (rendered)",
    )
    out.print("".join(diff), end="", highlight=False, markup=False)
    fail(f"{cfg.output} is out of date; run `mkreadme render`")


INIT_TEMPLATE = """\
{{% extends "base.md.j2" %}}

{{% block usage %}}
## Usage

Describe how to use {name} here.

{{% endblock %}}
"""

CONFIG_HEADER = """\
# mkreadme configuration. All keys are optional; autodetected values are shown.
# Keys: template, output, strict, screenshots{dir,width,style}, badges, badges_custom,
#       donate, donate_handles, project{...}, vars.
# Run `mkreadme badges` to list badge presets.
"""


def _init_config_data(root: Path) -> dict:
    cfg = resolve(root)
    data = cfg.model_dump(exclude_defaults=True, exclude_none=True)
    if (user := load_user_config()) is not None:
        user_data = user.model_dump(exclude_defaults=True, exclude_none=True)
        data = deep_merge(user_data, data)
    data.setdefault("badges", [])
    project = data.setdefault("project", {})
    project.pop("python_versions", None)
    project.pop("project_type", None)
    project.pop("version", None)
    return data


@app.command()
def init(root: RootOpt = Path(".")) -> None:
    """Scaffold readme.yaml and README.md.j2 in the repository."""
    config_path = root / DEFAULT_CONFIG_NAME
    template_path = root / DEFAULT_TEMPLATE
    for path in (config_path, template_path):
        if path.exists():
            fail(f"{path.name} already exists; refusing to overwrite")
    data = _init_config_data(root)
    config_path.write_text(CONFIG_HEADER + yaml.safe_dump(data, sort_keys=False))
    name = data.get("project", {}).get("name") or root.resolve().name
    template_path.write_text(INIT_TEMPLATE.format(name=name))
    out.print(f"created {DEFAULT_CONFIG_NAME} and {DEFAULT_TEMPLATE}; run `mkreadme render`")


@app.command()
def badges(root: RootOpt = Path("."), config: ConfigOpt = None) -> None:
    """List available badge presets."""
    try:
        cfg = resolve(root, config_path=config)
    except ValueError:
        cfg = Config(project=ProjectInfo())
    registry = BadgeRegistry(cfg)
    table = Table("preset", "example", show_lines=False)
    for name in registry.names():
        try:
            example = registry.render(name)
        except ValueError as exc:
            example = f"[dim]{exc}[/]"
        table.add_row(name, example)
    out.print(table)


if __name__ == "__main__":
    app()
