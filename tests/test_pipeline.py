from pathlib import Path

import pytest

from vsix_check_pipeline import pipeline
from vsix_check_pipeline.coverage import CoverageSummary
from vsix_check_pipeline.diff import DirectoryDiff
from vsix_check_pipeline.pipeline import PipelineConfig, PipelineError


def _config(tmp_path: Path) -> PipelineConfig:
    return PipelineConfig(
        package="pub.ext",
        version="1.2.3",
        work_dir=tmp_path / "work",
        install_command="install",
        source_repository=None,
        source_ref=None,
        build_command="build",
        test_command="test",
        coverage_enabled=True,
        coverage_tool=None,
        coverage_analyzer="lcov",
        coverage_file="coverage/lcov.info",
        coverage_threshold=80,
        keep_work_dir=True,
    )


def test_run_pipeline_orchestrates_all_steps(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[str] = []

    def download_vsix(package: str, version: str, destination: Path) -> None:
        calls.append(f"download:{package}:{version}")
        destination.write_text("vsix", encoding="utf-8")

    def extract_vsix(vsix: Path, destination: Path) -> None:
        calls.append(f"extract:{vsix.name}:{destination.name}")
        destination.mkdir(parents=True, exist_ok=True)

    def clone_repository(repository_url: str, destination: Path) -> None:
        calls.append(f"clone:{repository_url}")
        destination.mkdir()

    monkeypatch.setattr(pipeline, "download_vsix", download_vsix)
    monkeypatch.setattr(
        pipeline,
        "rename_vsix_to_zip",
        lambda vsix: vsix.with_suffix(".zip"),
    )
    monkeypatch.setattr(pipeline, "extract_vsix", extract_vsix)
    monkeypatch.setattr(pipeline, "read_repository_url", lambda path: "https://github.com/acme/ext")
    monkeypatch.setattr(pipeline, "clone_repository", clone_repository)
    monkeypatch.setattr(pipeline, "checkout_version_tag", lambda repo, version: "v1.2.3")
    monkeypatch.setattr(pipeline, "_build_vsix", lambda repo, command: repo / "dist" / "source.vsix")
    monkeypatch.setattr(
        pipeline,
        "compare_directories",
        lambda expected, actual: DirectoryDiff(added=(), removed=(), changed=()),
    )
    monkeypatch.setattr(pipeline, "_run_shell", lambda command, cwd: calls.append(f"run:{command}"))
    monkeypatch.setattr(
        pipeline,
        "assert_coverage_at_least",
        lambda path, threshold, analyzer: CoverageSummary(covered_lines=9, total_lines=10),
    )

    report = pipeline.run_pipeline(_config(tmp_path))

    assert report.repository_url == "https://github.com/acme/ext"
    assert report.marketplace_archive.name == "marketplace.zip"
    assert report.checked_out_ref == "v1.2.3"
    assert report.coverage_percent == 90
    assert calls == [
        "download:pub.ext:1.2.3",
        "extract:marketplace.zip:marketplace",
        "clone:https://github.com/acme/ext",
        "run:install",
        "extract:source.vsix:source",
        "run:test",
    ]


def test_run_pipeline_fails_on_directory_diff(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pipeline, "download_vsix", lambda package, version, destination: destination.write_text("vsix"))
    monkeypatch.setattr(pipeline, "rename_vsix_to_zip", lambda vsix: vsix.with_suffix(".zip"))
    monkeypatch.setattr(pipeline, "extract_vsix", lambda vsix, destination: destination.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(pipeline, "read_repository_url", lambda path: "https://github.com/acme/ext")
    monkeypatch.setattr(pipeline, "clone_repository", lambda repository_url, destination: destination.mkdir())
    monkeypatch.setattr(pipeline, "checkout_version_tag", lambda repo, version: "v1.2.3")
    monkeypatch.setattr(pipeline, "_run_shell", lambda command, cwd: None)
    monkeypatch.setattr(pipeline, "_build_vsix", lambda repo, command: repo / "source.vsix")
    monkeypatch.setattr(
        pipeline,
        "compare_directories",
        lambda expected, actual: DirectoryDiff(added=(Path("extra.txt"),), removed=(), changed=()),
    )

    with pytest.raises(PipelineError, match="VSIX contents differ"):
        pipeline.run_pipeline(_config(tmp_path))


def test_build_vsix_returns_newest_created_archive(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    old = repository / "old.vsix"
    old.write_text("old", encoding="utf-8")

    def fake_run_shell(command: str, cwd: Path) -> None:
        dist = cwd / "dist"
        dist.mkdir()
        (dist / "new.vsix").write_text("new", encoding="utf-8")

    monkeypatch.setattr(pipeline, "_run_shell", fake_run_shell)

    assert pipeline._build_vsix(repository, "build").name == "new.vsix"


def test_build_vsix_fails_when_no_archive_is_created(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    monkeypatch.setattr(pipeline, "_run_shell", lambda command, cwd: None)

    with pytest.raises(PipelineError, match="did not create"):
        pipeline._build_vsix(repository, "build")


def test_run_pipeline_can_skip_coverage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = _config(tmp_path)
    config = PipelineConfig(
        package=config.package,
        version=config.version,
        work_dir=config.work_dir,
        install_command=config.install_command,
        source_repository=config.source_repository,
        source_ref=config.source_ref,
        build_command=config.build_command,
        test_command=config.test_command,
        coverage_enabled=False,
        coverage_tool=config.coverage_tool,
        coverage_analyzer=config.coverage_analyzer,
        coverage_file=config.coverage_file,
        coverage_threshold=config.coverage_threshold,
        keep_work_dir=config.keep_work_dir,
    )

    monkeypatch.setattr(pipeline, "download_vsix", lambda package, version, destination: destination.write_text("vsix"))
    monkeypatch.setattr(pipeline, "rename_vsix_to_zip", lambda vsix: vsix.with_suffix(".zip"))
    monkeypatch.setattr(pipeline, "extract_vsix", lambda vsix, destination: destination.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(pipeline, "read_repository_url", lambda path: "https://github.com/acme/ext")
    monkeypatch.setattr(pipeline, "clone_repository", lambda repository_url, destination: destination.mkdir())
    monkeypatch.setattr(pipeline, "checkout_version_tag", lambda repo, version: "v1.2.3")
    monkeypatch.setattr(pipeline, "_run_shell", lambda command, cwd: None)
    monkeypatch.setattr(pipeline, "_build_vsix", lambda repo, command: repo / "source.vsix")
    monkeypatch.setattr(
        pipeline,
        "compare_directories",
        lambda expected, actual: DirectoryDiff(added=(), removed=(), changed=()),
    )
    monkeypatch.setattr(pipeline, "assert_coverage_at_least", lambda path, threshold: pytest.fail("coverage should be skipped"))

    report = pipeline.run_pipeline(config)

    assert report.coverage_percent is None


def test_run_pipeline_can_use_coverage_tool_preset(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = _config(tmp_path)
    config = PipelineConfig(
        package=config.package,
        version=config.version,
        work_dir=config.work_dir,
        install_command=config.install_command,
        source_repository=config.source_repository,
        source_ref=config.source_ref,
        build_command=config.build_command,
        test_command=config.test_command,
        coverage_enabled=True,
        coverage_tool="tap",
        coverage_analyzer=config.coverage_analyzer,
        coverage_file=config.coverage_file,
        coverage_threshold=config.coverage_threshold,
        keep_work_dir=config.keep_work_dir,
    )
    calls: list[str] = []

    monkeypatch.setattr(pipeline, "download_vsix", lambda package, version, destination: destination.write_text("vsix"))
    monkeypatch.setattr(pipeline, "rename_vsix_to_zip", lambda vsix: vsix.with_suffix(".zip"))
    monkeypatch.setattr(pipeline, "extract_vsix", lambda vsix, destination: destination.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(pipeline, "read_repository_url", lambda path: "https://github.com/acme/ext")
    monkeypatch.setattr(pipeline, "clone_repository", lambda repository_url, destination: destination.mkdir())
    monkeypatch.setattr(pipeline, "checkout_version_tag", lambda repo, version: "v1.2.3")
    def fake_run_shell(command: str, cwd: Path) -> None:
        calls.append(command)
        if command == "test":
            (cwd / ".tap" / "coverage").mkdir(parents=True)

    monkeypatch.setattr(pipeline, "_run_shell", fake_run_shell)
    monkeypatch.setattr(pipeline, "_build_vsix", lambda repo, command: repo / "source.vsix")
    monkeypatch.setattr(
        pipeline,
        "compare_directories",
        lambda expected, actual: DirectoryDiff(added=(), removed=(), changed=()),
    )
    monkeypatch.setattr(pipeline, "assert_coverage_at_least", lambda path, threshold, analyzer: pytest.fail("python coverage should be skipped"))

    report = pipeline.run_pipeline(config)

    assert "npx tap report --coverage-report=text --show-full-coverage" in calls
    assert report.coverage_percent is None
    assert report.coverage_tool == "tap"


def test_run_pipeline_can_checkout_source_ref(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = _config(tmp_path)
    config = PipelineConfig(
        package=config.package,
        version=config.version,
        work_dir=config.work_dir,
        install_command=None,
        source_repository=config.source_repository,
        source_ref="pre-release/1.2.3",
        build_command=config.build_command,
        test_command=config.test_command,
        coverage_enabled=False,
        coverage_tool=config.coverage_tool,
        coverage_analyzer=config.coverage_analyzer,
        coverage_file=config.coverage_file,
        coverage_threshold=config.coverage_threshold,
        keep_work_dir=config.keep_work_dir,
    )

    monkeypatch.setattr(pipeline, "download_vsix", lambda package, version, destination: destination.write_text("vsix"))
    monkeypatch.setattr(pipeline, "rename_vsix_to_zip", lambda vsix: vsix.with_suffix(".zip"))
    monkeypatch.setattr(pipeline, "extract_vsix", lambda vsix, destination: destination.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(pipeline, "read_repository_url", lambda path: "https://github.com/acme/ext")
    monkeypatch.setattr(pipeline, "clone_repository", lambda repository_url, destination: destination.mkdir())
    monkeypatch.setattr(pipeline, "checkout_ref", lambda repo, ref: ref)
    monkeypatch.setattr(pipeline, "_run_shell", lambda command, cwd: None)
    monkeypatch.setattr(pipeline, "_build_vsix", lambda repo, command: repo / "source.vsix")
    monkeypatch.setattr(
        pipeline,
        "compare_directories",
        lambda expected, actual: DirectoryDiff(added=(), removed=(), changed=()),
    )

    report = pipeline.run_pipeline(config)

    assert report.checked_out_ref == "pre-release/1.2.3"
