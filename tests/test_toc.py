from mkreadme.toc import TOC_TOKEN, build_toc, github_slug, insert_toc


def test_github_slug():
    assert github_slug("Installation") == "installation"
    assert github_slug("Quick Start & Usage") == "quick-start--usage"
    assert github_slug("`mkreadme render`") == "mkreadme-render"
    assert github_slug("  Ünïcode Title 2.0 ") == "ünïcode-title-20"


def test_build_toc_levels_and_indent():
    md = "# Title\n\n## Install\ntext\n### From PyPI\n## Usage\n#### too deep\n"
    assert build_toc(md) == "- [Install](#install)\n  - [From PyPI](#from-pypi)\n- [Usage](#usage)"


def test_build_toc_skips_code_fences_and_duplicates():
    md = "## Usage\n```\n## not a heading\n```\n## Usage\n"
    assert build_toc(md) == "- [Usage](#usage)\n- [Usage](#usage-1)"


def test_insert_toc_replaces_token_and_excludes_headings_above_it():
    md = f"# Title\n\n## Intro\n\n{TOC_TOKEN}\n\n## Install\n## Usage\n"
    out = insert_toc(md)
    assert TOC_TOKEN not in out
    assert "- [Install](#install)\n- [Usage](#usage)" in out
    assert "[Intro]" not in out


def test_insert_toc_noop_without_token():
    assert insert_toc("## A\n") == "## A\n"


def test_build_toc_depth_and_h1():
    from mkreadme.toc import toc_token

    md = "# Top\n## A\n### B\n#### C\n"
    assert build_toc(md, 1, 2) == "- [Top](#top)\n  - [A](#a)"
    assert build_toc(md, 2, 2) == "- [A](#a)"
    assert build_toc(md, 2, 4) == "- [A](#a)\n  - [B](#b)\n    - [C](#c)"
    assert insert_toc(toc_token(2, 2) + "\n## A\n### B\n") == "- [A](#a)\n## A\n### B\n"
