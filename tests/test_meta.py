from pathlib import Path

import pytest

from vsix_check_pipeline.meta import MetaError, load_package_meta, parse_package_meta


def test_load_package_meta_returns_empty_meta_when_file_is_missing(tmp_path: Path) -> None:
    meta = load_package_meta("pub.ext", tmp_path)

    assert meta.install_dependencies is None
    assert meta.build_vsix is None


def test_parse_package_meta_reads_commands_and_coverage(tmp_path: Path) -> None:
    path = tmp_path / "pub.ext.yml"
    path.write_text(
        "\n".join(
            [
                "install_dependencies: npm ci",
                "source_repository: https://github.com/acme/ext.git",
                "source_ref: pre-release/1.2.3",
                "build_vsix: npx @vscode/vsce package --out dist/source.vsix",
                "run_tests: npm test -- --coverage",
                "coverage:",
                "  enabled: false",
                "  tool: c8",
                "  analyzer: c8",
                "  file: coverage/lcov.info",
                "  threshold: 82.5",
            ]
        ),
        encoding="utf-8",
    )

    meta = parse_package_meta(path)

    assert meta.install_dependencies == "npm ci"
    assert meta.source_repository == "https://github.com/acme/ext.git"
    assert meta.source_ref == "pre-release/1.2.3"
    assert meta.build_vsix == "npx @vscode/vsce package --out dist/source.vsix"
    assert meta.run_tests == "npm test -- --coverage"
    assert meta.coverage_enabled is False
    assert meta.coverage_tool == "c8"
    assert meta.coverage_analyzer == "c8"
    assert meta.coverage_file == "coverage/lcov.info"
    assert meta.coverage_threshold == 82.5


def test_parse_package_meta_rejects_unsupported_indentation(tmp_path: Path) -> None:
    path = tmp_path / "pub.ext.yml"
    path.write_text("coverage:\n    file: coverage/lcov.info\n", encoding="utf-8")

    with pytest.raises(MetaError, match="indentation"):
        parse_package_meta(path)
