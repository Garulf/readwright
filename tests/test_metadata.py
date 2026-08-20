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


def test_detect_rust(tmp_path):
    (tmp_path / "Cargo.toml").write_text(
        '[package]\nname = "crabby"\nversion = "2.0.0"\ndescription = "Crab"\n'
        'license = "MIT OR Apache-2.0"\n'
    )
    meta = detect(tmp_path)
    assert (meta.name, meta.version, meta.tagline, meta.project_type) == (
        "crabby",
        "2.0.0",
        "Crab",
        "rust",
    )
    assert meta.crate == "crabby" and meta.license == "MIT OR Apache-2.0"


def test_detect_go(tmp_path):
    (tmp_path / "go.mod").write_text("module github.com/octo/gotool\n\ngo 1.22\n")
    meta = detect(tmp_path)
    assert meta.name == "gotool" and meta.go_module == "github.com/octo/gotool"
    assert meta.project_type == "go"


def test_detect_dotnet(tmp_path):
    (tmp_path / "Tool.csproj").write_text(
        "<Project><PropertyGroup><PackageId>Octo.Tool</PackageId><Version>1.0.1</Version>"
        "<Description>Dot</Description><PackAsTool>true</PackAsTool></PropertyGroup></Project>"
    )
    meta = detect(tmp_path)
    assert meta.name == "Octo.Tool" and meta.nuget == "Octo.Tool" and meta.version == "1.0.1"
    assert meta.tagline == "Dot" and meta.project_type == "dotnet"


def test_detect_gradle_minecraft_mod(tmp_path):
    (tmp_path / "build.gradle").write_text("plugins { id 'net.neoforged.moddev' }\n")
    (tmp_path / "gradle.properties").write_text(
        "mod_id=headglance\nmod_name=HeadGlance\nmod_version=0.3.1\n"
        "mod_description=Freelook\nminecraft_version=1.21.1\nmod_license=MIT\n"
    )
    meta = detect(tmp_path)
    assert meta.name == "HeadGlance" and meta.version == "0.3.1" and meta.tagline == "Freelook"
    assert meta.project_type == "minecraft-mod" and meta.minecraft_version == "1.21.1"
    assert meta.mod_id == "headglance" and meta.license == "MIT"


def test_detect_plain_gradle(tmp_path):
    (tmp_path / "build.gradle.kts").write_text('version = "1.0"\n')
    (tmp_path / "settings.gradle.kts").write_text('rootProject.name = "libby"\n')
    meta = detect(tmp_path)
    assert meta.project_type == "gradle" and meta.name == "libby"


def test_detect_hacs(tmp_path):
    (tmp_path / "hacs.json").write_text('{"name": "Motion Card", "render_readme": true}')
    meta = detect(tmp_path)
    assert meta.project_type == "hacs" and meta.name == "Motion Card"


def test_detect_hacs_with_package_json_prefers_hacs_type(tmp_path):
    (tmp_path / "hacs.json").write_text('{"name": "Motion Card"}')
    (tmp_path / "package.json").write_text('{"name": "motion-card", "version": "1.0.0"}')
    meta = detect(tmp_path)
    assert meta.project_type == "hacs" and meta.name == "Motion Card" and meta.version == "1.0.0"
