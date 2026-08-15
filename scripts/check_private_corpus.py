from __future__ import annotations

import argparse
import subprocess
from collections.abc import Iterable
from pathlib import PurePosixPath

FORBIDDEN_PREFIXES = (
    "books_pdf/",
    "private_knowledge/",
    "knowledge_private/",
    "drive_exports/",
    "ingestion_cache/",
    ".private_knowledge/",
)
FORBIDDEN_EXTENSIONS = {".epub", ".mobi", ".azw", ".azw3"}


def _normalize(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def check_paths(paths: Iterable[str]) -> list[str]:
    violations: list[str] = []
    for raw_path in paths:
        path = _normalize(raw_path.strip())
        if not path:
            continue
        lowered = path.lower()
        forbidden_prefix = any(lowered.startswith(prefix.lower()) for prefix in FORBIDDEN_PREFIXES)
        forbidden_extension = PurePosixPath(lowered).suffix in FORBIDDEN_EXTENSIONS
        if forbidden_prefix or forbidden_extension:
            violations.append(path)
    return violations


def _git_paths(*args: str) -> list[str]:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in completed.stdout.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Reject private corpus files from the public repo")
    parser.add_argument(
        "--tracked-only",
        action="store_true",
        help="scan tracked files only; default also checks staged paths",
    )
    args = parser.parse_args()

    paths = _git_paths("ls-files")
    if not args.tracked_only:
        paths.extend(_git_paths("diff", "--cached", "--name-only"))

    violations = sorted(set(check_paths(paths)))
    for path in violations:
        print(path)
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
