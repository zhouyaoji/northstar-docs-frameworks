#!/usr/bin/env python3
"""Import Northstar evaluation responses and run deterministic checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
EVALUATION = ROOT / "evaluation"
SUITE_PATH = EVALUATION / "benchmarks" / "answer-quality.yaml"
RESPONSE_SCHEMA_PATH = EVALUATION / "schemas" / "response.schema.json"
JUDGMENT_SCHEMA_PATH = EVALUATION / "schemas" / "judgment.schema.yaml"
REPORT_SCHEMA_PATH = EVALUATION / "schemas" / "import-report.schema.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def iso_time(value: str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("--evaluated-at must include a timezone")
    return value


def schema_errors(validator: Draft202012Validator, value: object) -> list[str]:
    errors: list[str] = []
    for error in sorted(validator.iter_errors(value), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.path) or "<root>"
        errors.append(f"schema error at {location}: {error.message}")
    return errors


def generator_id(generator: dict) -> str:
    raw = "-".join(
        str(generator.get(field, "unknown")) for field in ("provider", "model", "interface")
    ).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    fingerprint = hashlib.sha256(
        json.dumps(generator, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:10]
    return f"{slug or 'unknown-generator'}-{fingerprint}"


def validate_run_inputs(run: Path) -> tuple[dict, dict, dict, dict[tuple[str, str], dict]]:
    manifest_path = run / "share" / "manifest.json"
    condition_map_path = run / "private" / "condition-map.json"
    if not manifest_path.exists() or not condition_map_path.exists():
        raise FileNotFoundError("run must contain share/manifest.json and private/condition-map.json")
    manifest = load_json(manifest_path)
    condition_map = load_json(condition_map_path)
    suite = load_yaml(SUITE_PATH)
    if manifest.get("runId") != condition_map.get("runId"):
        raise ValueError("manifest and condition map run IDs do not match")
    if manifest.get("suiteVersion") != suite.get("suiteVersion"):
        raise ValueError("run suite version does not match the installed benchmark suite")
    mappings = condition_map.get("conditions", {})
    if set(mappings.values()) != {"documentation", "aipp"}:
        raise ValueError("condition map must contain documentation and aipp exactly once")

    packets: dict[tuple[str, str], dict] = {}
    share = (run / "share").resolve()
    for entry in manifest.get("packets", []):
        key = (entry.get("caseId"), entry.get("blindedCondition"))
        packet_path = (share / entry.get("file", "")).resolve()
        if share not in packet_path.parents or not packet_path.exists():
            raise ValueError(f"invalid packet path for {key[0]}/{key[1]}")
        packet = load_json(packet_path)
        if key in packets:
            raise ValueError(f"duplicate packet entry for {key[0]}/{key[1]}")
        if packet.get("caseId") != key[0] or packet.get("blindedCondition") != key[1]:
            raise ValueError(f"packet metadata mismatch for {entry.get('file')}")
        packets[key] = packet
    if len(packets) != manifest.get("packetCount"):
        raise ValueError("manifest packet count does not match its packet entries")
    cases = {case["id"]: case for case in suite.get("cases", [])}
    return manifest, condition_map, suite, cases, packets


def deterministic_judgment(
    response: dict,
    packet: dict,
    case: dict,
    condition: str,
    evaluated_at: str,
) -> dict:
    expectation = case["expectations"][condition]
    citations = set(response.get("citations", []))
    allowed = set(packet.get("source", {}).get("citationIds", []))
    required = set(expectation.get("requiredSourceIds", []))
    unexpected = sorted(citations - allowed)
    missing = sorted(required - citations)

    evidence = ["response-schema-valid", "packet-metadata-match"]
    if unexpected:
        evidence.append("disallowed-citations:" + ",".join(unexpected))
    else:
        evidence.append("citations-within-packet")
    if missing:
        evidence.append("missing-required-citations:" + ",".join(missing))
    else:
        evidence.append("required-citations-present")

    if unexpected:
        attribution_score: int | str = 0
        decision = "fail"
    elif missing:
        attribution_score = 2
        decision = "needs-review"
    else:
        attribution_score = 4
        decision = "pass"

    return {
        "schemaVersion": 1,
        "runId": response["runId"],
        "responseId": response["responseId"],
        "evaluator": {"type": "deterministic", "identity": "northstar-import-checks-v1"},
        "rubricVersion": "answer-quality-1.0.0",
        "scores": {
            "accuracy": "not_applicable",
            "completeness": "not_applicable",
            "attribution": attribution_score,
            "edgeCaseHandling": "not_applicable",
            "conflictHandling": "not_applicable",
            "uncertainty": "not_applicable",
        },
        "decision": decision,
        "notes": (
            "Deterministic checks cover structure, packet metadata, and citation identifiers only. "
            "They do not establish that the answer text expresses the required claims, avoids prohibited "
            "claims, or uses uncertainty appropriately; those dimensions require blinded model or human review."
        ),
        "evidence": evidence,
        "evaluatedAt": evaluated_at,
    }


def import_responses(run: Path, responses_dir: Path, output: Path, evaluated_at: str) -> dict:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output}")
    manifest, condition_map, _, cases, packets = validate_run_inputs(run)
    response_schema = load_json(RESPONSE_SCHEMA_PATH)
    judgment_schema = load_yaml(JUDGMENT_SCHEMA_PATH)
    report_schema = load_json(REPORT_SCHEMA_PATH)
    response_validator = Draft202012Validator(response_schema, format_checker=FormatChecker())
    judgment_validator = Draft202012Validator(judgment_schema, format_checker=FormatChecker())
    report_validator = Draft202012Validator(report_schema, format_checker=FormatChecker())

    response_files = sorted(responses_dir.rglob("*.json")) if responses_dir.exists() else []
    invalid: list[dict] = []
    imported: list[dict] = []
    generator_records: dict[str, dict] = {}
    received: dict[str, set[tuple[str, str]]] = defaultdict(set)
    response_ids: set[str] = set()

    for path in response_files:
        relative = str(path.relative_to(responses_dir))
        try:
            response = load_json(path)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            invalid.append({"file": relative, "errors": [f"invalid JSON: {error}"]})
            continue
        errors = schema_errors(response_validator, response)
        key = (response.get("caseId"), response.get("blindedCondition"))
        packet = packets.get(key)
        if response.get("runId") != manifest.get("runId"):
            errors.append("runId does not match manifest")
        if response.get("suiteVersion") != manifest.get("suiteVersion"):
            errors.append("suiteVersion does not match manifest")
        if packet is None:
            errors.append("caseId/blindedCondition does not match a packet")
        response_id = response.get("responseId")
        if response_id in response_ids:
            errors.append("duplicate responseId")
        generator = response.get("generator", {})
        gid = generator_id(generator)
        if key in received[gid]:
            errors.append("duplicate case and blinded condition for this generator")
        if errors:
            invalid.append({"file": relative, "errors": errors})
            continue

        response_ids.add(response_id)
        received[gid].add(key)
        generator_records.setdefault(
            gid,
            {
                "id": gid,
                "provider": generator["provider"],
                "model": generator["model"],
                "interface": generator["interface"],
            },
        )
        condition = condition_map["conditions"][response["blindedCondition"]]
        case = cases[response["caseId"]]
        judgment = deterministic_judgment(response, packet, case, condition, evaluated_at)
        judgment_errors = schema_errors(judgment_validator, judgment)
        if judgment_errors:
            invalid.append({"file": relative, "errors": judgment_errors})
            continue

        imported_path = output / "responses" / f"{response_id}.json"
        imported_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, imported_path)
        write_json(output / "deterministic-judgments" / f"{response_id}.json", judgment)
        imported.append(
            {
                "responseId": response_id,
                "generatorId": gid,
                "caseId": response["caseId"],
                "blindedCondition": response["blindedCondition"],
                "sha256": sha256(path),
                "deterministicDecision": judgment["decision"],
            }
        )

    expected_keys = set(packets)
    generators: list[dict] = []
    total_missing = 0
    for gid, record in sorted(generator_records.items()):
        missing_keys = sorted(expected_keys - received[gid])
        total_missing += len(missing_keys)
        generators.append(
            {
                **record,
                "received": len(received[gid]),
                "expected": len(expected_keys),
                "missing": [
                    {"caseId": case_id, "blindedCondition": label}
                    for case_id, label in missing_keys
                ],
            }
        )

    report = {
        "schemaVersion": 1,
        "runId": manifest["runId"],
        "suiteVersion": manifest["suiteVersion"],
        "protocolVersion": manifest["protocolVersion"],
        "importedAt": evaluated_at,
        "counts": {
            "expectedPackets": len(expected_keys),
            "responseFiles": len(response_files),
            "imported": len(imported),
            "invalid": len(invalid),
            "missing": total_missing,
        },
        "generators": generators,
        "responses": sorted(imported, key=lambda item: item["responseId"]),
        "invalidResponses": invalid,
    }
    report_errors = schema_errors(report_validator, report)
    if report_errors:
        raise ValueError("generated import report is invalid: " + "; ".join(report_errors))
    write_json(output / "import-report.json", report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path, help="Generated evaluation run directory")
    parser.add_argument("--responses", type=Path, help="Response directory; defaults to RUN/responses")
    parser.add_argument("--output", type=Path, help="New or empty output directory; defaults to RUN/results")
    parser.add_argument("--evaluated-at", help="ISO 8601 timestamp; defaults to current UTC time")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    run = args.run.resolve()
    responses = (args.responses or run / "responses").resolve()
    output = (args.output or run / "results").resolve()
    try:
        report = import_responses(run, responses, output, iso_time(args.evaluated_at))
    except (FileExistsError, FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        print(f"Response import failed: {error}", file=sys.stderr)
        return 1
    counts = report["counts"]
    print(
        f"Imported {counts['imported']} responses; "
        f"invalid={counts['invalid']}, missing={counts['missing']}. Results: {output}"
    )
    return 1 if counts["invalid"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
