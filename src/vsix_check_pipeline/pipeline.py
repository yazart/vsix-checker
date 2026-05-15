from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .coverage import CoverageError, assert_coverage_at_least, get_coverage_tool_preset
from .diff import compare_directories
from .git import checkout_ref, checkout_version_tag, clone_repository
from .marketplace import (
    VsixError,
    download_vsix,
    extract_vsix,
    read_repository_url,
    rename_vsix_to_zip,
)


class PipelineError(RuntimeError):
    """Raised when a pipeline step fails."""


@dataclass(frozen=True)
class PipelineConfig:
    package: str
    version: str
    work_dir: Path
    install_command: str | None
    source_repository: str | None
    source_ref: str | None
    build_command: str
    test_command: str
    coverage_enabled: bool
    coverage_tool: str | None
    coverage_analyzer: str
    coverage_file: str
    coverage_threshold: float
    keep_work_dir: bool = False


@dataclass(frozen=True)
class PipelineReport:
    marketplace_archive: Path
    repository_url: str
    checked_out_ref: str
    built_vsix: Path
    coverage_percent: float | None
    coverage_tool: str | None = None


def run_pipeline(config: PipelineConfig) -> PipelineReport:
    work_dir = config.work_dir.resolve()
    marketplace_vsix = work_dir / "marketplace.vsix"
    marketplace_extract = work_dir / "marketplace"
    repository_dir = work_dir / "repository"
    source_extract = work_dir / "source"

    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)

    try:
        download_vsix(config.package, config.version, marketplace_vsix)
        marketplace_archive = rename_vsix_to_zip(marketplace_vsix)
        extract_vsix(marketplace_archive, marketplace_extract)
        repository_url = config.source_repository or read_repository_url(marketplace_extract)

        clone_repository(repository_url, repository_dir)
        checked_out_ref = (
            checkout_ref(repository_dir, config.source_ref)
            if config.source_ref
            else checkout_version_tag(repository_dir, config.version)
        )

        if config.install_command:
            _run_shell(config.install_command, repository_dir)
        built_vsix = _build_vsix(repository_dir, config.build_command)
        extract_vsix(built_vsix, source_extract)

        diff = compare_directories(marketplace_extract, source_extract)
        if not diff.is_empty:
            raise PipelineError("VSIX contents differ:\n" + diff.format())

        _run_shell(config.test_command, repository_dir)
        coverage_percent: float | None = None
        coverage_tool: str | None = None
        if config.coverage_enabled:
            if config.coverage_tool:
                _run_coverage_tool(config.coverage_tool, config.coverage_threshold, repository_dir)
                coverage_tool = config.coverage_tool
            else:
                coverage = assert_coverage_at_least(
                    repository_dir / config.coverage_file,
                    config.coverage_threshold,
                    config.coverage_analyzer,
                )
                coverage_percent = coverage.percent

        return PipelineReport(
            marketplace_archive=marketplace_archive,
            repository_url=repository_url,
            checked_out_ref=checked_out_ref,
            built_vsix=built_vsix,
            coverage_percent=coverage_percent,
            coverage_tool=coverage_tool,
        )
    except (VsixError, CoverageError, subprocess.CalledProcessError) as exc:
        raise PipelineError(str(exc)) from exc
    finally:
        if not config.keep_work_dir and work_dir.exists():
            shutil.rmtree(work_dir)


def _build_vsix(repository_dir: Path, build_command: str) -> Path:
    before = set(repository_dir.rglob("*.vsix"))
    _run_shell(build_command, repository_dir)
    after = set(repository_dir.rglob("*.vsix"))
    created = sorted(after - before, key=lambda path: path.stat().st_mtime, reverse=True)
    if not created:
        raise PipelineError("build command did not create a VSIX file")
    return created[0]


def _run_shell(command: str, cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, shell=True, check=True)


def _run_coverage_tool(tool: str, threshold: float, cwd: Path) -> None:
    preset = get_coverage_tool_preset(tool, threshold)
    report_folder = cwd / preset.coverage_report_folder
    if not report_folder.exists():
        raise CoverageError(
            f"coverage tool '{tool}' expected report folder {report_folder}; "
            "make sure run_tests generates coverage data for this tool"
        )
    for command in (*preset.report, *preset.check):
        if command.strip():
            _run_shell(command, cwd)
