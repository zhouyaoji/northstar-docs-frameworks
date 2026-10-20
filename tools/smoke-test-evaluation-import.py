#!/usr/bin/env python3
"""Exercise response import and deterministic grading without model calls."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SUITE_PATH = ROOT / "evaluation" / "benchmarks" / "answer-quality.yaml"
IMPORTER = ROOT / "tools" / "import-evaluation-responses.py"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def build_responses(run: Path, destination: Path, add_bad_citation: bool = False) -> None:
    manifest = load_json(run / "share" / "manifest.json")
    condition_map = load_json(run / "private" / "condition-map.json")["conditions"]
    suite = yaml.safe_load(SUITE_PATH.read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in suite["cases"]}
    for index, entry in enumerate(manifest["packets"]):
        packet = load_json(run / "share" / entry["file"])
        response = packet["responseTemplate"]
        response["responseId"] = (
            f"{manifest['runId']}-{entry['caseId']}-{entry['blindedCondition']}-smoke-model"
        )
        response["generator"] = {
            "provider": "northstar-smoke",
            "model": "fixture-1",
            "interface": "manual-import",
            "parameters": {},
        }
        response["answer"] = "Synthetic response used only to test import mechanics."
        condition = condition_map[entry["blindedCondition"]]
        response["citations"] = list(
            cases[entry["caseId"]]["expectations"][condition]["requiredSourceIds"]
        )
        if add_bad_citation and index == 0:
            response["citations"] = ["not-in-the-packet"]
        write_json(destination / f"{response['responseId']}.json", response)


def run_import(run: Path, responses: Path, output: Path) -> dict:
    subprocess.run(
        [
            sys.executable,
            str(IMPORTER),
            "--run",
            str(run),
            "--responses",
            str(responses),
            "--output",
            str(output),
            "--evaluated-at",
            "2026-10-19T00:00:00Z",
        ],
        check=True,
    )
    return load_json(output / "import-report.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    args = parser.parse_args()
    run = args.run.resolve()
    with tempfile.TemporaryDirectory(prefix="northstar-import-smoke-") as temp:
        root = Path(temp)
        valid_responses = root / "valid-responses"
        valid_results = root / "valid-results"
        build_responses(run, valid_responses)
        valid_report = run_import(run, valid_responses, valid_results)
        expected = valid_report["counts"]["expectedPackets"]
        if valid_report["counts"] != {
            "expectedPackets": expected,
            "responseFiles": expected,
            "imported": expected,
            "invalid": 0,
            "missing": 0,
        }:
            raise RuntimeError(f"unexpected valid import counts: {valid_report['counts']}")
        if any(item["deterministicDecision"] != "pass" for item in valid_report["responses"]):
            raise RuntimeError("valid fixture did not pass deterministic checks")

        bad_responses = root / "bad-citation-responses"
        bad_results = root / "bad-citation-results"
        build_responses(run, bad_responses, add_bad_citation=True)
        bad_report = run_import(run, bad_responses, bad_results)
        if sum(item["deterministicDecision"] == "fail" for item in bad_report["responses"]) != 1:
            raise RuntimeError("disallowed citation was not graded as a deterministic failure")
    print("Validated response import, completeness accounting, and deterministic citation grading.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
