from pathlib import Path

from vsix_check_pipeline import git
from vsix_check_pipeline.git import choose_version_tag


def test_choose_version_tag_prefers_exact_version() -> None:
    assert choose_version_tag(["v1.2.3", "1.2.3"], "1.2.3") == "1.2.3"


def test_choose_version_tag_accepts_v_prefixed_version() -> None:
    assert choose_version_tag(["v1.2.3"], "1.2.3") == "v1.2.3"


def test_clone_repository_invokes_git_clone(monkeypatch, tmp_path: Path) -> None:
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(git.subprocess, "run", fake_run)

    git.clone_repository("https://github.com/acme/ext", tmp_path / "repo")

    assert calls[0][0] == [
        "git",
        "clone",
        "--depth",
        "1",
        "https://github.com/acme/ext",
        str(tmp_path / "repo"),
    ]
    assert calls[0][1]["check"] is True


def test_current_ref_reads_short_head(monkeypatch, tmp_path: Path) -> None:
    def fake_run(args, **kwargs):
        class Result:
            stdout = "abc123\n"

        return Result()

    monkeypatch.setattr(git.subprocess, "run", fake_run)

    assert git.current_ref(tmp_path) == "abc123"


def test_checkout_version_tag_fetches_and_checks_out_match(monkeypatch, tmp_path: Path) -> None:
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)

        class Result:
            stdout = "hash\trefs/tags/v1.2.3\n"

        return Result()

    monkeypatch.setattr(git.subprocess, "run", fake_run)

    assert git.checkout_version_tag(tmp_path, "1.2.3") == "v1.2.3"
    assert ["git", "fetch", "--depth", "1", "origin", "tag", "v1.2.3"] in calls
    assert ["git", "checkout", "--detach", "v1.2.3"] in calls


def test_checkout_version_tag_keeps_current_ref_without_match(monkeypatch, tmp_path: Path) -> None:
    def fake_run(args, **kwargs):
        class Result:
            stdout = "abc123\n" if "rev-parse" in args else ""

        return Result()

    monkeypatch.setattr(git.subprocess, "run", fake_run)

    assert git.checkout_version_tag(tmp_path, "1.2.3") == "abc123"


def test_checkout_ref_fetches_ref_and_checks_out_fetch_head(monkeypatch, tmp_path: Path) -> None:
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)

    monkeypatch.setattr(git.subprocess, "run", fake_run)

    assert git.checkout_ref(tmp_path, "pre-release/1.2.3") == "pre-release/1.2.3"
    assert ["git", "fetch", "--depth", "1", "origin", "pre-release/1.2.3"] in calls
    assert ["git", "checkout", "--detach", "FETCH_HEAD"] in calls
