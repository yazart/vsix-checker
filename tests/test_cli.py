from pathlib import Path

import pytest

from vsix_check_pipeline import cli
from vsix_check_pipeline.pipeline import PipelineError, PipelineReport


def test_main_prints_success_report(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def fake_run_pipeline(config):
        assert config.package == "pub.ext"
        assert config.version == "1.2.3"
        assert config.install_command == "npm ci"
        assert config.source_repository is None
        assert config.source_ref is None
        assert config.build_command == "npx @vscode/vsce package --out dist/source.vsix"
        assert config.coverage_enabled is True
        assert config.coverage_tool is None
        assert config.coverage_analyzer == "lcov"
        return PipelineReport(
            marketplace_archive=Path("/tmp/marketplace.zip"),
            repository_url="https://github.com/acme/ext",
            checked_out_ref="v1.2.3",
            built_vsix=Path("/tmp/source.vsix"),
            coverage_percent=91.25,
        )

    monkeypatch.setattr(cli, "run_pipeline", fake_run_pipeline)

    exit_code = cli.main(["pub.ext", "1.2.3"])

    output = capsys.readouterr()
    assert exit_code == 0
    assert "VSIX check passed" in output.out
    assert "Coverage: 91.25%" in output.out


def test_main_returns_error_code(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def fake_run_pipeline(config):
        raise PipelineError("archive mismatch")

    monkeypatch.setattr(cli, "run_pipeline", fake_run_pipeline)

    exit_code = cli.main(["pub.ext", "1.2.3"])

    output = capsys.readouterr()
    assert exit_code == 1
    assert "archive mismatch" in output.err


def test_main_uses_package_meta(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    meta_dir = tmp_path / "meta"
    meta_dir.mkdir()
    (meta_dir / "pub.ext.yml").write_text(
        "\n".join(
            [
                "install_dependencies: pnpm install --frozen-lockfile",
                "source_repository: https://github.com/acme/ext.git",
                "source_ref: release/1.2.3",
                "build_vsix: pnpm package",
                "run_tests: pnpm test:coverage",
                "coverage:",
                "  enabled: false",
                "  tool: c8",
                "  analyzer: nyc",
                "  file: reports/lcov.info",
                "  threshold: 85",
            ]
        ),
        encoding="utf-8",
    )
    seen_configs = []
    monkeypatch.setattr(cli, "run_pipeline", lambda config: seen_configs.append(config) or PipelineReport(
        marketplace_archive=Path("/tmp/marketplace.zip"),
        repository_url="https://github.com/acme/ext",
        checked_out_ref="v1.2.3",
        built_vsix=Path("/tmp/source.vsix"),
        coverage_percent=91.25,
    ))

    exit_code = cli.main(["pub.ext", "1.2.3", "--meta-dir", str(meta_dir)])

    assert exit_code == 0
    assert seen_configs[0].install_command == "pnpm install --frozen-lockfile"
    assert seen_configs[0].source_repository == "https://github.com/acme/ext.git"
    assert seen_configs[0].source_ref == "release/1.2.3"
    assert seen_configs[0].build_command == "pnpm package"
    assert seen_configs[0].test_command == "pnpm test:coverage"
    assert seen_configs[0].coverage_enabled is False
    assert seen_configs[0].coverage_tool == "c8"
    assert seen_configs[0].coverage_analyzer == "nyc"
    assert seen_configs[0].coverage_file == "reports/lcov.info"
    assert seen_configs[0].coverage_threshold == 85


def test_main_skip_coverage_flag_overrides_default(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_configs = []
    monkeypatch.setattr(cli, "run_pipeline", lambda config: seen_configs.append(config) or PipelineReport(
        marketplace_archive=Path("/tmp/marketplace.zip"),
        repository_url="https://github.com/acme/ext",
        checked_out_ref="v1.2.3",
        built_vsix=Path("/tmp/source.vsix"),
        coverage_percent=None,
    ))

    exit_code = cli.main(["pub.ext", "1.2.3", "--skip-coverage"])

    assert exit_code == 0
    assert seen_configs[0].coverage_enabled is False


def test_main_coverage_analyzer_flag_overrides_meta(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_configs = []
    monkeypatch.setattr(cli, "run_pipeline", lambda config: seen_configs.append(config) or PipelineReport(
        marketplace_archive=Path("/tmp/marketplace.zip"),
        repository_url="https://github.com/acme/ext",
        checked_out_ref="v1.2.3",
        built_vsix=Path("/tmp/source.vsix"),
        coverage_percent=90,
    ))

    exit_code = cli.main(["pub.ext", "1.2.3", "--coverage-analyzer", "c8"])

    assert exit_code == 0
    assert seen_configs[0].coverage_analyzer == "c8"


def test_main_coverage_tool_flag_overrides_default(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_configs = []
    monkeypatch.setattr(cli, "run_pipeline", lambda config: seen_configs.append(config) or PipelineReport(
        marketplace_archive=Path("/tmp/marketplace.zip"),
        repository_url="https://github.com/acme/ext",
        checked_out_ref="v1.2.3",
        built_vsix=Path("/tmp/source.vsix"),
        coverage_percent=None,
        coverage_tool="vitest",
    ))

    exit_code = cli.main(["pub.ext", "1.2.3", "--coverage-tool", "vitest"])

    assert exit_code == 0
    assert seen_configs[0].coverage_tool == "vitest"
