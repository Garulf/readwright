from pathlib import Path

import pytest
import yaml
from jinja2 import TemplateNotFound, UndefinedError

from mkreadme.config import resolve
from mkreadme.renderer import Renderer, marker
from mkreadme.toc import TOC_TOKEN

GOLDEN = Path(__file__).parent / "golden"


def write_config(repo: Path, **data) -> None:
    (repo / "readme.yaml").write_text(yaml.safe_dump(data))


def render(repo: Path, user_templates: Path | None = None):
    return Renderer(repo, resolve(repo), user_templates=user_templates).render()


def test_falls_back_to_packaged_base_template(tmp_repo):
    result = render(tmp_repo)
    assert result.template_name == "base.md.j2"
    assert result.text.startswith(marker("base.md.j2"))
    assert "# demo-pkg" in result.text
    assert "pip install demo-pkg" in result.text
    assert "## Screenshots" in result.text


def test_golden_base_render(tmp_repo):
    write_config(
        tmp_repo,
        badges=["pypi", "python", "license", {"preset": "ci", "workflow": "test.yml"}],
        donate=["kofi"],
        donate_handles={"kofi": "octo"},
        vars={"usage": "Run `demo-pkg --help`."},
    )
    expected = (GOLDEN / "base.md").read_text()
    assert render(tmp_repo).text == expected


def test_repo_template_extends_base_and_uses_helpers(tmp_repo):
    (tmp_repo / "README.md.j2").write_text(
        '{% extends "base.md.j2" %}\n'
        "{% block toc %}{{ toc() }}\n\n{% endblock %}\n"
        "{% block usage %}## Usage\n\n{{ screenshot('main', width=400) }}\n\n"
        "{{ badge('github-stars') }} {{ shield('a', 'b') }}\n\n{% endblock %}\n"
    )
    result = render(tmp_repo)
    assert result.template_name == "README.md.j2"
    assert result.text.startswith(marker("README.md.j2"))
    assert TOC_TOKEN not in result.text
    assert "- [Screenshots](#screenshots)\n- [Installation](#installation)\n- [Usage](#usage)" in (
        result.text
    )
    assert '<img src="docs/screenshots/main.png" alt="Main" width="400">' in result.text
    assert "img.shields.io/github/stars/Octo/demo-repo" in result.text
    assert "img.shields.io/badge/a-b-blue" in result.text
    assert result.user_templates == []


def test_repo_partial_shadows_packaged(tmp_repo):
    partial = tmp_repo / "templates" / "partials" / "contributing.md.j2"
    partial.parent.mkdir(parents=True)
    partial.write_text("## Help out\n\nPlease.\n")
    text = render(tmp_repo).text
    assert "## Help out" in text and "## Contributing" not in text


def test_user_template_dir_is_tracked(tmp_repo, tmp_path):
    user = tmp_path / "user-templates" / "partials"
    user.mkdir(parents=True)
    (user / "donate.md.j2").write_text("Buy me a coffee!\n\n")
    result = render(tmp_repo, user_templates=user.parent)
    assert "Buy me a coffee!" in result.text
    assert result.user_templates == ["partials/donate.md.j2"]


def test_user_template_dir_missing_is_fine(tmp_repo, tmp_path):
    assert render(tmp_repo, user_templates=tmp_path / "nope").user_templates == []


def test_undefined_variable_is_an_error(tmp_repo):
    (tmp_repo / "README.md.j2").write_text("{{ nope }}\n")
    with pytest.raises(UndefinedError):
        render(tmp_repo)


def test_explicit_missing_template_raises(tmp_repo):
    write_config(tmp_repo, template="missing.md.j2")
    with pytest.raises(TemplateNotFound):
        render(tmp_repo)


def test_warnings_collected(tmp_repo):
    (tmp_repo / "README.md.j2").write_text("{{ screenshot('nope') }}\n")
    result = render(tmp_repo)
    assert result.warnings and "nope" in result.warnings[0]


def test_vars_and_project_exposed(tmp_repo):
    write_config(tmp_repo, vars={"greeting": "hi"})
    (tmp_repo / "README.md.j2").write_text(
        "{{ vars.greeting }} {{ project.owner }} {{ project.url }}\n"
    )
    assert render(tmp_repo).text.endswith("hi Octo https://github.com/Octo/demo-repo\n")


def test_collapse_blank_lines_preserves_fences():
    from mkreadme.renderer import collapse_blank_lines

    text = "a\n\n\n\nb\n```\nx\n\n\n\ny\n```\n\n\n"
    assert collapse_blank_lines(text) == "a\n\nb\n```\nx\n\n\n\ny\n```\n"


def test_empty_blocks_leave_no_double_blank_lines(tmp_repo):
    text = render(tmp_repo).text
    assert "\n\n\n" not in text


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        ({"Cargo.toml": '[package]\nname = "crab"\n'}, "cargo install crab"),
        ({"go.mod": "module github.com/o/gotool\n"}, "go install github.com/o/gotool@latest"),
        (
            {
                "A.csproj": "<Project><PropertyGroup><PackageId>A</PackageId>"
                "</PropertyGroup></Project>"
            },
            "dotnet tool install --global A",
        ),
        (
            {"build.gradle": "", "gradle.properties": "mod_id=x\nminecraft_version=1.21.1\n"},
            "drop the jar into your `mods` folder (Minecraft 1.21.1)",
        ),
        ({"hacs.json": '{"name": "Card"}'}, "Install through [HACS]"),
    ],
)
def test_install_partial_per_project_type(tmp_path, files, expected):
    for name, content in files.items():
        (tmp_path / name).write_text(content)
    assert expected in render(tmp_path).text


def test_changelog_and_toc_depth_globals(tmp_repo):
    (tmp_repo / "CHANGELOG.md").write_text("## 1.0\n- first\n## 0.9\n- old\n")
    (tmp_repo / "README.md.j2").write_text(
        "{{ toc(1, 2) }}\n# Top\n## Latest\n### deep\n{{ changelog() }}\n"
    )
    text = render(tmp_repo).text
    assert "- [Top](#top)\n  - [Latest](#latest)" in text and "[deep]" not in text
    assert "## 1.0\n- first" in text and "0.9" not in text


def test_extra_template_paths_and_sources(tmp_repo, tmp_path):
    shared = tmp_path / "shared" / "partials"
    shared.mkdir(parents=True)
    (shared / "contributing.md.j2").write_text("## Shared contributing\n")
    write_config(tmp_repo, templates=[str(tmp_path / "shared")])
    result = render(tmp_repo, user_templates=tmp_path / "nope")
    assert "## Shared contributing" in result.text
    assert result.sources["partials/contributing.md.j2"] == str(tmp_path / "shared")
    assert result.sources["base.md.j2"] == "mkreadme"
    assert result.sources["partials/header.md.j2"] == "mkreadme"


def test_pkg_template_path(tmp_repo, tmp_path):
    write_config(tmp_repo, templates=["pkg:mkreadme/templates"])
    result = render(tmp_repo, user_templates=tmp_path / "nope")
    assert result.sources["base.md.j2"] == "pkg:mkreadme/templates"


def test_repo_template_beats_extra_paths(tmp_repo, tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "README.md.j2").write_text("shared\n")
    (tmp_repo / "README.md.j2").write_text("repo\n")
    write_config(tmp_repo, templates=[str(shared)])
    assert render(tmp_repo).text.endswith("repo\n")


def test_install_partial_flow_plugin(tmp_path):
    (tmp_path / "plugin.json").write_text('{"ActionKeyword": "x", "Name": "My Plugin"}')
    assert "pm install My Plugin" in render(tmp_path).text
