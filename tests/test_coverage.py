from pathlib import Path

import pytest

from vsix_check_pipeline.coverage import (
    CoverageError,
    assert_coverage_at_least,
    get_coverage_tool_preset,
    read_coverage_summary,
    read_lcov_summary,
)


def test_read_lcov_summary_counts_hit_lines(tmp_path: Path) -> None:
    lcov = tmp_path / "lcov.info"
    lcov.write_text(
        "\n".join(
            [
                "TN:",
                "SF:example.ts",
                "DA:1,1",
                "DA:2,0",
                "DA:3,4",
                "end_of_record",
            ]
        ),
        encoding="utf-8",
    )

    summary = read_lcov_summary(lcov)

    assert summary.covered_lines == 2
    assert summary.total_lines == 3
    assert summary.percent == pytest.approx(66.666, rel=0.01)


def test_assert_coverage_at_least_rejects_low_coverage(tmp_path: Path) -> None:
    lcov = tmp_path / "lcov.info"
    lcov.write_text("DA:1,1\nDA:2,0\n", encoding="utf-8")

    with pytest.raises(CoverageError, match="below required"):
        assert_coverage_at_least(lcov, 80)


@pytest.mark.parametrize("analyzer", ["c8", "istanbul", "nyc"])
def test_read_json_summary_for_common_node_analyzers(tmp_path: Path, analyzer: str) -> None:
    summary_file = tmp_path / "coverage-summary.json"
    summary_file.write_text(
        '{"total":{"lines":{"total":10,"covered":9,"skipped":0,"pct":90}}}',
        encoding="utf-8",
    )

    summary = read_coverage_summary(summary_file, analyzer)

    assert summary.covered_lines == 9
    assert summary.total_lines == 10
    assert summary.percent == 90


def test_read_coverage_summary_rejects_unknown_analyzer(tmp_path: Path) -> None:
    with pytest.raises(CoverageError, match="unsupported coverage analyzer"):
        read_coverage_summary(tmp_path / "coverage.json", "unknown")


def test_get_coverage_tool_preset_uses_threshold_in_check_command() -> None:
    preset = get_coverage_tool_preset("c8", 82.5)

    assert preset.report == ("npx c8 report --reporter=text",)
    assert preset.check == (
        "npx c8 check-coverage --branches 82.5 --functions 82.5 --lines 82.5 --statements 82.5",
    )
    assert preset.coverage_report_folder == "coverage"


def test_get_coverage_tool_preset_supports_tap_without_check_command() -> None:
    preset = get_coverage_tool_preset("tap")

    assert preset.report == ("npx tap report --coverage-report=text --show-full-coverage",)
    assert preset.check == ()
    assert preset.coverage_report_folder == ".tap/coverage"


def test_get_coverage_tool_preset_rejects_unknown_tool() -> None:
    with pytest.raises(CoverageError, match="unsupported coverage tool"):
        get_coverage_tool_preset("unknown")
