from mkreadme.changelog import latest_entries, split_entries

LOG = """# Changelog

## [Unreleased]
- wip

## [1.1.0] - 2026-08-01
### Added
- thing

## [1.0.0] - 2026-07-01
- initial
"""


def test_split_entries_skips_unreleased():
    entries = split_entries(LOG)
    assert len(entries) == 2
    assert entries[0].startswith("## [1.1.0]") and entries[0].endswith("- thing")


def test_latest_entries(tmp_path):
    (tmp_path / "CHANGELOG.md").write_text(LOG)
    assert latest_entries(tmp_path).startswith("## [1.1.0]")
    assert latest_entries(tmp_path, 2).count("## [") == 2
    assert latest_entries(tmp_path, path="nope.md") == ""


def test_latest_entries_missing(tmp_path):
    assert latest_entries(tmp_path) == ""
