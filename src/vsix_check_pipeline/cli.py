from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .meta import MetaError, load_package_meta
from .pipeline import PipelineConfig, PipelineError, run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vsix-check",
        description="Check a marketplace VSIX against a VSIX built from source.",
    )
    parser.add_argument("package", help="Marketplace item name, e.g. publisher.extension")
    parser.add_argument("version", help="Package version to verify")
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path(".vsix-check-work"),
        help="Directory for downloads, clones, and extracted archives.",
    )
    parser.add_argument(
        "--meta-dir",
        type=Path,
        default=Path("meta"),
        help="Directory with per-package metadata files named {package}.yml.",
    )
    parser.add_argument(
        "--install-command",
        default=None,
        help="Shell command used to install dependencies inside the cloned repository.",
    )
    parser.add_argument(
        "--build-command",
        default=None,
        help="Shell command used to build a VSIX inside the cloned repository.",
    )
    parser.add_argument(
        "--test-command",
        default=None,
        help="Shell command used to run tests inside the cloned repository.",
    )
    parser.add_argument(
        "--skip-coverage",
        action="store_true",
        help="Skip coverage verification for packages that do not produce coverage artifacts.",
    )
    parser.add_argument(
        "--coverage-file",
        default=None,
        help="Path to a coverage report relative to the cloned repository.",
    )
    parser.add_argument(
        "--coverage-analyzer",
        choices=("lcov", "c8", "istanbul", "nyc"),
        default=None,
        help="Coverage report analyzer to use.",
    )
    parser.add_argument(
        "--coverage-tool",
        choices=("c8", "vitest", "nyc", "jest", "istanbul", "tap"),
        default=None,
        help="Coverage tool preset to run for report and threshold checks.",
    )
    parser.add_argument(
        "--coverage-threshold",
        type=float,
        default=None,
        help="Minimum aggregate line coverage percentage.",
    )
    parser.add_argument(
        "--keep-work-dir",
        action="store_true",
        help="Keep the work directory after a successful run.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        meta = load_package_meta(args.package, args.meta_dir)
    except MetaError as exc:
        print(f"VSIX check failed: {exc}", file=sys.stderr)
        return 1

    config = PipelineConfig(
        package=args.package,
        version=args.version,
        work_dir=args.work_dir,
        install_command=args.install_command
        if args.install_command is not None
        else meta.install_dependencies or "npm ci",
        source_repository=meta.source_repository,
        source_ref=meta.source_ref,
        build_command=args.build_command
        if args.build_command is not None
        else meta.build_vsix or "npx @vscode/vsce package --out dist/source.vsix",
        test_command=args.test_command
        if args.test_command is not None
        else meta.run_tests or "npm test -- --coverage",
        coverage_enabled=False
        if args.skip_coverage
        else meta.coverage_enabled
        if meta.coverage_enabled is not None
        else True,
        coverage_tool=args.coverage_tool
        if args.coverage_tool is not None
        else meta.coverage_tool,
        coverage_analyzer=args.coverage_analyzer
        if args.coverage_analyzer is not None
        else meta.coverage_analyzer or "lcov",
        coverage_file=args.coverage_file
        if args.coverage_file is not None
        else meta.coverage_file or "coverage/lcov.info",
        coverage_threshold=args.coverage_threshold
        if args.coverage_threshold is not None
        else meta.coverage_threshold or 80.0,
        keep_work_dir=args.keep_work_dir,
    )

    try:
        report = run_pipeline(config)
    except PipelineError as exc:
        print(f"VSIX check failed: {exc}", file=sys.stderr)
        return 1

    print("VSIX check passed")
    print(f"Marketplace archive: {report.marketplace_archive}")
    print(f"Repository: {report.repository_url}")
    print(f"Checked out ref: {report.checked_out_ref}")
    print(f"Built VSIX: {report.built_vsix}")
    if report.coverage_percent is None:
        if report.coverage_tool is None:
            print("Coverage: skipped")
        else:
            print(f"Coverage: checked by {report.coverage_tool}")
    else:
        print(f"Coverage: {report.coverage_percent:.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
