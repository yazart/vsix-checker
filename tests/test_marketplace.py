import json
import zipfile
import gzip
from pathlib import Path

import pytest

from vsix_check_pipeline import marketplace
from vsix_check_pipeline.marketplace import (
    VsixError,
    download_vsix,
    extract_vsix,
    marketplace_vsix_url,
    parse_package_name,
    read_repository_url,
    rename_vsix_to_zip,
)


def test_parse_package_name_requires_publisher_and_extension() -> None:
    parsed = parse_package_name("publisher.extension")

    assert parsed.publisher == "publisher"
    assert parsed.extension == "extension"


def test_parse_package_name_rejects_invalid_name() -> None:
    with pytest.raises(VsixError, match="publisher.extension"):
        parse_package_name("extension-only")


def test_marketplace_vsix_url_uses_public_gallery_endpoint() -> None:
    assert marketplace_vsix_url("pub.ext", "1.2.3") == (
        "https://marketplace.visualstudio.com/_apis/public/gallery/"
        "publishers/pub/vsextensions/ext/1.2.3/vspackage"
    )


def test_read_repository_url_accepts_object_form(tmp_path: Path) -> None:
    package_json = tmp_path / "extension" / "package.json"
    package_json.parent.mkdir()
    package_json.write_text(
        json.dumps({"repository": {"url": "https://github.com/acme/ext"}}),
        encoding="utf-8",
    )

    assert read_repository_url(tmp_path) == "https://github.com/acme/ext"


def test_read_repository_url_accepts_string_form(tmp_path: Path) -> None:
    package_json = tmp_path / "extension" / "package.json"
    package_json.parent.mkdir()
    package_json.write_text(
        json.dumps({"repository": "https://github.com/acme/ext"}),
        encoding="utf-8",
    )

    assert read_repository_url(tmp_path) == "https://github.com/acme/ext"


def test_read_repository_url_rejects_invalid_json(tmp_path: Path) -> None:
    package_json = tmp_path / "extension" / "package.json"
    package_json.parent.mkdir()
    package_json.write_text("{", encoding="utf-8")

    with pytest.raises(VsixError, match="invalid package.json"):
        read_repository_url(tmp_path)


def test_read_repository_url_rejects_missing_metadata(tmp_path: Path) -> None:
    package_json = tmp_path / "extension" / "package.json"
    package_json.parent.mkdir()
    package_json.write_text("{}", encoding="utf-8")

    with pytest.raises(VsixError, match="repository.url"):
        read_repository_url(tmp_path)


def test_extract_vsix_unpacks_archive(tmp_path: Path) -> None:
    archive = tmp_path / "archive.vsix"
    destination = tmp_path / "out"
    with zipfile.ZipFile(archive, "w") as zip_file:
        zip_file.writestr("extension/package.json", "{}")

    extract_vsix(archive, destination)

    assert (destination / "extension" / "package.json").exists()


def test_rename_vsix_to_zip_moves_downloaded_archive(tmp_path: Path) -> None:
    vsix = tmp_path / "marketplace.vsix"
    vsix.write_bytes(b"archive")

    zip_path = rename_vsix_to_zip(vsix)

    assert zip_path == tmp_path / "marketplace.zip"
    assert zip_path.read_bytes() == b"archive"
    assert not vsix.exists()


def test_download_vsix_writes_response_body(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class FakeResponse:
        def __init__(self) -> None:
            self._sent = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def read(self, size=-1):
            if self._sent:
                return b""
            self._sent = True
            return b"vsix-bytes"

    seen_requests = []
    monkeypatch.setattr(
        marketplace.urllib.request,
        "urlopen",
        lambda request: seen_requests.append(request) or FakeResponse(),
    )

    destination = download_vsix("pub.ext", "1.2.3", tmp_path / "marketplace.vsix")

    assert destination.read_bytes() == b"vsix-bytes"
    assert seen_requests[0].headers["Accept-encoding"] == "identity"


def test_download_vsix_decompresses_gzip_wrapped_archive(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FakeResponse:
        def __init__(self) -> None:
            self._sent = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def read(self, size=-1):
            if self._sent:
                return b""
            self._sent = True
            return gzip.compress(b"PK\x03\x04zip-bytes")

    monkeypatch.setattr(marketplace.urllib.request, "urlopen", lambda request: FakeResponse())

    destination = download_vsix("pub.ext", "1.2.3", tmp_path / "marketplace.vsix")

    assert destination.read_bytes() == b"PK\x03\x04zip-bytes"
