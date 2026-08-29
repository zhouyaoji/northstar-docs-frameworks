#!/usr/bin/env python3
"""Validate the canonical content manifest and source-format coverage."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
MANIFEST = CONTENT / "manifest.yaml"
FORMATS = {"markdown", "restructuredtext", "asciidoc"}


def source_title(path: Path, source_format: str) -> str | None:
    lines = path.read_text(encoding="utf-8").splitlines()
    if source_format == "markdown":
        for line in lines:
            match = re.match(r"^#\s+(.+?)\s*$", line)
            if match:
                return match.group(1)
    elif source_format == "asciidoc":
        for line in lines:
            match = re.match(r"^=\s+(.+?)\s*$", line)
            if match:
                return match.group(1)
    else:
        for index in range(len(lines) - 1):
            title = lines[index].strip()
            underline = lines[index + 1].strip()
            if title and re.fullmatch(r"=+", underline) and len(underline) >= len(title):
                return title
    return None


def main() -> int:
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    errors: list[str] = []

    if manifest.get("schemaVersion") != 1:
        errors.append("manifest schemaVersion must be 1")

    pages = manifest.get("pages")
    if not isinstance(pages, list) or not pages:
        errors.append("manifest pages must be a non-empty list")
        pages = []

    seen_ids: set[str] = set()
    seen_paths: set[Path] = set()
    for page in pages:
        page_id = page.get("id")
        title = page.get("title")
        sources = page.get("sources", {})

        if not isinstance(page_id, str) or not page_id:
            errors.append("every page needs a non-empty id")
            continue
        if page_id in seen_ids:
            errors.append(f"duplicate page id: {page_id}")
        seen_ids.add(page_id)

        if not isinstance(title, str) or not title:
            errors.append(f"{page_id}: missing title")
        if set(sources) != FORMATS:
            missing = sorted(FORMATS - set(sources))
            extra = sorted(set(sources) - FORMATS)
            errors.append(f"{page_id}: invalid source formats; missing={missing}, extra={extra}")

        for source_format in FORMATS:
            relative = sources.get(source_format)
            if not relative:
                continue
            path = (CONTENT / relative).resolve()
            try:
                path.relative_to(CONTENT.resolve())
            except ValueError:
                errors.append(f"{page_id}: source escapes content directory: {relative}")
                continue
            if path in seen_paths:
                errors.append(f"{page_id}: source is assigned more than once: {relative}")
            seen_paths.add(path)
            if not path.is_file():
                errors.append(f"{page_id}: source does not exist: {relative}")
                continue
            actual_title = source_title(path, source_format)
            if actual_title != title:
                errors.append(
                    f"{page_id}: {source_format} title is {actual_title!r}; expected {title!r}"
                )

    if errors:
        print("Content validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(f"Validated {len(pages)} pages across {len(FORMATS)} source formats.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
