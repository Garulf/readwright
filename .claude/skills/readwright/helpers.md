# readwright template helpers — full reference

All helpers are called from `README.md.j2` (or any partial it includes). Signatures
below match the Python implementation; Jinja calls omit `self`.

## Badges

- `badge(preset, **options)` — a preset badge (`readwright badges` lists names:
  `pypi`, `pypi-downloads`, `python`, `license`, `ci`, `codecov`, `npm`,
  `github-release`, `github-stars`, `pre-commit`, `ruff`, `version`, `modrinth`,
  `curseforge`, `hacs`, `ha-version`; donation presets: `kofi`, `buymeacoffee`,
  `github-sponsors`, `patreon`, `paypal`). Presets pull from `project.*` in config —
  e.g. `badge("ci", workflow="test.yml")` needs `project.owner`/`project.repo`.
- `shield(label, message, color, link=None, style=None)` — a custom static
  shields.io badge: `shield("Discord", "chat", "5865F2", link=gh_link("wiki"))`.
- `badges()` — renders every entry in config's `badges:` list (preset names, or
  `{preset: ..., **opts}` / `{shield: {...}}` dicts) plus anything under
  `badges_custom:`, in one row.
- `donate_badges()` — same, for config's `donate:` list.
- `badges_extra` / `donate_extra` block hooks — add a badge to the row without
  editing the config list:
  `{% block badges_extra %} {{ shield("docs", "latest", "success") }}{% endblock %}`
- Pass `style=` to any badge helper, or set `badges_style:` in config, to apply a
  shields.io style (`flat-square`, etc.) to everything.

## Images

- `screenshot(name, alt=None, width=None)` — finds `docs/screenshots/{name}.{png,jpg,gif,webp,svg}`
  (dir configurable via `screenshots.dir`). If `{name}-dark.*` and `{name}-light.*`
  both exist, renders a theme-aware pair using GitHub's `#gh-light-mode-only` /
  `#gh-dark-mode-only` markdown fragments (or an HTML `<picture>` if
  `screenshots.style: html` / `html=True` via a wider call, or `width=` is set,
  since markdown can't express width).
- `screenshots(columns=2, order=None, captions=None, subdir=None)` — a gallery
  table of every image in the screenshots dir. `order=["main", "settings"]` fixes
  ordering; `captions={"main": "Main window"}` or a `captions.yaml` file in the
  folder supplies captions.
- `has_screenshots()` — boolean, for conditionally rendering a screenshots section.
- `image(path, alt="", width=None)` — an explicit image (local path or URL), no
  discovery.
- `logo(width=None, alt=None, name="logo")` — theme-aware logo from
  `docs/logo.{png,svg,...}` (or `logo-dark`/`logo-light` pair).
- `video(name, width=None, alt=None)` — embeds a video/gif from the screenshots dir.
- `unsplash(photo, alt=None, width=1200, height=None, credit=None, user=None, photo_id=None, link=None, quality=80, html=False)` —
  hero image from Unsplash's CDN. `photo` is a photo id like
  `"photo-1518770660439-4636190af475"` or a full `images.unsplash.com` URL.
  **Always pass `credit=` and `user=`** — Unsplash's license requires attribution;
  omitting them renders the image with a `warn()` and no attribution line. `banner:`
  in config renders one automatically above the title via the same helper.

Image helpers emit plain markdown by default (no `<picture>`/`<img>`), and only
fall back to HTML when markdown can't express what was asked (a `width=`, an
explicit `html=True`).

## Structure

- `toc(min_level=2, max_level=3)` — table of contents built from the markdown
  headings that appear *below* this call in the rendered output.
- `changelog(n=1)` — the newest `n` entries from `CHANGELOG.md` /
  `CHANGES.md` / `HISTORY.md` (Keep-a-Changelog `##` headings), with heading levels
  shifted to nest under the calling context.

## Pulling in files and command output

- `include_file(path)` — raw contents of a file, relative to repo root.
- `code_block(path, language=None)` — `include_file` wrapped in a fenced code
  block; language defaults to the file extension.
- `snippet(path, start, end, language=None, dedent=True)` — the lines between the
  first line containing `start` and the first line at/after it containing `end`,
  fenced. Useful for pulling a marked region out of a source file instead of the
  whole thing.
- `cli_help(command, language="text", strip_ansi=True)` — runs `command` (shell-split,
  no shell interpolation) via subprocess and fences stdout/stderr.
  **Requires `allow_exec: true` in config** — raises `PermissionError` otherwise,
  since it executes code during render.

## Tables

- `config_table(path, section=None, headers=("Key", "Value"))` — flattens a
  YAML/TOML/JSON file (optionally a dotted `section=`) into a two-column markdown
  table.
- `env_table(path=".env.example")` — parses `KEY=value` lines (using preceding `#`
  comment lines as descriptions) into a Variable/Default/Description table.
- `entry_points_table()` — table of `[project.scripts]` from `pyproject.toml`.

## Links

- `gh_link(path="", text=None)` — `{project.owner}/{project.repo}`-relative GitHub
  URL, e.g. `gh_link("issues", "Issues")`. Needs `project.owner`/`project.repo` set
  or autodetected from the git remote.
- `spdx_link(license_id=None)` — link to the SPDX page for the project's license
  (or an explicit id).
- `my_ha_link(redirect, text=None, **params)` — a "My Home Assistant" redirect
  button/link, e.g. `my_ha_link("hacs_repository", owner=..., repository=...)`.

## Layout

- `callout(kind, text)` — a GitHub alert (`kind` is `note`/`tip`/`important`/
  `warning`/`caution`).
- `details(summary, body, open=False)` — a `<details>` collapsible.
- `center(content)` — centers a block of markdown/HTML.
- `columns(cells, align="center")` — lays out a list of markdown cells
  side-by-side (as an HTML table row).
- `contributors(logins=None, size=64)` — avatar grid; `logins` defaults to
  contributors autodetected from the repo.

## Ecosystem-specific

- `flow_install_cmd()` — Flow Launcher plugin install command.
- `mc_versions()`, `mod_dependencies()` — Minecraft mod metadata tables (from
  Gradle `gradle.properties`).
- `related_repos()` — table from config's `related:` list
  (`[{repo: other-tool, description: ...}]`).
- `pyversions_list(sep=", ")` — joined list of supported Python versions.

## Build metadata

- `git_sha(short=True)`, `git_tag()`, `today()` — current commit/tag/date. These
  change on every render, so a checked-in `README.md` that used them will always
  show as stale to `readwright check` unless re-rendered immediately before the
  check (e.g. in a release job). Avoid them in a README that's committed and
  linted by CI; fine for a render step that runs at publish time.

## Context available in every template

- `project.*` — `name`, `owner`, `repo`, `tagline`, `pypi`, `npm`, `license`,
  `ci_workflow`, plus anything autodetected from the git remote / `LICENSE` /
  manifest file. `gh_link()` and badge presets read from here.
- `vars.*` — free-form values from config's `vars:` map, for anything
  project-specific that doesn't fit elsewhere.
