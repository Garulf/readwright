"""readwright command line interface."""

from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.console import Console
from rich.table import Table

from readwright import __version__
from readwright.badges import BadgeRegistry
from readwright.config import (
    DEFAULT_CONFIG_NAME,
    DEFAULT_TEMPLATE,
    Config,
    ProjectInfo,
    config_sources,
    deep_merge,
    load_user_config,
    resolve,
)
from readwright.renderer import BASE_TEMPLATE, MARKER_PREFIX, Renderer, RenderResult

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
        "--user-config", help="Merge ~/.config/readwright/config.yaml under the repo config."
    ),
]
StrictOpt = Annotated[bool, typer.Option("--strict", help="Missing screenshots are errors.")]
VerboseOpt = Annotated[
    bool, typer.Option("--verbose", "-v", help="Show which loader served each template.")
]


def version_callback(value: bool) -> None:
    if value:
        out.print(f"readwright {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool, typer.Option("--version", callback=version_callback, is_eager=True)
    ] = False,
) -> None:
    pass


def warn(message: str) -> None:
    err.print("[yellow]warning:[/] ", end="")
    err.print(message, markup=False, highlight=False)


def fail(message: str, code: int = 1) -> None:
    err.print("[red]error:[/] ", end="")
    err.print(message, markup=False, highlight=False)
    raise typer.Exit(code)


def _load(root: Path, config: Path | None, user_config: bool, strict: bool) -> Config:
    if config is None and len(sources := config_sources(root)) > 1:
        warn(f"both {' and '.join(sources)} exist; using {sources[0]}")
    try:
        cfg = resolve(root, config_path=config, use_user_config=user_config)
    except ValueError as exc:
        fail(str(exc))
    return cfg.model_copy(update={"strict": True}) if strict else cfg


def _render_with(root: Path, cfg: Config, verbose: bool) -> RenderResult:
    try:
        result = Renderer(root, cfg, warn=warn).render()
    except Exception as exc:
        fail(f"{type(exc).__name__}: {exc}")
    if verbose:
        for name, source in result.sources.items():
            err.print(f"[dim]template {name} <- {source}[/]")
    return result


def _render(
    root: Path, config: Path | None, user_config: bool, strict: bool, verbose: bool = False
) -> tuple[Config, RenderResult]:
    cfg = _load(root, config, user_config, strict)
    return cfg, _render_with(root, cfg, verbose)


def _is_managed(path: Path) -> bool:
    return path.read_text(encoding="utf-8").startswith(MARKER_PREFIX)


def _write_output(root: Path, cfg: Config, result: RenderResult, force: bool) -> None:
    target = root / cfg.output
    if target.is_file():
        if target.read_text(encoding="utf-8") == result.text:
            out.print(f"{cfg.output} unchanged")
            return
        if not force and not _is_managed(target):
            fail(
                f"{cfg.output} exists and is not managed by readwright; "
                "use --force to overwrite or `readwright init --from-readme` to adopt it"
            )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(result.text, encoding="utf-8")
    out.print(f"{cfg.output} updated from {result.template_name}")


def watch_paths(root: Path, cfg: Config) -> list[Path]:
    candidates = [
        root / cfg.template,
        root / DEFAULT_CONFIG_NAME,
        root / "pyproject.toml",
        root / "templates",
        root / cfg.screenshots.dir,
        root / "CHANGELOG.md",
    ]
    candidates += [root / t for t in cfg.templates if not t.startswith("pkg:")]
    return [p for p in candidates if p.exists()]


@app.command()
def render(
    root: RootOpt = Path("."),
    config: ConfigOpt = None,
    user_config: UserConfigOpt = False,
    strict: StrictOpt = False,
    verbose: VerboseOpt = False,
    output: Annotated[
        str | None, typer.Option("--output", "-o", help="Output path, or '-' for stdout.")
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Overwrite an unmanaged existing README.")
    ] = False,
    watch: Annotated[
        bool, typer.Option("--watch", "-w", help="Re-render whenever inputs change.")
    ] = False,
) -> None:
    """Render the README template to the output file."""
    cfg = _load(root, config, user_config, strict)
    if output:
        cfg = cfg.model_copy(update={"output": output})
    result = _render_with(root, cfg, verbose)
    if cfg.output == "-":
        sys.stdout.write(result.text)
        return
    _write_output(root, cfg, result, force)
    if watch:
        _watch_loop(root, config, user_config, strict, verbose, output, force)


def _watch_loop(
    root: Path,
    config: Path | None,
    user_config: bool,
    strict: bool,
    verbose: bool,
    output: str | None,
    force: bool,
) -> None:
    from watchfiles import watch as watch_files

    cfg = _load(root, config, user_config, strict)
    paths = watch_paths(root, cfg)
    err.print(
        f"[dim]watching {', '.join(str(p.relative_to(root)) for p in paths)} (ctrl-c to stop)[/]"
    )
    try:
        for _changes in watch_files(*paths):
            try:
                cfg = _load(root, config, user_config, strict)
                if output:
                    cfg = cfg.model_copy(update={"output": output})
                _write_output(root, cfg, _render_with(root, cfg, verbose), force)
            except typer.Exit:
                continue
    except KeyboardInterrupt:
        return


@app.command()
def check(
    root: RootOpt = Path("."),
    config: ConfigOpt = None,
    user_config: UserConfigOpt = False,
    strict: StrictOpt = False,
    verbose: VerboseOpt = False,
) -> None:
    """Exit 1 if the output file is out of date with its template."""
    cfg, result = _render(root, config, user_config, strict, verbose)
    for name in result.user_templates:
        warn(f"user-level template '{name}' was used; CI renders will differ")
    target = root / cfg.output
    if not target.is_file():
        fail(f"{cfg.output} does not exist; run `readwright render`")
    current = target.read_text(encoding="utf-8")
    if not current.startswith(MARKER_PREFIX):
        warn(f"{cfg.output} is not managed by readwright (no marker); skipping")
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
    fail(f"{cfg.output} is out of date; run `readwright render`")


INIT_TEMPLATE = """\
{{% extends "base.md.j2" %}}

{{% block usage %}}
## Usage

Describe how to use {name} here.
{{% endblock %}}
"""

ADOPT_TEMPLATE = """\
{{% extends "base.md.j2" %}}

{{# Existing README content, moved here by `readwright init --from-readme`.
   Trim sections now provided by the base template (install, contributing, license),
   remove the raw tags to start using helpers like screenshot() and badge(). #}}
{{% block usage %}}
{open}{body}{close}
{{% endblock %}}

{{% block screenshots %}}{{% endblock %}}
{{% block install %}}{{% endblock %}}
{{% block contributing %}}{{% endblock %}}
{{% block license %}}{{% endblock %}}
"""

CONFIG_HEADER = """\
# readwright configuration. All keys are optional; autodetected values are shown.
# Keys: template, templates, output, strict, allow_exec, screenshots{dir,width,style}, badges,
#       badges_style, badges_custom, donate, donate_handles, related, project{...}, vars.
# Run `readwright badges` / `readwright blocks` to list badge presets and template blocks.
"""

H1 = re.compile(r"^#\s+.+\n+", re.MULTILINE)
JINJA_SYNTAX = re.compile(r"{[{%#]")


def _init_config_data(root: Path) -> dict:
    cfg = resolve(root)
    data = cfg.model_dump(exclude_defaults=True, exclude_none=True)
    if (user := load_user_config()) is not None:
        data = deep_merge(user.model_dump(exclude_defaults=True, exclude_none=True), data)
    data.setdefault("badges", [])
    project = data.setdefault("project", {})
    for key in ("python_versions", "project_type", "version"):
        project.pop(key, None)
    return data


def _adopted_body(readme: Path) -> str:
    body = H1.sub("", readme.read_text(encoding="utf-8"), count=1).strip("\n") + "\n"
    if JINJA_SYNTAX.search(body):
        return ADOPT_TEMPLATE.format(open="{% raw %}\n", body=body, close="{% endraw +%}\n")
    return ADOPT_TEMPLATE.format(open="", body=body, close="")


def _write_pyproject_config(root: Path, data: dict) -> None:
    import tomli_w

    path = root / "pyproject.toml"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    if "[tool.readme]" in text:
        fail("pyproject.toml already has a [tool.readme] section; refusing to overwrite")
    section = tomli_w.dumps({"tool": {"readme": data}})
    path.write_text(text.rstrip("\n") + "\n\n" + section if text else section, encoding="utf-8")


@app.command()
def init(
    root: RootOpt = Path("."),
    from_readme: Annotated[
        bool,
        typer.Option("--from-readme", help="Move an existing README.md body into the template."),
    ] = False,
    pyproject: Annotated[
        bool,
        typer.Option("--pyproject", help="Write config to [tool.readme] instead of readme.yaml."),
    ] = False,
) -> None:
    """Scaffold readme.yaml and README.md.j2 in the repository."""
    config_path = root / DEFAULT_CONFIG_NAME
    template_path = root / DEFAULT_TEMPLATE
    existing = [
        p for p in ((template_path,) if pyproject else (config_path, template_path)) if p.exists()
    ]
    if existing:
        fail(f"{existing[0].name} already exists; refusing to overwrite")
    if pyproject and config_path.exists():
        fail(f"{DEFAULT_CONFIG_NAME} already exists; refusing to overwrite")
    data = _init_config_data(root)
    name = data.get("project", {}).get("name") or root.resolve().name
    readme = root / "README.md"
    if from_readme:
        if not readme.is_file():
            fail("--from-readme given but README.md does not exist")
        if _is_managed(readme):
            fail("README.md is already managed by readwright")
        template_path.write_text(_adopted_body(readme), encoding="utf-8")
    else:
        template_path.write_text(INIT_TEMPLATE.format(name=name), encoding="utf-8")
    if pyproject:
        _write_pyproject_config(root, data)
        config_name = "pyproject.toml [tool.readme]"
    else:
        config_path.write_text(
            CONFIG_HEADER + yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
        )
        config_name = DEFAULT_CONFIG_NAME
    if from_readme:
        cfg = _load(root, None, False, False)
        _write_output(root, cfg, _render_with(root, cfg, False), force=True)
        out.print(f"created {config_name} and {DEFAULT_TEMPLATE}; README.md is now managed")
        return
    out.print(f"created {config_name} and {DEFAULT_TEMPLATE}; run `readwright render`")


@app.command()
def badges(root: RootOpt = Path("."), config: ConfigOpt = None) -> None:
    """List available badge presets."""
    try:
        cfg = resolve(root, config_path=config)
    except ValueError:
        cfg = Config(project=ProjectInfo())
    registry = BadgeRegistry(cfg)
    table = Table(show_lines=False)
    table.add_column("preset", no_wrap=True)
    table.add_column("example", overflow="fold")
    for name in registry.names():
        try:
            example = registry.render(name)
        except ValueError as exc:
            example = f"[dim]{exc}[/]"
        table.add_row(name, example)
    out.print(table)


@app.command()
def blocks(root: RootOpt = Path("."), config: ConfigOpt = None) -> None:
    """List the blocks of base.md.j2 and the partials that can be shadowed."""
    cfg = _load(root, config, False, False)
    renderer = Renderer(root, cfg)
    template = renderer.env.get_template(BASE_TEMPLATE)
    out.print(f"[bold]blocks in {BASE_TEMPLATE}[/]")
    for name in template.blocks:
        out.print(f"  {name}")
    out.print("[bold]partials[/] (shadow with templates/partials/<name> in the repo)")
    for name in sorted(renderer.env.list_templates()):
        if name.startswith("partials/"):
            out.print(f"  {name}  [dim]<- {renderer.source_label(name)}[/]")


@app.command()
def show(
    name: Annotated[str, typer.Argument(help="Template name, e.g. base.md.j2")],
    root: RootOpt = Path("."),
    config: ConfigOpt = None,
) -> None:
    """Print a template's source (useful for copying a partial to override it)."""
    cfg = _load(root, config, False, False)
    renderer = Renderer(root, cfg)
    try:
        source, _, _ = renderer.env.loader.get_source(renderer.env, name)
    except Exception:
        fail(f"template '{name}' not found")
    err.print(f"[dim]# {name} <- {renderer.source_label(name)}[/]")
    sys.stdout.write(source)


if __name__ == "__main__":
    app()
