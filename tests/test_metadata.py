import subprocess

from mkreadme.metadata import detect, parse_github_remote


def test_parse_github_remote_ssh_and_https():
    assert parse_github_remote("git@github.com:Octo/demo-repo.git") == ("Octo", "demo-repo")
    assert parse_github_remote("https://github.com/Octo/demo-repo") == ("Octo", "demo-repo")
    assert parse_github_remote("https://github.com/Octo/demo-repo.git") == ("Octo", "demo-repo")
    assert parse_github_remote("ssh://git@github.com/Octo/demo-repo.git") == ("Octo", "demo-repo")
    assert parse_github_remote("https://gitlab.com/Octo/demo-repo") is None


def test_detect_full_python_repo(tmp_repo):
    meta = detect(tmp_repo)
    assert meta.owner == "Octo"
    assert meta.repo == "demo-repo"
    assert meta.name == "demo-pkg"
    assert meta.version == "1.2.3"
    assert meta.tagline == "A demo package"
    assert meta.license == "MIT"
    assert meta.pypi == "demo-pkg"
    assert meta.python_versions == ["3.11", "3.12"]
    assert meta.project_type == "python"
    assert meta.url == "https://github.com/Octo/demo-repo"


def test_detect_node_repo(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"name": "@octo/widget", "version": "0.4.0", "description": "Widgets", "license": "ISC"}'
    )
    meta = detect(tmp_path)
    assert meta.name == "@octo/widget"
    assert meta.npm == "@octo/widget"
    assert meta.version == "0.4.0"
    assert meta.tagline == "Widgets"
    assert meta.license == "ISC"
    assert meta.project_type == "node"
    assert meta.owner is None
    assert meta.repo is None


def test_detect_bare_dir_uses_dirname(tmp_path):
    meta = detect(tmp_path)
    assert meta.name == tmp_path.name
    assert meta.project_type == "generic"
    assert meta.license is None
    assert meta.url is None


def test_detect_license_from_file_when_pyproject_lacks_it(tmp_path):
    (tmp_path / "LICENSE").write_text("Apache License\nVersion 2.0, January 2004\n")
    assert detect(tmp_path).license == "Apache-2.0"


def test_detect_git_without_remote(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    meta = detect(tmp_path)
    assert meta.owner is None and meta.repo is None
