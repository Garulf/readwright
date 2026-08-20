import pytest

from mkreadme.config import Config, ScreenshotsConfig
from mkreadme.images import ImageHelper, MissingImageError


def helper(tmp_repo, warnings=None, **shots) -> ImageHelper:
    cfg = Config(screenshots=ScreenshotsConfig(**shots))
    return ImageHelper(tmp_repo, cfg, warn=(warnings.append if warnings is not None else None))


def test_screenshot_markdown(tmp_repo):
    md = helper(tmp_repo).screenshot("main")
    assert md == "![Main](docs/screenshots/main.png)"


def test_screenshot_custom_alt_and_width_forces_html(tmp_repo):
    md = helper(tmp_repo).screenshot("main", alt="Main view", width=600)
    assert md == '<img src="docs/screenshots/main.png" alt="Main view" width="600">'


def test_screenshot_html_style_uses_config_width(tmp_repo):
    md = helper(tmp_repo, style="html", width=500).screenshot("main")
    assert md == '<img src="docs/screenshots/main.png" alt="Main" width="500">'


def test_screenshot_html_style_without_width(tmp_repo):
    md = helper(tmp_repo, style="html", width=None).screenshot("main")
    assert md == '<img src="docs/screenshots/main.png" alt="Main">'


def test_screenshot_dark_light_picture(tmp_repo):
    md = helper(tmp_repo).screenshot("settings")
    dark, light = "docs/screenshots/settings-dark.png", "docs/screenshots/settings-light.png"
    assert md == (
        "<picture>\n"
        f'  <source media="(prefers-color-scheme: dark)" srcset="{dark}">\n'
        f'  <source media="(prefers-color-scheme: light)" srcset="{light}">\n'
        f'  <img src="{light}" alt="Settings">\n'
        "</picture>"
    )


def test_screenshot_picture_with_width(tmp_repo):
    md = helper(tmp_repo).screenshot("settings", width=300)
    assert 'alt="Settings" width="300">' in md


def test_screenshot_extension_fallback_order(tmp_repo):
    shots = tmp_repo / "docs" / "screenshots"
    (shots / "demo.gif").write_bytes(b"GIF89a")
    (shots / "demo.webp").write_bytes(b"RIFF")
    assert helper(tmp_repo).screenshot("demo").endswith("demo.gif)")


def test_screenshot_missing_warns_and_returns_empty(tmp_repo):
    warnings = []
    assert helper(tmp_repo, warnings).screenshot("nope") == ""
    assert warnings and "nope" in warnings[0] and "docs/screenshots" in warnings[0]


def test_screenshot_missing_strict_raises(tmp_repo):
    cfg = Config(strict=True)
    with pytest.raises(MissingImageError, match="nope"):
        ImageHelper(tmp_repo, cfg).screenshot("nope")


def test_screenshot_custom_dir(tmp_repo):
    (tmp_repo / "img").mkdir()
    (tmp_repo / "img" / "x.png").write_bytes(b"x")
    assert helper(tmp_repo, dir="img").screenshot("x") == "![X](img/x.png)"


def test_image_explicit_path(tmp_repo):
    h = helper(tmp_repo)
    assert h.image("docs/screenshots/main.png", "Alt") == "![Alt](docs/screenshots/main.png)"
    assert h.image("docs/screenshots/main.png", "Alt", width=200) == (
        '<img src="docs/screenshots/main.png" alt="Alt" width="200">'
    )
    assert h.image("https://example.com/x.png", "Remote") == "![Remote](https://example.com/x.png)"


def test_image_missing_local_warns_but_still_emits(tmp_repo):
    warnings = []
    assert helper(tmp_repo, warnings).image("nope.png", "x") == "![x](nope.png)"
    assert warnings and "nope.png" in warnings[0]


def test_screenshots_gallery(tmp_repo):
    (tmp_repo / "docs" / "screenshots" / "zeta-view.png").write_bytes(b"x")
    md = helper(tmp_repo).screenshots()
    lines = md.splitlines()
    assert lines[0] == "<table>"
    assert lines[-1] == "</table>"
    assert md.count("<tr>") == 2
    assert md.count("<td") == 3
    assert md.index("main.png") < md.index("settings-light.png") < md.index("zeta-view.png")
    assert "<picture>" in md
    assert 'alt="Zeta View"' in md
    assert 'width="720"' in md


def test_screenshots_gallery_columns_and_empty(tmp_repo):
    assert helper(tmp_repo).screenshots(columns=1).count("<tr>") == 2
    for f in (tmp_repo / "docs" / "screenshots").iterdir():
        f.unlink()
    warnings = []
    assert helper(tmp_repo, warnings).screenshots() == ""
    assert warnings


def test_screenshots_gallery_missing_dir(tmp_path):
    warnings = []
    assert helper(tmp_path, warnings).screenshots() == ""
    assert warnings and "docs/screenshots" in warnings[0]


def test_screenshots_captions_order_and_subdir(tmp_repo):
    shots = tmp_repo / "docs" / "screenshots"
    (shots / "captions.yaml").write_text("main: The main window\n")
    md = helper(tmp_repo).screenshots(order=["settings", "main"])
    assert md.index("settings-light.png") < md.index("main.png")
    assert "<sub>The main window</sub>" in md and 'alt="The main window"' in md
    assert "<sub>Settings</sub>" in md
    md = helper(tmp_repo).screenshots(captions={"settings": "Prefs"}, show_captions=False)
    assert 'alt="Prefs"' in md and "<sub>" not in md
    sub = shots / "mobile"
    sub.mkdir()
    (sub / "phone.png").write_bytes(b"x")
    md = helper(tmp_repo).screenshots(subdir="mobile")
    assert "docs/screenshots/mobile/phone.png" in md and "main.png" not in md
    assert (
        helper(tmp_repo).screenshot("mobile/phone") == "![Phone](docs/screenshots/mobile/phone.png)"
    )


def test_screenshots_order_unknown_warns(tmp_repo):
    warnings = []
    helper(tmp_repo, warnings).screenshots(order=["nope"])
    assert warnings and "nope" in warnings[0]
