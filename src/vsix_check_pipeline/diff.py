from __future__ import annotations

import filecmp
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DirectoryDiff:
    added: tuple[Path, ...]
    removed: tuple[Path, ...]
    changed: tuple[Path, ...]

    @property
    def is_empty(self) -> bool:
        return not self.added and not self.removed and not self.changed

    def format(self) -> str:
        lines: list[str] = []
        for label, paths in (
            ("added", self.added),
            ("removed", self.removed),
            ("changed", self.changed),
        ):
            for path in paths:
                lines.append(f"{label}: {path.as_posix()}")
        return "\n".join(lines)


def compare_directories(expected: Path, actual: Path) -> DirectoryDiff:
    expected_files = _collect_files(expected)
    actual_files = _collect_files(actual)

    removed = tuple(sorted(expected_files - actual_files))
    added = tuple(sorted(actual_files - expected_files))
    common = sorted(expected_files & actual_files)
    changed = tuple(
        path
        for path in common
        if not filecmp.cmp(expected / path, actual / path, shallow=False)
    )

    return DirectoryDiff(added=added, removed=removed, changed=changed)


def _collect_files(root: Path) -> set[Path]:
    return {
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file()
    }
