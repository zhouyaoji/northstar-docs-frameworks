#!/usr/bin/env python3
"""Create blinded human-review packets from imported Northstar responses."""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
EVALUATION = ROOT / "evaluation"
SUITE_PATH = EVALUATION / "benchmarks" / "answer-quality.yaml"
PACKET_SCHEMA_PATH = EVALUATION / "schemas" / "human-review-packet.schema.json"

SCALE = {
    "0": "unsupported, harmful, or wholly incorrect",
    "1": "major errors or omissions",
    "2": "partly correct but materially incomplete",
    "3": "correct with minor omissions",
    "4": "fully supported and useful",
    "not_applicable": "dimension does not apply to this case",
}

DIMENSIONS = {
    "accuracy": "Are the factual statements supported by the supplied source?",
    "completeness": "Does the answer include the required claims for this case?",
    "attribution": "Do the citations support the answer and stay within the supplied source?",
    "edgeCaseHandling": "Does the answer handle the case-specific edge condition safely?",
    "conflictHandling": "Does the answer identify unresolved disagreement when the case requires it?",
    "uncertainty": "Does the answer abstain or qualify its conclusion when the evidence is insufficient?",
}

INSTRUCTIONS = [
    "Review only the question, supplied source, gold requirements, and answer in this packet.",
    "Do not attempt to identify the source condition or answer-generating model.",
    "Score each dimension from 0 to 4, or use not_applicable when the dimension does not apply.",
    "Use a reviewer role, not a personal name, in evaluator.identity.",
    "Replace the template scores, decision, notes, evidence, and evaluatedAt as appropriate.",
    "Return the completed judgmentTemplate as one standalone JSON file.",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def iso_time(value: str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("--created-at must include a timezone")
    return value


def judgment_template(run_id: str, review_id: str, created_at: str) -> dict:
    return {
        "schemaVersion": 1,
        "runId": run_id,
        "responseId": review_id,
        "evaluator": {"type": "human", "identity": "reviewer-role"},
        "rubricVersion": "answer-quality-1.0.0",
        "scores": {dimension: "not_applicable" for dimension in DIMENSIONS},
        "decision": "needs-review",
        "notes": "Replace with a concise explanation of the scores.",
        "evidence": ["Replace with specific supported or unsupported claims."],
        "evaluatedAt": created_at,
    }


def prepare(run: Path, results: Path, output: Path, seed: int, created_at: str) -> dict:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output}")
    manifest = load_json(run / "share" / "manifest.json")
    condition_map = load_json(run / "private" / "condition-map.json")
    import_report = load_json(results / "import-report.json")
    suite = load_yaml(SUITE_PATH)
    schema = load_json(PACKET_SCHEMA_PATH)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    if manifest["runId"] != import_report["runId"] or manifest["runId"] != condition_map["runId"]:
        raise ValueError("run, import report, and condition map IDs do not match")

    cases = {case["id"]: case for case in suite["cases"]}
    packet_paths = {
        (entry["caseId"], entry["blindedCondition"]): run / "share" / entry["file"]
        for entry in manifest["packets"]
    }
    responses = list(import_report["responses"])
    random.Random(seed).shuffle(responses)
    private_records: list[dict] = []
    share_records: list[dict] = []

    for number, item in enumerate(responses, start=1):
        review_id = f"review-{number:03d}"
        response = load_json(results / "responses" / f"{item['responseId']}.json")
        packet = load_json(packet_paths[(item["caseId"], item["blindedCondition"])])
        condition = condition_map["conditions"][item["blindedCondition"]]
        case = cases[item["caseId"]]
        expectation = case["expectations"][condition]
        claims = {claim["id"]: claim for claim in case.get("claims", [])}
        review_packet = {
            "schemaVersion": 1,
            "runId": manifest["runId"],
            "reviewId": review_id,
            "question": packet["question"],
            "answer": response["answer"],
            "citations": response["citations"],
            "source": {
                "citationIds": packet["source"]["citationIds"],
                "content": packet["source"]["content"],
            },
            "gold": {
                "expectedBehavior": expectation["behavior"],
                **({"rationale": expectation["rationale"]} if expectation.get("rationale") else {}),
                "requiredClaims": [
                    {"id": claim_id, "text": claims[claim_id]["text"]}
                    for claim_id in expectation.get("requiredClaimIds", [])
                ],
                "prohibitedClaims": [
                    {"id": claim["id"], "text": claim["text"]}
                    for claim in case.get("prohibitedClaims", [])
                ],
            },
            "rubric": {"version": "answer-quality-1.0.0", "scale": SCALE, "dimensions": DIMENSIONS},
            "instructions": INSTRUCTIONS,
            "judgmentTemplate": judgment_template(manifest["runId"], review_id, created_at),
        }
        errors = sorted(validator.iter_errors(review_packet), key=lambda error: list(error.path))
        if errors:
            raise ValueError(f"invalid review packet {review_id}: " + "; ".join(error.message for error in errors))
        filename = f"{review_id}.json"
        write_json(output / "share" / "packets" / filename, review_packet)
        share_records.append({"reviewId": review_id, "file": f"packets/{filename}"})
        private_records.append(
            {
                "reviewId": review_id,
                "responseId": item["responseId"],
                "generatorId": item["generatorId"],
                "caseId": item["caseId"],
                "blindedCondition": item["blindedCondition"],
                "condition": condition,
            }
        )

    share_manifest = {
        "schemaVersion": 1,
        "runId": manifest["runId"],
        "createdAt": created_at,
        "reviewCount": len(share_records),
        "reviews": share_records,
    }
    private_map = {
        "schemaVersion": 1,
        "runId": manifest["runId"],
        "seed": seed,
        "warning": "Do not provide this file to blinded reviewers.",
        "reviews": private_records,
    }
    write_json(output / "share" / "manifest.json", share_manifest)
    write_json(output / "private" / "review-map.json", private_map)
    (output / "share" / "README.md").write_text(
        "# Blinded human-review packets\n\n"
        "Give reviewers only this `share` directory. Each reviewer should complete the "
        "`judgmentTemplate` in every packet and return one JSON file per review ID. "
        "Do not expose `../private/review-map.json` until all reviews are complete.\n",
        encoding="utf-8",
    )
    print(f"Prepared {len(share_records)} blinded human-review packets in {output}")
    return share_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--results", type=Path, help="Import results; defaults to RUN/results")
    parser.add_argument("--output", type=Path, help="New or empty review directory; defaults to RUN/human-review")
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--created-at", help="ISO 8601 timestamp; defaults to current UTC time")
    args = parser.parse_args()
    run = args.run.resolve()
    try:
        prepare(
            run,
            (args.results or run / "results").resolve(),
            (args.output or run / "human-review").resolve(),
            args.seed,
            iso_time(args.created_at),
        )
    except (FileExistsError, FileNotFoundError, KeyError, ValueError, json.JSONDecodeError) as error:
        print(f"Human-review preparation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
