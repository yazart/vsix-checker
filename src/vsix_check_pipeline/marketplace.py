from __future__ import annotations

import gzip
import json
import shutil
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote


class VsixError(ValueError):
    """Raised when a VSIX cannot be downloaded or inspected."""


@dataclass(frozen=True)
class PackageName:
    publisher: str
    extension: str

    @property
    def item_name(self) -> str:
        return f"{self.publisher}.{self.extension}"


def parse_package_name(package: str) -> PackageName:
    parts = package.split(".", 1)
    if len(parts) != 2 or not all(parts):
        raise VsixError("package must use publisher.extension format")
    return PackageName(publisher=parts[0], extension=parts[1])


def marketplace_vsix_url(package: str, version: str) -> str:
    parsed = parse_package_name(package)
    publisher = quote(parsed.publisher, safe="")
    extension = quote(parsed.extension, safe="")
    package_version = quote(version, safe="")
    return (
        "https://marketplace.visualstudio.com/_apis/public/gallery/"
        f"publishers/{publisher}/vsextensions/{extension}/{package_version}/vspackage"
    )


def download_vsix(package: str, version: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    url = marketplace_vsix_url(package, version)
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/octet-stream",
            "Accept-Encoding": "identity",
            "User-Agent": "vsix-check-pipeline/0.1",
        },
    )
    try:
        with urllib.request.urlopen(request) as response, destination.open("wb") as output:
            shutil.copyfileobj(response, output)
    except OSError as exc:
        raise VsixError(f"could not download VSIX from {url}: {exc}") from exc
    _decompress_gzip_wrapped_file(destination)
    return destination


def _decompress_gzip_wrapped_file(path: Path) -> None:
    if path.read_bytes()[:2] != b"\x1f\x8b":
        return

    decompressed = path.with_suffix(path.suffix + ".decompressed")
    try:
        with gzip.open(path, "rb") as source, decompressed.open("wb") as output:
            shutil.copyfileobj(source, output)
    except OSError as exc:
        raise VsixError(f"could not decompress gzip-wrapped VSIX: {path}") from exc
    decompressed.replace(path)


def rename_vsix_to_zip(vsix_path: Path) -> Path:
    if vsix_path.suffix != ".vsix":
        raise VsixError(f"expected .vsix file, got: {vsix_path}")
    zip_path = vsix_path.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    return vsix_path.rename(zip_path)


def extract_vsix(vsix_path: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    try:
        with zipfile.ZipFile(vsix_path) as archive:
            archive.extractall(destination)
    except zipfile.BadZipFile as exc:
        raise VsixError(f"invalid VSIX archive: {vsix_path}") from exc


def read_repository_url(extracted_vsix: Path) -> str:
    package_json = extracted_vsix / "extension" / "package.json"
    if not package_json.exists():
        raise VsixError(f"VSIX does not contain extension/package.json: {extracted_vsix}")

    try:
        manifest = json.loads(package_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VsixError(f"invalid package.json inside VSIX: {exc}") from exc

    repository = manifest.get("repository")
    if isinstance(repository, str):
        return repository
    if isinstance(repository, dict) and isinstance(repository.get("url"), str):
        return repository["url"]
    raise VsixError("VSIX package.json does not declare repository.url")
