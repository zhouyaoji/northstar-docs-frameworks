#!/usr/bin/env python3
"""Validate Northstar AIPP sources and writer-controlled entries."""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
AIPP = ROOT / "aipp"
ALLOWED_KINDS = {"concept", "environment", "instruction", "reference", "support_case", "troubleshooting"}
ALLOWED_REVIEW_STATES = {"draft", "in-review", "approved-for-demo", "rejected"}


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def validate() -> list[str]:
    errors: list[str] = []
    registry = load(AIPP / "sources.yaml")
    type_catalog = load(AIPP / "source-types.yaml")
    if type_catalog.get("schemaVersion") != 1:
        errors.append("aipp/source-types.yaml: schemaVersion must be 1")
    source_types = type_catalog.get("sourceTypes", [])
    source_type_ids = [item.get("id") for item in source_types]
    if len(source_type_ids) != len(set(source_type_ids)):
        errors.append("aipp/source-types.yaml: source type IDs must be unique")
    for item in source_types:
        label = item.get("id", "<missing source type id>")
        for field in ("id", "name", "typicalAuthority", "typicalOwners", "commonFormats"):
            if not item.get(field):
                errors.append(f"source type {label}: missing field {field}")
    if registry.get("schemaVersion") != 1:
        errors.append("aipp/sources.yaml: schemaVersion must be 1")
    sources = registry.get("sources", [])
    source_ids = [source.get("id") for source in sources]
    if len(source_ids) != len(set(source_ids)):
        errors.append("aipp/sources.yaml: source IDs must be unique")
    for source in sources:
        label = source.get("id", "<missing source id>")
        for field in ("id", "name", "sourceType", "format", "authority", "owner", "topics", "lifecycle", "locator", "retrieval"):
            if not source.get(field):
                errors.append(f"{label}: missing source field {field}")
        if source.get("sourceType") not in source_type_ids:
            errors.append(f"{label}: unknown sourceType {source.get('sourceType')!r}")
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

    examples = load(AIPP / "sample-sources" / "source-registry.example.yaml")
    for source in examples.get("sources", []):
        label = f"sample source {source.get('id', '<missing source id>')}"
        for field in ("id", "name", "sourceType", "format", "authority", "owner", "topics", "lifecycle", "locator", "retrieval"):
            if not source.get(field):
                errors.append(f"{label}: missing source field {field}")
        if source.get("sourceType") not in source_type_ids:
            errors.append(f"{label}: unknown sourceType {source.get('sourceType')!r}")
        locator = source.get("locator", {})
        parsed = urlparse(str(locator.get("value")))
        if locator.get("kind") != "url" or parsed.scheme not in {"https", "http"} or not parsed.netloc:
            errors.append(f"{label}: sample locator must be a valid URL")

    manifest = load(ROOT / "content" / "manifest.yaml")
    sidecar_schema = load(AIPP / "schemas" / "sidecar.schema.yaml")
    try:
        Draft202012Validator.check_schema(sidecar_schema)
    except Exception as error:
        errors.append(f"aipp/schemas/sidecar.schema.yaml: invalid schema: {error}")
    sidecar_validator = Draft202012Validator(sidecar_schema)
    page_ids = {page["id"] for page in manifest.get("pages", [])}
    entry_pages: set[str] = set()
    statement_ids: set[str] = set()
    for path in sorted((AIPP / "entries").glob("*.yaml")):
        entry = load(path)
        label = str(path.relative_to(ROOT))
        for error in sorted(sidecar_validator.iter_errors(entry), key=lambda item: list(item.path)):
            location = ".".join(str(part) for part in error.path) or "<root>"
            errors.append(f"{label}: schema error at {location}: {error.message}")
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
