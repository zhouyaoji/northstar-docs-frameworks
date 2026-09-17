#!/usr/bin/env python3
"""Validate Northstar AIPP sources and writer-controlled entries."""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parents[1]
AIPP = ROOT / "aipp"
ALLOWED_KINDS = {"concept", "environment", "instruction", "reference", "support_case", "troubleshooting"}
ALLOWED_REVIEW_STATES = {"draft", "in-review", "approved-for-demo", "rejected"}


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def validate() -> list[str]:
    errors: list[str] = []
    registry = load(AIPP / "sources.yaml")
    if registry.get("schemaVersion") != 1:
        errors.append("aipp/sources.yaml: schemaVersion must be 1")
    sources = registry.get("sources", [])
    source_ids = [source.get("id") for source in sources]
    if len(source_ids) != len(set(source_ids)):
        errors.append("aipp/sources.yaml: source IDs must be unique")
    for source in sources:
        label = source.get("id", "<missing source id>")
        for field in ("id", "name", "type", "authority", "owner", "topics", "lifecycle", "locator", "retrieval"):
            if not source.get(field):
                errors.append(f"{label}: missing source field {field}")
        locator = source.get("locator", {})
        kind, value = locator.get("kind"), locator.get("value")
        if kind == "path":
            path = (ROOT / str(value)).resolve()
            try:
                path.relative_to(ROOT.resolve())
            except ValueError:
                errors.append(f"{label}: source path escapes repository")
            else:
                if not path.exists():
                    errors.append(f"{label}: source path does not exist: {value}")
        elif kind == "url":
            parsed = urlparse(str(value))
            if parsed.scheme not in {"https", "http"} or not parsed.netloc:
                errors.append(f"{label}: invalid source URL")
        else:
            errors.append(f"{label}: locator.kind must be path or url")

    manifest = load(ROOT / "content" / "manifest.yaml")
    page_ids = {page["id"] for page in manifest.get("pages", [])}
    entry_pages: set[str] = set()
    statement_ids: set[str] = set()
    for path in sorted((AIPP / "entries").glob("*.yaml")):
        entry = load(path)
        label = str(path.relative_to(ROOT))
        if entry.get("schemaVersion") != 1:
            errors.append(f"{label}: schemaVersion must be 1")
        document_id = entry.get("documentId")
        if document_id not in page_ids:
            errors.append(f"{label}: unknown documentId {document_id!r}")
        if document_id in entry_pages:
            errors.append(f"{label}: duplicate documentId {document_id}")
        entry_pages.add(document_id)
        state = entry.get("review", {}).get("state")
        if state not in ALLOWED_REVIEW_STATES:
            errors.append(f"{label}: invalid review state {state!r}")
        for source_id in entry.get("sourceIds", []):
            if source_id not in source_ids:
                errors.append(f"{label}: unknown source {source_id}")
        for statement in entry.get("aiOnlyStatements", []):
            statement_id = statement.get("id")
            if not statement_id or statement_id in statement_ids:
                errors.append(f"{label}: missing or duplicate statement ID {statement_id!r}")
            statement_ids.add(statement_id)
            if statement.get("kind") not in ALLOWED_KINDS:
                errors.append(f"{label}: {statement_id} has unsupported kind")
            if not statement.get("text"):
                errors.append(f"{label}: {statement_id} is missing text")
            citations = statement.get("sourceIds", [])
            if not citations:
                errors.append(f"{label}: {statement_id} needs at least one source")
            for source_id in citations:
                if source_id not in source_ids:
                    errors.append(f"{label}: {statement_id} cites unknown source {source_id}")
    missing_entries = sorted(page_ids - entry_pages)
    if missing_entries:
        errors.append(f"AIPP entries missing for: {', '.join(missing_entries)}")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("AIPP validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print("Validated AIPP source registry and entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
