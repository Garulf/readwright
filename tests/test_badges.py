import pytest

from mkreadme.badges import BadgeRegistry, shield
from mkreadme.config import BadgeSpec, Config, CustomBadge, ProjectInfo


def make_registry(**overrides) -> BadgeRegistry:
    cfg = Config(
        project=ProjectInfo(
            name="demo-pkg",
            owner="Octo",
            repo="demo-repo",
            pypi="demo-pkg",
            npm="@octo/widget",
            license="MIT",
            ci_workflow="ci.yml",
        ),
        **overrides,
    )
    return BadgeRegistry(cfg)


def test_shield_basic():
    md = shield("Discord", "chat", "5865F2", link="https://discord.gg/x")
    assert md == (
        "[![Discord](https://img.shields.io/badge/Discord-chat-5865F2)](https://discord.gg/x)"
    )


def test_shield_escapes_and_options():
    md = shield("my label", "a-b_c", logo="github", style="flat-square")
    assert "https://img.shields.io/badge/my%20label-a--b__c-blue?" in md
    assert "logo=github" in md and "style=flat-square" in md
    assert md.startswith("![my label](")


@pytest.mark.parametrize(
    ("preset", "img", "link"),
    [
        ("pypi", "https://img.shields.io/pypi/v/demo-pkg", "https://pypi.org/project/demo-pkg/"),
        (
            "pypi-downloads",
            "https://img.shields.io/pypi/dm/demo-pkg",
            "https://pypi.org/project/demo-pkg/",
        ),
        (
            "python",
            "https://img.shields.io/pypi/pyversions/demo-pkg",
            "https://pypi.org/project/demo-pkg/",
        ),
        (
            "license",
            "https://img.shields.io/github/license/Octo/demo-repo",
            "https://github.com/Octo/demo-repo/blob/main/LICENSE",
        ),
        (
            "ci",
            "https://img.shields.io/github/actions/workflow/status/Octo/demo-repo/ci.yml",
            "https://github.com/Octo/demo-repo/actions/workflows/ci.yml",
        ),
        (
            "codecov",
            "https://img.shields.io/codecov/c/github/Octo/demo-repo",
            "https://codecov.io/gh/Octo/demo-repo",
        ),
        (
            "npm",
            "https://img.shields.io/npm/v/%40octo%2Fwidget",
            "https://www.npmjs.com/package/@octo/widget",
        ),
        (
            "github-release",
            "https://img.shields.io/github/v/release/Octo/demo-repo",
            "https://github.com/Octo/demo-repo/releases/latest",
        ),
        (
            "github-stars",
            "https://img.shields.io/github/stars/Octo/demo-repo",
            "https://github.com/Octo/demo-repo/stargazers",
        ),
        (
            "pre-commit",
            "https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit",
            "https://github.com/pre-commit/pre-commit",
        ),
        (
            "ruff",
            "https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json",
            "https://github.com/astral-sh/ruff",
        ),
    ],
)
def test_builtin_presets(preset, img, link):
    md = make_registry().render(preset)
    assert md.startswith("[![")
    assert f"]({img})" in md
    assert md.endswith(f"]({link})")


def test_version_badge():
    cfg = Config(project=ProjectInfo(version="1.2.3", owner="O", repo="R"))
    md = BadgeRegistry(cfg).render("version")
    assert "badge/version-1.2.3-informational" in md and md.endswith("(https://github.com/O/R)")


def test_ci_workflow_override():
    md = make_registry().render("ci", workflow="test.yml")
    assert "/Octo/demo-repo/test.yml" in md


def test_missing_metadata_raises_helpful_error():
    registry = BadgeRegistry(Config(project=ProjectInfo(name="x")))
    with pytest.raises(ValueError, match="pypi"):
        registry.render("pypi")
    with pytest.raises(ValueError, match="owner"):
        registry.render("github-stars")


def test_unknown_preset_raises():
    with pytest.raises(ValueError, match="unknown badge preset 'nope'"):
        make_registry().render("nope")


def test_custom_preset_from_config():
    reg = make_registry(
        badges_custom={
            "discord": CustomBadge(
                label="Discord", message="chat", color="5865F2", link="https://discord.gg/x"
            )
        }
    )
    assert reg.render("discord") == shield("Discord", "chat", "5865F2", link="https://discord.gg/x")
    assert "discord" in reg.names()


@pytest.mark.parametrize(
    ("preset", "handle", "img_fragment", "link"),
    [
        ("kofi", "octo", "Ko--fi", "https://ko-fi.com/octo"),
        ("buymeacoffee", "octo", "Buy%20Me%20a%20Coffee", "https://www.buymeacoffee.com/octo"),
        ("github-sponsors", "Octo", "github/sponsors/Octo", "https://github.com/sponsors/Octo"),
        ("patreon", "octo", "Patreon", "https://patreon.com/octo"),
        ("paypal", "octo", "PayPal", "https://paypal.me/octo"),
    ],
)
def test_donation_presets(preset, handle, img_fragment, link):
    reg = make_registry(donate_handles={preset: handle})
    md = reg.render(preset)
    assert img_fragment in md
    assert md.endswith(f"]({link})")


def test_donation_handle_kw_override_and_missing():
    reg = make_registry()
    assert reg.render("kofi", handle="other").endswith("(https://ko-fi.com/other)")
    with pytest.raises(ValueError, match="donate_handles.kofi"):
        reg.render("kofi")


def test_badges_and_donate_badges_from_config():
    reg = make_registry(
        badges=[BadgeSpec(preset="pypi"), BadgeSpec(preset="ci", options={"workflow": "t.yml"})],
        donate=["kofi"],
        donate_handles={"kofi": "octo"},
    )
    all_badges = reg.render_all()
    assert all_badges.count("[![") == 2
    assert " " in all_badges and "\n" not in all_badges
    assert reg.render_donate().endswith("(https://ko-fi.com/octo)")
    assert make_registry().render_donate() == ""


def test_names_lists_builtin_and_custom():
    names = make_registry().names()
    assert "pypi" in names and "kofi" in names


def test_badge_style_config_and_kw():
    reg = make_registry(badges_style="flat-square", badges=[BadgeSpec(preset="pypi")])
    assert "pypi/v/demo-pkg?style=flat-square)" in reg.render("pypi")
    assert "logo=pre-commit&style=flat-square" in reg.render("pre-commit")
    assert "style=for-the-badge" in reg.render("pypi", style="for-the-badge")
    assert "style=flat-square" in reg.render_all()
    assert "style=plastic" in reg.render_all(style="plastic")
    assert "style=" not in make_registry().render("pypi")


def test_modrinth_curseforge_hacs_badges():
    reg = BadgeRegistry(
        Config(
            project=ProjectInfo(modrinth="demo-mod", curseforge="12345", ha_min_version="2024.6")
        )
    )
    assert "modrinth/dt/demo-mod" in reg.render("modrinth")
    assert reg.render("modrinth", slug="other").endswith("(https://modrinth.com/mod/other)")
    assert "curseforge/dt/12345" in reg.render("curseforge")
    assert "HACS-Custom-41BDF5" in reg.render("hacs") and "HACS-Default" in reg.render(
        "hacs", kind="Default"
    )
    assert "Home%20Assistant-2024.6%2B-03A9F4" in reg.render("ha-version")
    with pytest.raises(ValueError, match="modrinth"):
        BadgeRegistry(Config()).render("modrinth")
