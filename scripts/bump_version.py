#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

PYPROJECT = Path("pyproject.toml")
VERSION_PATTERN = re.compile(r'^(version\s*=\s*")([0-9]+)\.([0-9]+)\.([0-9]+)(")', re.MULTILINE)


def bump_version(text: str, level: str) -> tuple[str, str]:
    match = VERSION_PATTERN.search(text)
    if not match:
        raise SystemExit("Could not locate version in pyproject.toml")
    major, minor, patch = (int(match.group(i)) for i in range(2, 5))
    if level == "major":
        major += 1
        minor = 0
        patch = 0
    elif level == "minor":
        minor += 1
        patch = 0
    else:
        patch += 1
    new_version = f"{major}.{minor}.{patch}"
    start, end = match.span()
    updated = text[:start] + match.group(1) + new_version + match.group(5) + text[end:]
    return new_version, updated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bump project version")
    parser.add_argument("--dry-run", action="store_true", help="Do not write changes back to pyproject.toml")
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the new version string (for GitHub Actions)",
    )
    parser.add_argument(
        "--level",
        choices=("patch", "minor", "major"),
        default="patch",
        help="Which part of the version to increment (default: patch)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    text = PYPROJECT.read_text(encoding="utf-8")
    version, updated = bump_version(text, args.level)
    if not args.dry_run:
        PYPROJECT.write_text(updated, encoding="utf-8")
    if args.output:
        args.output.write_text(f"version={version}\n", encoding="utf-8")
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
