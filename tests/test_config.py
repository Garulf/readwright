import pytest
import yaml

from mkreadme.config import BadgeSpec, Config, load_config, load_user_config, resolve


def test_defaults_from_autodetect(tmp_repo):
    cfg = resolve(tmp_repo)
    assert cfg.project.name == "demo-pkg"
    assert cfg.project.owner == "Octo"
    assert cfg.output == "README.md"
    assert cfg.template == "README.md.j2"
    assert cfg.screenshots.dir == "docs/screenshots"
    assert cfg.badges == []
    assert cfg.donate == []


def test_readme_yaml_overrides_autodetect(tmp_repo):
    (tmp_repo / "readme.yaml").write_text(
        yaml.safe_dump(
            {
                "project": {"name": "Demo!", "tagline": "custom"},
                "badges": ["pypi", {"preset": "ci", "workflow": "test.yml"}],
                "donate": ["kofi"],
                "donate_handles": {"kofi": "octo"},
                "vars": {"channel": "#demo"},
            }
        )
    )
    cfg = resolve(tmp_repo)
    assert cfg.project.name == "Demo!"
    assert cfg.project.tagline == "custom"
    assert cfg.project.owner == "Octo"
    assert cfg.badges == [
        BadgeSpec(preset="pypi"),
        BadgeSpec(preset="ci", options={"workflow": "test.yml"}),
    ]
    assert cfg.donate == ["kofi"]
    assert cfg.donate_handles["kofi"] == "octo"
    assert cfg.vars["channel"] == "#demo"


def test_tool_readme_in_pyproject(tmp_repo):
    with (tmp_repo / "pyproject.toml").open("a") as fh:
        fh.write(
            '\n[tool.readme]\nbadges = ["license"]\n[tool.readme.project]\ntagline = "from toml"\n'
        )
    cfg = resolve(tmp_repo)
    assert cfg.badges == [BadgeSpec(preset="license")]
    assert cfg.project.tagline == "from toml"


def test_readme_yaml_wins_over_pyproject(tmp_repo):
    with (tmp_repo / "pyproject.toml").open("a") as fh:
        fh.write('\n[tool.readme]\nbadges = ["license"]\n')
    (tmp_repo / "readme.yaml").write_text("badges: [pypi]\n")
    assert resolve(tmp_repo).badges == [BadgeSpec(preset="pypi")]


def test_explicit_config_path(tmp_repo):
    custom = tmp_repo / "cfg" / "r.yaml"
    custom.parent.mkdir()
    custom.write_text("output: docs/README.md\n")
    assert resolve(tmp_repo, config_path=custom).output == "docs/README.md"


def test_load_config_rejects_unknown_keys(tmp_repo):
    (tmp_repo / "readme.yaml").write_text("bogus: 1\n")
    with pytest.raises(ValueError, match="bogus"):
        load_config(tmp_repo)


def test_user_config_loaded_from_xdg(no_user_config):
    (no_user_config / "mkreadme").mkdir()
    (no_user_config / "mkreadme" / "config.yaml").write_text(
        "donate: [kofi]\ndonate_handles: {kofi: me}\nproject: {owner: Me}\n"
    )
    user = load_user_config()
    assert user is not None
    assert user.donate == ["kofi"]
    assert user.project.owner == "Me"


def test_user_config_absent(no_user_config):
    assert load_user_config() is None


def test_resolve_ignores_user_config_by_default(tmp_repo, no_user_config):
    (no_user_config / "mkreadme").mkdir()
    (no_user_config / "mkreadme" / "config.yaml").write_text("donate: [kofi]\n")
    assert resolve(tmp_repo).donate == []
    assert resolve(tmp_repo, use_user_config=True).donate == ["kofi"]


def test_repo_config_wins_over_user_config(tmp_repo, no_user_config):
    (no_user_config / "mkreadme").mkdir()
    (no_user_config / "mkreadme" / "config.yaml").write_text(
        "donate: [kofi]\ndonate_handles: {kofi: me, patreon: me}\n"
    )
    (tmp_repo / "readme.yaml").write_text("donate: [patreon]\ndonate_handles: {patreon: repo}\n")
    cfg = resolve(tmp_repo, use_user_config=True)
    assert cfg.donate == ["patreon"]
    assert cfg.donate_handles == {"kofi": "me", "patreon": "repo"}


def test_config_model_roundtrip():
    cfg = Config.model_validate({"badges": ["pypi"], "screenshots": {"width": 400}})
    assert cfg.screenshots.width == 400
    assert cfg.screenshots.style == "markdown"


def test_config_sources_reports_both(tmp_repo):
    from mkreadme.config import config_sources

    assert config_sources(tmp_repo) == []
    (tmp_repo / "readme.yaml").write_text("badges: [pypi]\n")
    with (tmp_repo / "pyproject.toml").open("a") as fh:
        fh.write("\n[tool.readme]\nbadges = []\n")
    assert config_sources(tmp_repo) == ["readme.yaml", "pyproject.toml [tool.readme]"]
