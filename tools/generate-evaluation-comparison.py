#!/usr/bin/env python3
"""Validate human judgments and generate unblinded Northstar comparison reports."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
EVALUATION = ROOT / "evaluation"
SUITE_PATH = EVALUATION / "benchmarks" / "answer-quality.yaml"
JUDGMENT_SCHEMA_PATH = EVALUATION / "schemas" / "judgment.schema.yaml"
REPORT_SCHEMA_PATH = EVALUATION / "schemas" / "comparison-report.schema.json"
DIMENSIONS = ["accuracy", "completeness", "attribution", "edgeCaseHandling", "conflictHandling", "uncertainty"]


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
        raise ValueError("--generated-at must include a timezone")
    return value


def schema_errors(validator: Draft202012Validator, value: object) -> list[str]:
    errors = []
    for error in sorted(validator.iter_errors(value), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.path) or "<root>"
        errors.append(f"schema error at {location}: {error.message}")
    return errors


def mean_or_none(values: list[int]) -> float | None:
    return round(statistics.mean(values), 3) if values else None


def judgment_score(judgment: dict) -> float | None:
    values = [value for value in judgment["scores"].values() if isinstance(value, int)]
    return mean_or_none(values)


def aggregate(records: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for record in records:
        groups[(record["evaluatorType"], record["generatorId"], record["condition"], record["category"])].append(record)
    output = []
    for (evaluator_type, generator_id, condition, category), items in sorted(groups.items()):
        dimension_values = {
            dimension: [
                judgment["scores"][dimension]
                for item in items
                for judgment in item["judgments"]
                if isinstance(judgment["scores"][dimension], int)
            ]
            for dimension in DIMENSIONS
        }
        decisions = Counter(
            judgment["decision"] for item in items for judgment in item["judgments"]
        )
        output.append(
            {
                "evaluatorType": evaluator_type,
                "generatorId": generator_id,
                "condition": condition,
                "category": category,
                "responseCount": len({item["responseId"] for item in items}),
                "judgmentCount": sum(len(item["judgments"]) for item in items),
                "dimensionAverages": {
                    dimension: mean_or_none(values) for dimension, values in dimension_values.items()
                },
                "decisionCounts": {name: decisions.get(name, 0) for name in ("pass", "needs-review", "fail")},
            }
        )
    return output


def paired_comparisons(individual: list[dict]) -> list[dict]:
    by_pair: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for item in individual:
        for judgment in item["humanJudgments"]:
            score = judgment_score(judgment)
            if score is not None:
                by_pair[(item["generatorId"], item["caseId"])][item["condition"]].append(score)
    output = []
    for (generator_id, case_id), conditions in sorted(by_pair.items()):
        if not conditions.get("documentation") or not conditions.get("aipp"):
            continue
        documentation = round(statistics.mean(conditions["documentation"]), 3)
        aipp = round(statistics.mean(conditions["aipp"]), 3)
        output.append(
            {
                "generatorId": generator_id,
                "caseId": case_id,
                "documentationScore": documentation,
                "aippScore": aipp,
                "difference": round(aipp - documentation, 3),
                "note": "Descriptive paired difference only; do not interpret as statistical significance.",
            }
        )
    return output


def markdown(report: dict) -> str:
    coverage = report["coverage"]
    lines = [
        "# Northstar AIPP answer-quality comparison",
        "",
        f"Run: `{report['runId']}`  ",
        f"Generated: `{report['generatedAt']}`",
        "",
        "## Review coverage",
        "",
        f"- Imported responses: {coverage['responses']}",
        f"- Human judgments: {coverage['humanJudgments']}",
        f"- Responses with human review: {coverage['responsesWithHumanReview']}",
        f"- Responses missing human review: {len(coverage['missingHumanReview'])}",
        "",
        "## Aggregate results",
        "",
        "| Evaluator | Generator | Condition | Category | Responses | Judgments | Accuracy | Completeness | Attribution | Edge cases | Conflicts | Uncertainty |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in report["aggregates"]:
        averages = item["dimensionAverages"]
        display = lambda value: "—" if value is None else f"{value:.2f}"
        lines.append(
            "| " + " | ".join(
                [
                    item["evaluatorType"], item["generatorId"], item["condition"], item["category"],
                    str(item["responseCount"]), str(item["judgmentCount"]),
                    display(averages["accuracy"]), display(averages["completeness"]),
                    display(averages["attribution"]), display(averages["edgeCaseHandling"]),
                    display(averages["conflictHandling"]), display(averages["uncertainty"]),
                ]
            ) + " |"
        )
    lines.extend([
        "",
        "## Paired human-review differences",
        "",
        "| Generator | Case | Documentation | AIPP | Difference |",
        "|---|---|---:|---:|---:|",
    ])
    for item in report["pairedComparisons"]:
        lines.append(
            f"| {item['generatorId']} | {item['caseId']} | {item['documentationScore']:.2f} | "
            f"{item['aippScore']:.2f} | {item['difference']:+.2f} |"
        )
    if not report["pairedComparisons"]:
        lines.append("| — | No complete human-reviewed pairs yet | — | — | — |")
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.extend(["", "## Individual results", ""])
    for item in report["individualResults"]:
        lines.extend([
            f"### `{item['responseId']}`",
            "",
            f"- Generator: `{item['generatorId']}`",
            f"- Case: `{item['caseId']}` ({item['category']})",
            f"- Condition: `{item['condition']}` (blinded label `{item['blindedCondition']}`)",
            f"- Deterministic decision: `{item['deterministicDecision']}`",
            f"- Human judgments: {len(item['humanJudgments'])}",
            "",
        ])
    return "\n".join(lines) + "\n"


def generate(run: Path, results: Path, review: Path, judgments_dir: Path, output: Path, generated_at: str) -> dict:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output}")
    import_report = load_json(results / "import-report.json")
    review_map_doc = load_json(review / "private" / "review-map.json")
    suite = load_yaml(SUITE_PATH)
    cases = {case["id"]: case for case in suite["cases"]}
    review_map = {item["reviewId"]: item for item in review_map_doc["reviews"]}
    if import_report["runId"] != review_map_doc["runId"]:
        raise ValueError("import report and review map run IDs do not match")

    judgment_validator = Draft202012Validator(load_yaml(JUDGMENT_SCHEMA_PATH), format_checker=FormatChecker())
    human_by_response: dict[str, list[dict]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    errors: list[str] = []
    for path in sorted(judgments_dir.rglob("*.json")) if judgments_dir.exists() else []:
        try:
            judgment = load_json(path)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            errors.append(f"{path.name}: invalid JSON: {error}")
            continue
        file_errors = schema_errors(judgment_validator, judgment)
        review_id = judgment.get("responseId")
        if judgment.get("runId") != import_report["runId"]:
            file_errors.append("runId does not match import report")
        if judgment.get("evaluator", {}).get("type") != "human":
            file_errors.append("evaluator.type must be human")
        if review_id not in review_map:
            file_errors.append("responseId is not a known blinded review ID")
        reviewer = judgment.get("evaluator", {}).get("identity", "")
        if (review_id, reviewer) in seen:
            file_errors.append("duplicate reviewer role for this review ID")
        if file_errors:
            errors.extend(f"{path.name}: {error}" for error in file_errors)
            continue
        seen.add((review_id, reviewer))
        resolved = {**judgment, "responseId": review_map[review_id]["responseId"], "reviewId": review_id}
        human_by_response[resolved["responseId"]].append(resolved)
    if errors:
        raise ValueError("human judgment validation failed: " + "; ".join(errors))

    individual = []
    aggregate_records = []
    for item in import_report["responses"]:
        mapping = next(record for record in review_map.values() if record["responseId"] == item["responseId"])
        deterministic = load_json(results / "deterministic-judgments" / f"{item['responseId']}.json")
        humans = human_by_response.get(item["responseId"], [])
        record = {
            "responseId": item["responseId"],
            "generatorId": item["generatorId"],
            "caseId": item["caseId"],
            "category": cases[item["caseId"]]["category"],
            "condition": mapping["condition"],
            "blindedCondition": item["blindedCondition"],
            "deterministicDecision": deterministic["decision"],
            "humanJudgments": humans,
        }
        individual.append(record)
        aggregate_records.append({**record, "evaluatorType": "deterministic", "judgments": [deterministic]})
        if humans:
            aggregate_records.append({**record, "evaluatorType": "human", "judgments": humans})

    missing = sorted(item["responseId"] for item in individual if not item["humanJudgments"])
    report = {
        "schemaVersion": 1,
        "runId": import_report["runId"],
        "suiteVersion": import_report["suiteVersion"],
        "protocolVersion": import_report["protocolVersion"],
        "generatedAt": generated_at,
        "coverage": {
            "responses": len(individual),
            "humanJudgments": sum(len(item["humanJudgments"]) for item in individual),
            "responsesWithHumanReview": len(individual) - len(missing),
            "missingHumanReview": missing,
        },
        "limitations": [
            "The initial suite is small; paired differences are descriptive and not statistically significant.",
            "Source formats are preserved, so an answer generator may infer which condition it received.",
            "Deterministic checks verify structure and citation identifiers, not semantic correctness.",
            "Human scores reflect the declared reviewer roles and rubric; disagreement remains visible in individual results.",
        ],
        "aggregates": aggregate(aggregate_records),
        "pairedComparisons": paired_comparisons(individual),
        "individualResults": sorted(individual, key=lambda item: item["responseId"]),
    }
    report_validator = Draft202012Validator(load_json(REPORT_SCHEMA_PATH), format_checker=FormatChecker())
    report_errors = schema_errors(report_validator, report)
    if report_errors:
        raise ValueError("generated comparison report is invalid: " + "; ".join(report_errors))
    write_json(output / "comparison-report.json", report)
    (output / "comparison-report.md").write_text(markdown(report), encoding="utf-8")
    print(
        f"Generated comparison report for {len(individual)} responses and "
        f"{report['coverage']['humanJudgments']} human judgments in {output}"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--results", type=Path, help="Import results; defaults to RUN/results")
    parser.add_argument("--review", type=Path, help="Review workspace; defaults to RUN/human-review")
    parser.add_argument("--judgments", type=Path, help="Human judgment files; defaults to REVIEW/judgments")
    parser.add_argument("--output", type=Path, help="New or empty report directory; defaults to RUN/comparison")
    parser.add_argument("--generated-at", help="ISO 8601 timestamp; defaults to current UTC time")
    args = parser.parse_args()
    run = args.run.resolve()
    results = (args.results or run / "results").resolve()
    review = (args.review or run / "human-review").resolve()
    judgments = (args.judgments or review / "judgments").resolve()
    output = (args.output or run / "comparison").resolve()
    try:
        generate(run, results, review, judgments, output, iso_time(args.generated_at))
    except (FileExistsError, FileNotFoundError, KeyError, StopIteration, ValueError, json.JSONDecodeError) as error:
        print(f"Comparison report generation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
