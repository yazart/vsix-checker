from pathlib import Path

from vsix_check_pipeline.diff import compare_directories


def test_compare_directories_reports_added_removed_and_changed(tmp_path: Path) -> None:
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    expected.mkdir()
    actual.mkdir()

    (expected / "same.txt").write_text("same", encoding="utf-8")
    (actual / "same.txt").write_text("same", encoding="utf-8")
    (expected / "removed.txt").write_text("removed", encoding="utf-8")
    (actual / "added.txt").write_text("added", encoding="utf-8")
    (expected / "changed.txt").write_text("before", encoding="utf-8")
    (actual / "changed.txt").write_text("after", encoding="utf-8")

    diff = compare_directories(expected, actual)

    assert diff.added == (Path("added.txt"),)
    assert diff.removed == (Path("removed.txt"),)
    assert diff.changed == (Path("changed.txt"),)


def test_compare_directories_accepts_identical_trees(tmp_path: Path) -> None:
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    (expected / "nested").mkdir(parents=True)
    (actual / "nested").mkdir(parents=True)
    (expected / "nested" / "file.txt").write_text("same", encoding="utf-8")
    (actual / "nested" / "file.txt").write_text("same", encoding="utf-8")

    diff = compare_directories(expected, actual)

    assert diff.is_empty
