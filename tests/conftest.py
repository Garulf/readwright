import subprocess
from pathlib import Path

import pytest

PYPROJECT = """\
[project]
name = "demo-pkg"
version = "1.2.3"
description = "A demo package"
requires-python = ">=3.11"
license = "MIT"
classifiers = [
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]
"""

PNG_BYTES = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "git@github.com:Octo/demo-repo.git"],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    (tmp_path / "LICENSE").write_text("MIT License\n\nCopyright (c) 2026 Octo\n")
    shots = tmp_path / "docs" / "screenshots"
    shots.mkdir(parents=True)
    (shots / "main.png").write_bytes(PNG_BYTES)
    (shots / "settings-dark.png").write_bytes(PNG_BYTES)
    (shots / "settings-light.png").write_bytes(PNG_BYTES)
    return tmp_path


@pytest.fixture
def no_user_config(monkeypatch, tmp_path: Path) -> Path:
    home = tmp_path / "xdg-home"
    home.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home))
    return home
