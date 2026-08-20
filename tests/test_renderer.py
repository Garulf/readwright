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
