from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


class MetaError(ValueError):
    """Raised when package metadata cannot be parsed."""


@dataclass(frozen=True)
class PackageMeta:
    install_dependencies: str | None = None
    source_repository: str | None = None
    source_ref: str | None = None
    build_vsix: str | None = None
    run_tests: str | None = None
    coverage_enabled: bool | None = None
    coverage_tool: str | None = None
    coverage_analyzer: str | None = None
    coverage_file: str | None = None
    coverage_threshold: float | None = None


def load_package_meta(package: str, meta_dir: Path) -> PackageMeta:
    path = meta_dir / f"{package}.yml"
    if not path.exists():
        return PackageMeta()
    return parse_package_meta(path)


def parse_package_meta(path: Path) -> PackageMeta:
    raw = _parse_simple_yaml(path)
    coverage = raw.get("coverage", {})
    if coverage is None:
        coverage = {}
    if not isinstance(coverage, dict):
        raise MetaError("coverage must be a mapping")

    return PackageMeta(
        install_dependencies=_optional_string(raw, "install_dependencies"),
        source_repository=_optional_string(raw, "source_repository"),
        source_ref=_optional_string(raw, "source_ref"),
        build_vsix=_optional_string(raw, "build_vsix"),
        run_tests=_optional_string(raw, "run_tests"),
        coverage_enabled=_optional_bool(raw, "coverage_enabled")
        if "coverage_enabled" in raw
        else _optional_bool(coverage, "enabled"),
        coverage_tool=_optional_string(raw, "coverage_tool")
        or _optional_string(coverage, "tool"),
        coverage_analyzer=_optional_string(raw, "coverage_analyzer")
        or _optional_string(coverage, "analyzer"),
        coverage_file=_optional_string(raw, "coverage_file")
        or _optional_string(coverage, "file"),
        coverage_threshold=_optional_float(raw, "coverage_threshold")
        or _optional_float(coverage, "threshold"),
    )


def _parse_simple_yaml(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current_section: dict[str, Any] | None = None

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if indent not in (0, 2):
            raise MetaError(f"{path}:{line_number}: only 0 or 2 spaces indentation is supported")

        key, value = _split_key_value(path, line_number, raw_line.strip())
        if indent == 0:
            if value == "":
                section: dict[str, Any] = {}
                result[key] = section
                current_section = section
            else:
                result[key] = _parse_scalar(value)
                current_section = None
        else:
            if current_section is None:
                raise MetaError(f"{path}:{line_number}: nested key without section")
            current_section[key] = _parse_scalar(value)

    return result


def _split_key_value(path: Path, line_number: int, line: str) -> tuple[str, str]:
    if ":" not in line:
        raise MetaError(f"{path}:{line_number}: expected key: value")
    key, value = line.split(":", 1)
    key = key.strip()
    if not key:
        raise MetaError(f"{path}:{line_number}: empty key")
    return key, value.strip()


def _parse_scalar(value: str) -> str | float:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    try:
        return float(value)
    except ValueError:
        return value


def _optional_string(values: dict[str, Any], key: str) -> str | None:
    value = values.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise MetaError(f"{key} must be a string")
    return value


def _optional_float(values: dict[str, Any], key: str) -> float | None:
    value = values.get(key)
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError as exc:
            raise MetaError(f"{key} must be a number") from exc
    raise MetaError(f"{key} must be a number")


def _optional_bool(values: dict[str, Any], key: str) -> bool | None:
    value = values.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in ("true", "yes", "on"):
            return True
        if lowered in ("false", "no", "off"):
            return False
    raise MetaError(f"{key} must be a boolean")
