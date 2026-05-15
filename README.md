# VSIX Check Pipeline

Python CLI that checks a published VS Code extension VSIX against a VSIX built
from the extension source repository.

## What it does

Given a marketplace package name and version, the pipeline:

1. Downloads the marketplace VSIX.
2. Renames the downloaded `.vsix` file to `.zip` and extracts that archive.
3. Reads repository metadata from the extracted `extension/package.json`.
4. Clones the repository.
5. Checks out a matching version tag when one exists.
6. Builds a VSIX from source.
7. Recursively compares unpacked marketplace and source-built VSIX contents.
8. Runs repository tests.
9. Verifies test coverage is at least 80%.

## Install for development

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

## Usage

```bash
vsix-check publisher.extension 1.2.3
```

The package name must use the Visual Studio Marketplace item name format:
`publisher.extension`.

Useful options:

```bash
vsix-check publisher.extension 1.2.3 \
  --work-dir .work \
  --install-command "npm ci" \
  --build-command "npx @vscode/vsce package --out dist/source.vsix" \
  --test-command "npm test -- --coverage" \
  --coverage-file coverage/lcov.info
```

## Package metadata

You can describe package-specific steps in `meta/{publisher.extension}.yml`.
For example, `meta/eamodio.gitlens.yml`:

```yaml
install_dependencies: "npm ci"
build_vsix: "npx @vscode/vsce package --out dist/source.vsix"
run_tests: "npm test -- --coverage"
coverage:
  enabled: true
  tool: "c8"
  threshold: 80
```

CLI flags override values from the metadata file. If no metadata file exists,
the default steps are:

```yaml
install_dependencies: "npm ci"
build_vsix: "npx @vscode/vsce package --out dist/source.vsix"
run_tests: "npm test -- --coverage"
coverage:
  enabled: true
  analyzer: "lcov"
  file: "coverage/lcov.info"
  threshold: 80
```

Set `coverage.enabled: false` only for packages whose upstream test command
does not produce a coverage artifact.

Supported coverage tool presets:

- `c8`
- `vitest`
- `nyc`
- `jest`
- `istanbul`
- `tap`

When `coverage.tool` is set, the pipeline runs that tool's preset `report`
commands followed by its `check` commands. The threshold from
`coverage.threshold` is applied to preset check commands where the tool supports
thresholds.

Example for c8:

```yaml
run_tests: "npx c8 --clean --temp-directory coverage/tmp npm test"
coverage:
  enabled: true
  tool: "c8"
  threshold: 80
```

Analyzer mode is still available when a package already produces a report file
and you want the Python pipeline to read it directly:

- `lcov`: reads `coverage/lcov.info`.
- `c8`, `istanbul`, `nyc`: read `coverage/coverage-summary.json`.

Example for reading a c8 JSON summary:

```yaml
run_tests: "npx c8 --reporter=json-summary npm test"
coverage:
  enabled: true
  analyzer: "c8"
  file: "coverage/coverage-summary.json"
  threshold: 80
```

The pipeline checks aggregate line coverage and fails when it is below the
configured threshold.

## Notes

This tool intentionally compares archive contents after extraction. It ignores
common archive metadata noise and reports added, removed, and changed files.
# vsix-checker
