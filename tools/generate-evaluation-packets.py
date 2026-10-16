#!/usr/bin/env python3
"""Generate randomized, blinded Northstar answer-evaluation packets."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
EVALUATION = ROOT / "evaluation"
SUITE_PATH = EVALUATION / "benchmarks" / "answer-quality.yaml"
PACKET_SCHEMA_PATH = EVALUATION / "schemas" / "packet.schema.json"
RESPONSE_SCHEMA_PATH = EVALUATION / "schemas" / "response.schema.json"
RUN_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

SOURCE_PATHS = {
    "documentation": ROOT / "public" / "llms-full.txt",
    "aipp": ROOT / "public" / "aipp" / "northstar-platform.json",
}

INSTRUCTIONS = [
    "Answer the question using only the source content in this packet.",
    "If the source does not establish the answer, say that the available evidence is insufficient.",
    "Cite only identifiers listed in source.citationIds.",
    "Do not guess which source condition the blinded label represents.",
    "Return only one JSON object matching evaluation/schemas/response.schema.json.",
    "Replace every replace-* placeholder in responseTemplate and preserve the supplied run, case, and blinded-condition values.",
]


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def source_record(condition: str) -> dict:
    path = SOURCE_PATHS[condition]
    if not path.exists():
        raise FileNotFoundError(f"Missing source artifact {path.relative_to(ROOT)}; run ./tools/build-sites.sh first.")
    content = path.read_text(encoding="utf-8")
    if condition == "documentation":
        citation_ids = ["northstar-human-docs"]
    else:
        compiled = json.loads(content)
        citation_ids = sorted(
            {
                source_id
                for statement in compiled.get("content", {}).get("statements", [])
                for source_id in statement.get("source_ids", [])
            }
        )
    return {"sha256": digest(content), "citationIds": citation_ids, "content": content}


def response_template(run_id: str, suite_version: str, case_id: str, label: str, created_at: str) -> dict:
    return {
        "schemaVersion": 1,
        "responseId": f"{run_id}-{case_id}-{label}-replace-model",
        "runId": run_id,
        "suiteVersion": suite_version,
        "caseId": case_id,
        "blindedCondition": label,
        "generator": {
            "provider": "replace-provider",
            "model": "replace-model",
            "interface": "assistant-file-review",
            "parameters": {},
        },
        "answer": "replace-answer",
        "citations": [],
        "generatedAt": created_at,
    }


def parse_created_at(value: str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("--created-at must include a timezone")
    return value


def generate(run_id: str, seed: int, output: Path, created_at: str) -> int:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError("--run-id must contain lowercase letters, digits, and single hyphens")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output}")

    suite = load_yaml(SUITE_PATH)
    packet_schema = load_json(PACKET_SCHEMA_PATH)
    response_schema = load_json(RESPONSE_SCHEMA_PATH)
    registry = Registry().with_resource(
        response_schema["$id"], Resource.from_contents(response_schema)
    )
    packet_validator = Draft202012Validator(
        packet_schema, registry=registry, format_checker=FormatChecker()
    )

    rng = random.Random(seed)
    conditions = ["documentation", "aipp"]
    rng.shuffle(conditions)
    labels = ["source-a", "source-b"]
    condition_map = dict(zip(labels, conditions, strict=True))
    sources = {condition: source_record(condition) for condition in conditions}

    cases = list(suite.get("cases", []))
    rng.shuffle(cases)
    packet_entries: list[dict] = []
    for position, case in enumerate(cases, start=1):
        for label in labels:
            condition = condition_map[label]
            packet = {
                "schemaVersion": 1,
                "runId": run_id,
                "suiteVersion": suite["suiteVersion"],
                "protocolVersion": suite["protocolVersion"],
                "caseId": case["id"],
                "question": case["question"],
                "blindedCondition": label,
                "instructions": INSTRUCTIONS,
                "source": sources[condition],
                "responseTemplate": response_template(run_id, suite["suiteVersion"], case["id"], label, created_at),
            }
            validation_errors = sorted(packet_validator.iter_errors(packet), key=lambda item: list(item.path))
            if validation_errors:
                details = "; ".join(error.message for error in validation_errors)
                raise ValueError(f"Generated packet {case['id']}/{label} is invalid: {details}")
            filename = f"{position:02d}-{case['id']}-{label}.json"
            write_json(output / "share" / "packets" / filename, packet)
            packet_entries.append(
                {
                    "caseId": case["id"],
                    "blindedCondition": label,
                    "file": f"packets/{filename}",
                    "sourceSha256": sources[condition]["sha256"],
                }
            )

    manifest = {
        "schemaVersion": 1,
        "runId": run_id,
        "suiteVersion": suite["suiteVersion"],
        "protocolVersion": suite["protocolVersion"],
        "createdAt": created_at,
        "packetCount": len(packet_entries),
        "packets": packet_entries,
    }
    private_map = {
        "schemaVersion": 1,
        "runId": run_id,
        "seed": seed,
        "warning": "Do not provide this file to answer generators or blinded evaluators.",
        "conditions": condition_map,
        "sourceArtifacts": {
            condition: {
                "path": str(SOURCE_PATHS[condition].relative_to(ROOT)),
                "sha256": sources[condition]["sha256"],
            }
            for condition in conditions
        },
    }
    write_json(output / "share" / "manifest.json", manifest)
    write_json(output / "private" / "condition-map.json", private_map)
    (output / "share" / "README.md").write_text(
        "# Blinded Northstar evaluation packets\n\n"
        "Give only this `share` directory to an answer-generating assistant. "
        "For each packet, return the completed `responseTemplate` as a standalone JSON file. "
        "Do not expose `../private/condition-map.json` until the blinded evaluation is complete.\n",
        encoding="utf-8",
    )
    print(f"Generated {len(packet_entries)} blinded packets in {output}")
    return len(packet_entries)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="Stable lowercase run identifier, for example pilot-001")
    parser.add_argument("--seed", required=True, type=int, help="Integer used to randomize conditions and question order")
    parser.add_argument("--output", required=True, type=Path, help="New or empty output directory")
    parser.add_argument("--created-at", help="ISO 8601 timestamp; defaults to the current UTC time")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        created_at = parse_created_at(args.created_at)
        generate(args.run_id, args.seed, args.output.resolve(), created_at)
    except (FileExistsError, FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        print(f"Packet generation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
