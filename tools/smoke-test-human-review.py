#!/usr/bin/env python3
"""Exercise blinded human review and comparison reporting without model calls."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREPARE = ROOT / "tools" / "prepare-human-review.py"
REPORT = ROOT / "tools" / "generate-evaluation-comparison.py"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--results", required=True, type=Path)
    args = parser.parse_args()
    run = args.run.resolve()
    results = args.results.resolve()
    with tempfile.TemporaryDirectory(prefix="northstar-human-review-smoke-") as temp:
        root = Path(temp)
        review = root / "review"
        judgments = root / "judgments"
        comparison = root / "comparison"
        subprocess.run(
            [
                sys.executable, str(PREPARE), "--run", str(run), "--results", str(results),
                "--output", str(review), "--seed", "20261026", "--created-at", "2026-10-26T00:00:00Z",
            ],
            check=True,
        )
        manifest = load_json(review / "share" / "manifest.json")
        for entry in manifest["reviews"]:
            packet = load_json(review / "share" / entry["file"])
            judgment = packet["judgmentTemplate"]
            judgment["evaluator"]["identity"] = "documentation-reviewer"
            judgment["scores"] = {dimension: 4 for dimension in judgment["scores"]}
            judgment["decision"] = "pass"
            judgment["notes"] = "Synthetic judgment used only to test report mechanics."
            judgment["evidence"] = ["smoke-test-fixture"]
            write_json(judgments / f"{entry['reviewId']}.json", judgment)
        subprocess.run(
            [
                sys.executable, str(REPORT), "--run", str(run), "--results", str(results),
                "--review", str(review), "--judgments", str(judgments), "--output", str(comparison),
                "--generated-at", "2026-10-26T00:00:00Z",
            ],
            check=True,
        )
        report = load_json(comparison / "comparison-report.json")
        expected = len(manifest["reviews"])
        if report["coverage"] != {
            "responses": expected,
            "humanJudgments": expected,
            "responsesWithHumanReview": expected,
            "missingHumanReview": [],
        }:
            raise RuntimeError(f"unexpected human-review coverage: {report['coverage']}")
        if len(report["pairedComparisons"]) != expected // 2:
            raise RuntimeError("comparison report did not produce one paired result per case")
        if any(item["difference"] != 0 for item in report["pairedComparisons"]):
            raise RuntimeError("equal synthetic judgments should produce zero paired differences")
        if not (comparison / "comparison-report.md").exists():
            raise RuntimeError("Markdown comparison report was not generated")
    print("Validated blinded human-review packets, judgment import, and comparison reports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
