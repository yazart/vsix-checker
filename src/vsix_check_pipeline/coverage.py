from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


class CoverageError(ValueError):
    """Raised when coverage data cannot be read or fails a threshold."""


CoverageAnalyzer = Literal["lcov", "c8", "istanbul", "nyc"]
SUPPORTED_ANALYZERS: tuple[CoverageAnalyzer, ...] = ("lcov", "c8", "istanbul", "nyc")
CoverageTool = Literal["c8", "vitest", "nyc", "jest", "istanbul", "tap"]
SUPPORTED_TOOLS: tuple[CoverageTool, ...] = ("c8", "vitest", "nyc", "jest", "istanbul", "tap")


@dataclass(frozen=True)
class CoverageSummary:
    covered_lines: int
    total_lines: int

    @property
    def percent(self) -> float:
        if self.total_lines == 0:
            return 0.0
        return self.covered_lines / self.total_lines * 100


@dataclass(frozen=True)
class CoverageToolPreset:
    report: tuple[str, ...]
    check: tuple[str, ...]
    coverage_report_folder: str


def get_coverage_tool_preset(tool: str, threshold: float = 80) -> CoverageToolPreset:
    normalized = tool.lower()
    value = _format_threshold(threshold)
    presets = {
        "c8": CoverageToolPreset(
            report=("npx c8 report --reporter=text",),
            check=(
                f"npx c8 check-coverage --branches {value} --functions {value} --lines {value} --statements {value}",
            ),
            coverage_report_folder="coverage",
        ),
        "vitest": CoverageToolPreset(
            report=("npx vitest --coverage --run",),
            check=(
                "npx vitest --run --coverage "
                f"--coverage.thresholds.lines={value} "
                f"--coverage.thresholds.functions={value} "
                f"--coverage.thresholds.branches={value} "
                f"--coverage.thresholds.statements={value}",
            ),
            coverage_report_folder="coverage",
        ),
        "nyc": CoverageToolPreset(
            report=("npx nyc report",),
            check=(
                f"npx nyc check-coverage --branches {value} --functions {value} --lines {value} --statements {value}",
            ),
            coverage_report_folder=".nyc_output",
        ),
        "jest": CoverageToolPreset(
            report=("npx istanbul report text",),
            check=(
                f"npx istanbul check-coverage --statements {value} --functions {value} --branches {value} --lines {value}",
            ),
            coverage_report_folder="coverage",
        ),
        "istanbul": CoverageToolPreset(
            report=("npx istanbul report text",),
            check=(
                f"npx istanbul check-coverage --statements {value} --functions {value} --branches {value} --lines {value}",
            ),
            coverage_report_folder="coverage",
        ),
        "tap": CoverageToolPreset(
            report=("npx tap report --coverage-report=text --show-full-coverage",),
            check=(),
            coverage_report_folder=".tap/coverage",
        ),
    }
    if normalized not in presets:
        raise CoverageError(
            f"unsupported coverage tool '{tool}', expected one of: {', '.join(SUPPORTED_TOOLS)}"
        )
    return presets[normalized]


def read_coverage_summary(path: Path, analyzer: str) -> CoverageSummary:
    normalized = analyzer.lower()
    if normalized == "lcov":
        return read_lcov_summary(path)
    if normalized in ("c8", "istanbul", "nyc"):
        return read_json_summary(path, normalized)
    raise CoverageError(
        f"unsupported coverage analyzer '{analyzer}', expected one of: {', '.join(SUPPORTED_ANALYZERS)}"
    )


def read_lcov_summary(path: Path) -> CoverageSummary:
    if not path.exists():
        raise CoverageError(f"coverage file does not exist: {path}")

    covered = 0
    total = 0
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.startswith("DA:"):
            continue
        try:
            _, payload = raw_line.split(":", 1)
            _, hits_raw = payload.split(",", 1)
            hits = int(hits_raw)
        except ValueError as exc:
            raise CoverageError(f"invalid LCOV line: {raw_line}") from exc
        total += 1
        if hits > 0:
            covered += 1

    if total == 0:
        raise CoverageError(f"coverage file contains no line data: {path}")

    return CoverageSummary(covered_lines=covered, total_lines=total)


def read_json_summary(path: Path, analyzer: str) -> CoverageSummary:
    if not path.exists():
        raise CoverageError(f"coverage file does not exist: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CoverageError(f"invalid {analyzer} coverage summary: {path}") from exc

    lines = _get_nested_mapping(payload, "total", "lines")
    total = _read_json_number(lines, "total")
    covered = _read_json_number(lines, "covered")
    if total <= 0:
        raise CoverageError(f"{analyzer} coverage summary contains no line data: {path}")
    return CoverageSummary(covered_lines=int(covered), total_lines=int(total))


def assert_coverage_at_least(path: Path, threshold: float, analyzer: str = "lcov") -> CoverageSummary:
    summary = read_coverage_summary(path, analyzer)
    if summary.percent < threshold:
        raise CoverageError(
            f"coverage {summary.percent:.2f}% is below required {threshold:.2f}%"
        )
    return summary


def _get_nested_mapping(payload: dict[str, Any], *keys: str) -> dict[str, Any]:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict) or not isinstance(current.get(key), dict):
            raise CoverageError(f"coverage summary is missing {'.'.join(keys)}")
        current = current[key]
    return current


def _read_json_number(payload: dict[str, Any], key: str) -> float:
    value = payload.get(key)
    if not isinstance(value, (int, float)):
        raise CoverageError(f"coverage summary field '{key}' must be a number")
    return float(value)


def _format_threshold(threshold: float) -> str:
    value = float(threshold)
    if value.is_integer():
        return str(int(value))
    return str(value)
