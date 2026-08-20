import subprocess

import pytest

from mkreadme.config import Config, ProjectInfo, RelatedRepo
from mkreadme.helpers import Helpers, fenced, md_table


def make(tmp_repo, warnings=None, **cfg) -> Helpers:
    project = cfg.pop("project", None) or ProjectInfo(
        name="demo-pkg",
        owner="Octo",
        repo="demo-repo",
        license="MIT",
        python_versions=["3.11", "3.12"],
        minecraft_version="1.21.1",
        flow_plugin="Demo Plugin",
    )
    config = Config(project=project, **cfg)
    return Helpers(tmp_repo, config, warn=(warnings.append if warnings is not None else None))


def test_fenced_and_md_table():
    assert fenced("x", "sh") == "```sh\nx\n```"
    assert fenced("```inner```").startswith("````")
    assert md_table(["a", "b"], [["1", "x|y"]]) == "| a | b |\n| --- | --- |\n| 1 | x\\|y |"
    assert md_table(["a"], []) == ""


def test_include_file_code_block_snippet(tmp_repo):
    (tmp_repo / "docs").mkdir(exist_ok=True)
    (tmp_repo / "docs" / "usage.md").write_text("Use it.\n")
    (tmp_repo / "ex.py").write_text("x = 1\n# begin\n    def f():\n        pass\n# end\n")
    h = make(tmp_repo)
    assert h.include_file("docs/usage.md") == "Use it."
    assert h.code_block("docs/usage.md") == "```md\nUse it.\n```"
    assert h.snippet("ex.py", "# begin", "# end") == "```py\ndef f():\n    pass\n```"
    assert h.snippet("ex.py", "# begin", "# end", language="", dedent=False) == (
        "    def f():\n        pass"
    )
    warnings = []
    assert make(tmp_repo, warnings).include_file("nope") == ""
    assert make(tmp_repo, warnings).snippet("ex.py", "a", "b") == ""
    assert len(warnings) == 2


def test_cli_help_gated(tmp_repo):
    with pytest.raises(PermissionError, match="allow_exec"):
        make(tmp_repo).cli_help("echo hi")
    out = make(tmp_repo, allow_exec=True).cli_help("echo hi")
    assert out == "```text\nhi\n```"
    warnings = []
    assert make(tmp_repo, warnings, allow_exec=True).cli_help("definitely-not-a-cmd") == ""
    assert warnings
    with pytest.raises(FileNotFoundError):
        make(tmp_repo, allow_exec=True, strict=True).cli_help("definitely-not-a-cmd")


def test_config_table_and_env_table(tmp_repo):
    (tmp_repo / "opts.yaml").write_text("a: 1\nb:\n  c: [x, y]\n  d: true\n")
    h = make(tmp_repo)
    table = h.config_table("opts.yaml")
    assert "| `a` |" not in table
    assert "| a | `1` |" in table and "| b.c | `x`, `y` |" in table and "| b.d | true |" in table
    assert h.config_table("opts.yaml", section="b").startswith("| Key | Value |")
    with (tmp_repo / "pyproject.toml").open("a") as fh:
        fh.write("\n[tool.demo]\nflag = 1\n")
    assert "| flag | `1` |" in h.config_table("pyproject.toml", section="tool.demo")
    (tmp_repo / ".env.example").write_text(
        "# API token\nTOKEN=\n\n# Port to bind\nPORT=8080\nJUNK\n"
    )
    env = h.env_table()
    assert "| `TOKEN` |  | API token |" in env and "| `PORT` | `8080` | Port to bind |" in env


def test_links(tmp_repo):
    h = make(tmp_repo)
    assert h.gh_link() == "https://github.com/Octo/demo-repo"
    assert h.gh_link("issues", "Issues") == "[Issues](https://github.com/Octo/demo-repo/issues)"
    assert h.spdx_link() == "[MIT](https://spdx.org/licenses/MIT.html)"
    assert h.my_ha_link("hacs_repository", owner="Octo", repository="demo-repo").startswith(
        "[![Open your Home Assistant instance](https://my.home-assistant.io/badges/hacs_repository.svg)]"
    )
    assert h.my_ha_link("integrations", "Open") == (
        "[Open](https://my.home-assistant.io/redirect/integrations/)"
    )
    with pytest.raises(ValueError):
        make(tmp_repo, project=ProjectInfo()).gh_link()


def test_layout_helpers(tmp_repo):
    h = make(tmp_repo)
    assert h.details("More", "body") == "<details>\n<summary>More</summary>\n\nbody\n\n</details>"
    assert h.details("More", "body", open=True).startswith("<details open>")
    assert h.callout("note", "line1\n\nline2") == "> [!NOTE]\n> line1\n>\n> line2"
    with pytest.raises(ValueError):
        h.callout("bogus", "x")
    assert h.center("<b>x</b>") == '<p align="center">\n<b>x</b>\n</p>'
    cols = h.columns(["a", "b"])
    assert cols.count("<td") == 2 and cols.startswith("<table>")


def test_logo_and_video(tmp_repo):
    warnings = []
    h = make(tmp_repo, warnings)
    assert h.logo() == "" and warnings
    (tmp_repo / "docs" / "logo.svg").write_text("<svg/>")
    assert h.logo() == '<img src="docs/logo.svg" alt="demo-pkg" width="120">'
    assert h.logo(width=None, alt="L") == '<img src="docs/logo.svg" alt="L">'
    (tmp_repo / "logo-dark.png").write_bytes(b"x")
    (tmp_repo / "logo-light.png").write_bytes(b"x")
    assert "<picture>" in h.logo() and 'srcset="logo-dark.png"' in h.logo()
    (tmp_repo / "docs" / "screenshots" / "demo.mp4").write_bytes(b"x")
    assert h.video("demo") == '<video src="docs/screenshots/demo.mp4" controls muted loop></video>'
    (tmp_repo / "docs" / "demo2.gif").write_bytes(b"x")
    assert h.video("demo2", width=300) == '<img src="docs/demo2.gif" alt="demo2" width="300">'
    assert h.video("https://x/y.mp4").startswith('<video src="https://x/y.mp4"')
    assert h.video("missing") == ""


def test_contributors(tmp_repo):
    h = make(tmp_repo)
    md = h.contributors(["octo", "cat"], size=32)
    assert md.count("<a href=") == 2 and "github.com/octo.png?size=32" in md
    (tmp_repo / ".all-contributorsrc").write_text('{"contributors": [{"login": "zed"}]}')
    assert "github.com/zed" in h.contributors()
    warnings = []
    (tmp_repo / ".all-contributorsrc").unlink()
    assert make(tmp_repo, warnings).contributors() == "" and warnings


def test_project_helpers(tmp_repo):
    h = make(
        tmp_repo,
        related=[RelatedRepo(repo="other", description="sibling"), RelatedRepo(repo="x/y")],
    )
    assert h.pyversions_list() == "3.11, 3.12"
    assert h.pyversions_list(" / ") == "3.11 / 3.12"
    with (tmp_repo / "pyproject.toml").open("a") as fh:
        fh.write('\n[project.scripts]\ndemo = "demo.cli:app"\n')
    assert "| `demo` | `demo.cli:app` |" in h.entry_points_table()
    assert h.flow_install_cmd() == "```text\npm install Demo Plugin\n```"
    assert h.mc_versions() == "1.21.1"
    table = h.related_repos()
    assert "[other](https://github.com/Octo/other) | sibling" in table
    assert "[x/y](https://github.com/x/y)" in table


def test_mod_dependencies(tmp_repo):
    meta = tmp_repo / "src" / "main" / "resources" / "META-INF"
    meta.mkdir(parents=True)
    (meta / "neoforge.mods.toml").write_text(
        '[[dependencies.demo]]\nmodId = "neoforge"\ntype = "required"\nversionRange = "[21,)"\n'
        '[[dependencies.demo]]\nmodId = "create"\ntype = "optional"\nversionRange = "*"\n'
    )
    table = make(tmp_repo).mod_dependencies()
    assert "| `neoforge` | required | `[21,)` |" in table and "`create` | optional" in table
    warnings = []
    (meta / "neoforge.mods.toml").unlink()
    assert make(tmp_repo, warnings).mod_dependencies() == "" and warnings


def test_git_and_today(tmp_repo):
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "init",
        ],
        cwd=tmp_repo,
        check=True,
    )
    subprocess.run(["git", "tag", "v9.9.9"], cwd=tmp_repo, check=True)
    h = make(tmp_repo)
    assert len(h.git_sha()) in (7, 8, 9, 10, 11, 12)
    assert len(h.git_sha(short=False)) == 40
    assert h.git_tag() == "v9.9.9"
    assert len(h.today()) == 10 and h.today("%Y").isdigit()


def test_helpers_available_in_templates(tmp_repo):
    from mkreadme.config import resolve
    from mkreadme.renderer import Renderer

    (tmp_repo / "README.md.j2").write_text(
        "{{ callout('tip', 'hi') }}\n{{ gh_link('issues', 'Issues') }}\n{{ spdx_link() }}\n"
    )
    text = Renderer(tmp_repo, resolve(tmp_repo)).render().text
    assert "> [!TIP]" in text and "[Issues](https://github.com/Octo/demo-repo/issues)" in text
    assert "[MIT](https://spdx.org/licenses/MIT.html)" in text


def test_unsplash_helper(tmp_repo):
    h = make(tmp_repo)
    md = h.unsplash(
        "photo-1518770660439-4636190af475",
        alt="Circuit board",
        width=800,
        credit="Alexandre Debiève",
        user="alexkixa",
        photo_id="FO7JIlwjOtU",
    )
    assert md.startswith('<a href="https://unsplash.com/photos/FO7JIlwjOtU"><img src="')
    assert (
        "images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&q=80&w=800" in md
    )
    assert 'alt="Circuit board" width="800">' in md
    assert (
        'Photo by <a href="https://unsplash.com/@alexkixa?utm_source=demo-repo&utm_medium=referral">'
        in md
    )
    assert "Alexandre Debi" in md and 'utm_medium=referral">Unsplash</a></sub>' in md
    url_form = h.unsplash(
        "https://images.unsplash.com/photo-1518770660439-4636190af475?w=1&q=2",
        credit="X",
        height=300,
    )
    assert "&h=300" in url_form and "photo-1518770660439-4636190af475?" in url_form
    warnings = []
    bare = make(tmp_repo, warnings).unsplash("1518770660439-4636190af475", width=None)
    assert bare.startswith("<img src=") and "width=" not in bare and "Photo by" not in bare
    assert warnings and "attribution" in warnings[0]
    with pytest.raises(ValueError, match="photo id"):
        h.unsplash("https://unsplash.com/photos/FO7JIlwjOtU")


def test_banner_helper(tmp_repo):
    from mkreadme.config import BannerConfig

    assert make(tmp_repo).banner() == ""
    h = make(
        tmp_repo,
        banner=BannerConfig(
            unsplash="photo-1518770660439-4636190af475", credit="A", user="a", width=600
        ),
    )
    assert "Photo by" in h.banner() and 'width="600"' in h.banner()
    (tmp_repo / "docs" / "banner.png").write_bytes(b"x")
    h = make(tmp_repo, banner=BannerConfig(image="docs/banner.png", link="https://x", width=None))
    assert h.banner() == '<a href="https://x"><img src="docs/banner.png" alt="demo-pkg"></a>'
    warnings = []
    make(tmp_repo, warnings, banner=BannerConfig(image="nope.png")).banner()
    assert warnings and "nope.png" in warnings[0]
