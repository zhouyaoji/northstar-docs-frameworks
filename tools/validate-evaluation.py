#!/usr/bin/env python3
"""Validate the versioned Northstar answer-quality evaluation contract."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
EVALUATION = ROOT / "evaluation"


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def validate() -> list[str]:
    errors: list[str] = []
    schema_paths = sorted((EVALUATION / "schemas").glob("*.schema.yaml"))
    schemas: dict[str, dict] = {}
    for path in schema_paths:
        schema = load(path)
        schemas[path.name] = schema
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as error:
            errors.append(f"{path.relative_to(ROOT)}: invalid schema: {error}")

    suite_path = EVALUATION / "benchmarks" / "answer-quality.yaml"
    suite = load(suite_path)
    suite_schema = schemas.get("benchmark-suite.schema.yaml")
    if suite_schema:
        validator = Draft202012Validator(suite_schema, format_checker=FormatChecker())
        for error in sorted(validator.iter_errors(suite), key=lambda item: list(item.path)):
            location = ".".join(str(part) for part in error.path) or "<root>"
            errors.append(f"{suite_path.relative_to(ROOT)}: schema error at {location}: {error.message}")

    source_registry = load(ROOT / "aipp" / "sources.yaml")
    known_sources = {source["id"] for source in source_registry.get("sources", [])}
    case_ids: set[str] = set()
    for case in suite.get("cases", []):
        case_id = case.get("id", "<missing-case-id>")
        if case_id in case_ids:
            errors.append(f"{suite_path.relative_to(ROOT)}: duplicate case ID {case_id}")
        case_ids.add(case_id)
        claims = {claim.get("id"): claim for claim in case.get("claims", [])}
        if len(claims) != len(case.get("claims", [])):
            errors.append(f"{case_id}: claim IDs must be unique")
        prohibited_ids = [claim.get("id") for claim in case.get("prohibitedClaims", [])]
        if len(prohibited_ids) != len(set(prohibited_ids)):
            errors.append(f"{case_id}: prohibited claim IDs must be unique")
        for claim in claims.values():
            for source_id in claim.get("sourceIds", []):
                if source_id not in known_sources:
                    errors.append(f"{case_id}: claim {claim.get('id')} cites unknown source {source_id}")
        for condition, expectation in case.get("expectations", {}).items():
            for claim_id in expectation.get("requiredClaimIds", []):
                if claim_id not in claims:
                    errors.append(f"{case_id}: {condition} requires unknown claim {claim_id}")
            for source_id in expectation.get("requiredSourceIds", []):
                if source_id not in known_sources:
                    errors.append(f"{case_id}: {condition} requires unknown source {source_id}")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Evaluation contract validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print("Validated evaluation schemas and answer-quality benchmark suite.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

