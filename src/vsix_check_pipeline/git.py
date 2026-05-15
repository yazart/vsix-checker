from __future__ import annotations

import subprocess
from pathlib import Path


def clone_repository(repository_url: str, destination: Path) -> None:
    subprocess.run(
        ["git", "clone", "--depth", "1", repository_url, str(destination)],
        check=True,
    )


def checkout_version_tag(repository: Path, version: str) -> str:
    tags = _matching_tags(repository, version)
    if not tags:
        return current_ref(repository)

    tag = choose_version_tag(tags, version)
    subprocess.run(["git", "fetch", "--depth", "1", "origin", f"tag", tag], cwd=repository, check=True)
    subprocess.run(["git", "checkout", "--detach", tag], cwd=repository, check=True)
    return tag


def checkout_ref(repository: Path, ref: str) -> str:
    subprocess.run(["git", "fetch", "--depth", "1", "origin", ref], cwd=repository, check=True)
    subprocess.run(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=repository, check=True)
    return ref


def choose_version_tag(tags: list[str], version: str) -> str:
    preferred = [version, f"v{version}"]
    for tag in preferred:
        if tag in tags:
            return tag
    return sorted(tags)[0]


def current_ref(repository: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repository,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def _matching_tags(repository: Path, version: str) -> list[str]:
    patterns = [version, f"v{version}"]
    tags: list[str] = []
    for pattern in patterns:
        result = subprocess.run(
            ["git", "ls-remote", "--tags", "origin", pattern],
            cwd=repository,
            check=True,
            text=True,
            capture_output=True,
        )
        for line in result.stdout.splitlines():
            ref = line.rsplit("/", 1)[-1]
            if ref.endswith("^{}"):
                ref = ref[:-3]
            if ref not in tags:
                tags.append(ref)
    return tags
