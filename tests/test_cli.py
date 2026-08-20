import yaml
from typer.testing import CliRunner

from mkreadme.cli import app
from mkreadme.renderer import MARKER_PREFIX

runner = CliRunner()


def run(*args):
    return runner.invoke(app, [str(a) for a in args])


def test_version():
    result = run("--version")
    assert result.exit_code == 0 and result.output.startswith("mkreadme ")


def test_render_writes_and_reports_unchanged(tmp_repo):
    result = run("render", "-C", tmp_repo)
    assert result.exit_code == 0, result.output
    assert "README.md updated from base.md.j2" in result.output
    text = (tmp_repo / "README.md").read_text()
    assert text.startswith(MARKER_PREFIX) and "# demo-pkg" in text
    again = run("render", "-C", tmp_repo)
    assert "README.md unchanged" in again.output


def test_render_custom_output_and_config(tmp_repo):
    cfg = tmp_repo / "c.yaml"
    cfg.write_text("output: docs/README.md\n")
    assert run("render", "-C", tmp_repo, "-c", cfg).exit_code == 0
    assert (tmp_repo / "docs" / "README.md").is_file()


def test_render_strict_fails_on_missing_screenshot(tmp_repo):
    (tmp_repo / "README.md.j2").write_text("{{ screenshot('nope') }}\n")
    assert run("render", "-C", tmp_repo).exit_code == 0
    result = run("render", "-C", tmp_repo, "--strict")
    assert result.exit_code == 1 and "nope" in result.output


def test_render_reports_template_errors(tmp_repo):
    (tmp_repo / "README.md.j2").write_text("{{ undefined_thing }}\n")
    result = run("render", "-C", tmp_repo)
    assert result.exit_code == 1 and "UndefinedError" in result.output


def test_render_reports_config_errors(tmp_repo):
    (tmp_repo / "readme.yaml").write_text("bogus: 1\n")
    result = run("render", "-C", tmp_repo)
    assert result.exit_code == 1 and "bogus" in result.output


def test_check_missing_stale_and_fresh(tmp_repo):
    missing = run("check", "-C", tmp_repo)
    assert missing.exit_code == 1 and "does not exist" in missing.output
    run("render", "-C", tmp_repo)
    assert run("check", "-C", tmp_repo).exit_code == 0
    readme = tmp_repo / "README.md"
    readme.write_text(readme.read_text().replace("# demo-pkg", "# edited"))
    stale = run("check", "-C", tmp_repo)
    assert stale.exit_code == 1
    assert "-# edited" in stale.output and "+# demo-pkg" in stale.output
    assert "out of date" in stale.output


def test_check_unmanaged_readme_warns_exit_zero(tmp_repo):
    (tmp_repo / "README.md").write_text("# hand written\n")
    result = run("check", "-C", tmp_repo)
    assert result.exit_code == 0 and "not managed" in result.output


def test_check_warns_about_user_templates(tmp_repo, no_user_config):
    user = no_user_config / "mkreadme" / "templates" / "partials"
    user.mkdir(parents=True)
    (user / "donate.md.j2").write_text("coffee\n")
    run("render", "-C", tmp_repo)
    result = run("check", "-C", tmp_repo)
    assert result.exit_code == 0 and "user-level template" in result.output


def test_init_scaffolds_and_refuses_overwrite(tmp_repo, no_user_config):
    result = run("init", "-C", tmp_repo)
    assert result.exit_code == 0, result.output
    data = yaml.safe_load((tmp_repo / "readme.yaml").read_text())
    assert data["project"]["name"] == "demo-pkg"
    assert data["project"]["owner"] == "Octo"
    assert "version" not in data["project"]
    assert data["badges"] == []
    template = (tmp_repo / "README.md.j2").read_text()
    assert template.startswith('{% extends "base.md.j2" %}') and "{% block usage %}" in template
    assert run("render", "-C", tmp_repo).exit_code == 0
    assert "demo-pkg" in (tmp_repo / "README.md").read_text()
    again = run("init", "-C", tmp_repo)
    assert again.exit_code == 1 and "already exists" in again.output


def test_init_bakes_in_user_config(tmp_repo, no_user_config):
    (no_user_config / "mkreadme").mkdir()
    (no_user_config / "mkreadme" / "config.yaml").write_text(
        "donate: [kofi]\ndonate_handles: {kofi: me}\nproject: {owner: Overridden}\n"
    )
    assert run("init", "-C", tmp_repo).exit_code == 0
    data = yaml.safe_load((tmp_repo / "readme.yaml").read_text())
    assert data["donate"] == ["kofi"] and data["donate_handles"] == {"kofi": "me"}
    assert data["project"]["owner"] == "Octo"


def test_render_user_config_flag(tmp_repo, no_user_config):
    (no_user_config / "mkreadme").mkdir()
    (no_user_config / "mkreadme" / "config.yaml").write_text(
        "donate: [kofi]\ndonate_handles: {kofi: me}\n"
    )
    run("render", "-C", tmp_repo)
    assert "ko-fi.com/me" not in (tmp_repo / "README.md").read_text()
    run("render", "-C", tmp_repo, "--user-config")
    assert "ko-fi.com/me" in (tmp_repo / "README.md").read_text()


def test_badges_lists_presets(tmp_repo):
    (tmp_repo / "readme.yaml").write_text(
        "badges_custom: {discord: {label: Discord, message: chat}}\n"
    )
    result = run("badges", "-C", tmp_repo)
    assert result.exit_code == 0
    for name in ("pypi", "kofi", "discord"):
        assert name in result.output


def test_render_to_stdout(tmp_repo):
    result = run("render", "-C", tmp_repo, "-o", "-")
    assert result.exit_code == 0 and result.output.startswith(MARKER_PREFIX)
    assert not (tmp_repo / "README.md").exists()


def test_render_refuses_unmanaged_without_force(tmp_repo):
    (tmp_repo / "README.md").write_text("# handwritten\n")
    result = run("render", "-C", tmp_repo)
    assert result.exit_code == 1 and "--force" in result.output
    assert (tmp_repo / "README.md").read_text() == "# handwritten\n"
    assert run("render", "-C", tmp_repo, "--force").exit_code == 0
    assert (tmp_repo / "README.md").read_text().startswith(MARKER_PREFIX)


def test_render_verbose_lists_sources(tmp_repo):
    result = run("render", "-C", tmp_repo, "-v")
    assert "template base.md.j2 <- mkreadme" in result.output


def test_config_conflict_warning(tmp_repo):
    (tmp_repo / "readme.yaml").write_text("badges: []\n")
    with (tmp_repo / "pyproject.toml").open("a") as fh:
        fh.write("\n[tool.readme]\nbadges = []\n")
    result = run("render", "-C", tmp_repo)
    assert "both readme.yaml and pyproject.toml [tool.readme] exist" in result.output


def test_init_from_readme(tmp_repo, no_user_config):
    (tmp_repo / "README.md").write_text(
        "# Demo\n\nIntro text.\n\n## Usage\n\nRun it {{ not jinja }}.\n"
    )
    result = run("init", "-C", tmp_repo, "--from-readme")
    assert result.exit_code == 0, result.output
    template = (tmp_repo / "README.md.j2").read_text()
    assert "{% raw %}" in template and "Intro text." in template and "# Demo" not in template
    assert "{% block install %}{% endblock %}" in template
    text = (tmp_repo / "README.md").read_text()
    assert run("check", "-C", tmp_repo).exit_code == 0
    assert "Run it {{ not jinja }}." in text and "## Installation" not in text
    assert text.startswith(MARKER_PREFIX) and "# demo-pkg" in text


def test_init_from_readme_requires_unmanaged(tmp_repo, no_user_config):
    assert run("init", "-C", tmp_repo, "--from-readme").exit_code == 1
    run("render", "-C", tmp_repo)
    (tmp_repo / "README.md.j2").unlink() if (tmp_repo / "README.md.j2").exists() else None
    result = run("init", "-C", tmp_repo, "--from-readme")
    assert result.exit_code == 1 and "already managed" in result.output


def test_init_pyproject(tmp_repo, no_user_config):
    result = run("init", "-C", tmp_repo, "--pyproject")
    assert result.exit_code == 0, result.output
    assert not (tmp_repo / "readme.yaml").exists()
    text = (tmp_repo / "pyproject.toml").read_text()
    assert "[tool.readme]" in text and 'owner = "Octo"' in text
    assert run("render", "-C", tmp_repo).exit_code == 0
    again = run("init", "-C", tmp_repo, "--pyproject")
    assert again.exit_code == 1


def test_blocks_and_show(tmp_repo):
    result = run("blocks", "-C", tmp_repo)
    assert result.exit_code == 0
    for name in ("header", "usage", "license", "partials/install.md.j2"):
        assert name in result.output
    shown = run("show", "partials/license.md.j2", "-C", tmp_repo)
    assert shown.exit_code == 0 and "{% if project.license %}" in shown.output
    assert run("show", "nope.j2", "-C", tmp_repo).exit_code == 1


def test_watch_paths(tmp_repo):
    from mkreadme.cli import watch_paths
    from mkreadme.config import resolve

    (tmp_repo / "README.md.j2").write_text("x\n")
    paths = watch_paths(tmp_repo, resolve(tmp_repo))
    names = {p.name for p in paths}
    assert {"README.md.j2", "pyproject.toml", "screenshots"} <= names
