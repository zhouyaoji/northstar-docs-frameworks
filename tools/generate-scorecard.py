#!/usr/bin/env python3
"""Generate deterministic documentation scorecards for all Northstar renderers."""

from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
EVALUATION = ROOT / "evaluation"
OUTPUT = PUBLIC / "scorecard"
BASELINE = EVALUATION / "baselines" / "v1.json"
RENDERERS = (
    "docusaurus",
    "mkdocs",
    "sphinx-rest",
    "sphinx-myst",
    "antora",
    "redocly",
    "mintlify",
)
GENERIC_LINKS = {"click here", "here", "learn more", "read more", "more"}
RISKY_PHRASES = (
    "simply",
    "obviously",
    "as you can see",
    "above-mentioned",
    "below-mentioned",
)
IMPACT_VALUE = {"low": 1, "medium": 2, "high": 3}
EFFORT_VALUE = {"low": 1, "medium": 2, "high": 3}
FEASIBILITY_VALUE = {
    "native": 1.0,
    "configurable": 0.9,
    "plugin": 0.75,
    "custom": 0.6,
    "workaround": 0.35,
    "unsupported": 0.0,
    "unknown": 0.25,
}


@dataclass
class Page:
    path: Path
    title: str = ""
    description: str = ""
    language: str = ""
    headings: list[int] = field(default_factory=list)
    images: list[dict[str, str | None]] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    text: list[str] = field(default_factory=list)
    assistant: bool = False
    redirect: bool = False


class PageParser(HTMLParser):
    def __init__(self, path: Path) -> None:
        super().__init__()
        self.page = Page(path)
        self._title = False
        self._anchor_depth = 0
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag in {"script", "style", "noscript", "template"}:
            self._ignored_depth += 1
        if tag == "html":
            self.page.language = values.get("lang") or ""
        elif tag == "title":
            self._title = True
        elif tag == "meta" and (values.get("name") or "").lower() == "description":
            self.page.description = values.get("content") or ""
        elif tag == "meta" and (values.get("http-equiv") or "").lower() == "refresh":
            self.page.redirect = True
        elif re.fullmatch(r"h[1-6]", tag):
            self.page.headings.append(int(tag[1]))
        elif tag == "img":
            self.page.images.append(values)
        elif tag == "a":
            self._anchor_depth += 1
        if "data-northstar-assistant" in values:
            self.page.assistant = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._title = False
        elif tag == "a" and self._anchor_depth:
            self._anchor_depth -= 1
        if tag in {"script", "style", "noscript", "template"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        value = " ".join(data.split())
        if not value:
            return
        self.page.text.append(value)
        if self._title:
            self.page.title += (" " if self.page.title else "") + value
        if self._anchor_depth:
            self.page.links.append(value)


def parse_pages(renderer: str) -> list[Page]:
    pages: list[Page] = []
    for path in sorted((PUBLIC / renderer).rglob("*.html")):
        parser = PageParser(path)
        parser.feed(path.read_text(encoding="utf-8", errors="replace"))
        pages.append(parser.page)
    return pages


def result(criterion: dict, renderer: str, passed: bool | None, evidence: str) -> dict:
    status = "not_evaluated" if passed is None else ("pass" if passed else "fail")
    return {
        "criterion": criterion["id"],
        "category": criterion["category"],
        "method": criterion["method"],
        "renderer": renderer,
        "status": status,
        "weight": criterion["weight"],
        "blocking": criterion["blocking"],
        "evidence": evidence,
    }


def rubric_metadata(rubric: dict) -> tuple[dict[str, str], dict[str, dict]]:
    groups: dict[str, str] = {}
    for group_id, group in rubric["scoreGroups"].items():
        for criterion_id in group["criteria"]:
            if criterion_id in groups:
                raise ValueError(f"criterion appears in multiple score groups: {criterion_id}")
            groups[criterion_id] = group_id
    criteria_ids = {criterion["id"] for criterion in rubric["criteria"]}
    if set(groups) != criteria_ids:
        raise ValueError(
            f"score-group mapping mismatch; missing={sorted(criteria_ids - set(groups))}, "
            f"unknown={sorted(set(groups) - criteria_ids)}"
        )
    return groups, rubric.get("recommendations", {})


def decorate_result(item: dict, groups: dict[str, str], recommendations: dict[str, dict]) -> dict:
    item["scoreGroup"] = groups[item["criterion"]]
    recommendation = recommendations.get(item["criterion"])
    item["providedBy"] = recommendation.get("providedBy") if recommendation else None
    item["recommendation"] = recommendation if item["status"] == "fail" else None
    return item


def evaluate_shared_content(criteria: list[dict]) -> list[dict]:
    source_files = sorted((ROOT / "content" / "markdown").rglob("*.md"))
    evaluated_files = [path for path in source_files if path.name != "style-guide.md"]
    normalized = " ".join(
        path.read_text(encoding="utf-8", errors="replace").lower()
        for path in evaluated_files
    )
    risky = [phrase for phrase in RISKY_PHRASES if phrase in normalized]
    checks: dict[str, tuple[bool | None, str]] = {
        "localization.risky_phrases": (
            not risky,
            f"checked {len(evaluated_files)} canonical content files; flagged phrases: {', '.join(risky) or 'none'}; excluded the style guide that defines the rule",
        ),
        "translation.locale_coverage": (None, "no translated locale has been declared"),
    }
    return [
        result(criterion, "shared-content", *checks.get(criterion["id"], (None, "review evidence has not been supplied")))
        for criterion in criteria
    ]


def heading_structure_valid(page: Page) -> bool:
    if 1 not in page.headings:
        return False
    content_headings = page.headings[page.headings.index(1) :]
    return all(current <= previous + 1 for previous, current in zip(content_headings, content_headings[1:]))


def corpus_sections(text: str) -> list[tuple[str, str]]:
    sections = []
    for section in text.split("\n---\n"):
        match = re.search(r"^#\s+(.+)$", section, re.MULTILINE)
        if match:
            sections.append((match.group(1).strip(), section))
    return sections


def retrieve(question: str, sections: list[tuple[str, str]]) -> list[str]:
    terms = {term for term in re.findall(r"[a-z0-9]+", question.lower()) if len(term) > 2}
    ranked = []
    for title, body in sections:
        lower = f"{title} {body}".lower()
        score = sum(lower.count(term) for term in terms)
        if score:
            ranked.append((score, title))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [title for _, title in ranked[:3]]


def evaluate_renderer(renderer: str, criteria: list[dict], expected_titles: list[str], benchmarks: list[dict]) -> list[dict]:
    directory = PUBLIC / renderer
    pages = parse_pages(renderer) if directory.is_dir() else []
    content_pages = [page for page in pages if page.headings]
    llms_path = directory / "llms.txt"
    full_path = directory / "llms-full.txt"
    llms = llms_path.read_text(encoding="utf-8") if llms_path.is_file() else ""
    full = full_path.read_text(encoding="utf-8") if full_path.is_file() else ""
    sections = corpus_sections(full)
    normalized_text = " ".join(" ".join(page.text) for page in content_pages).lower()
    checks: dict[str, tuple[bool | None, str]] = {}

    checks["publication.renderer_output"] = (bool(pages), f"{len(pages)} generated HTML page(s)")
    indexed_titles = ["Northstar API reference"] if renderer == "redocly" else expected_titles
    missing_titles = [title for title in indexed_titles if title not in llms]
    checks["structured.expected_pages"] = (
        not missing_titles,
        "all canonical titles present" if not missing_titles else f"missing: {', '.join(missing_titles)}",
    )
    titles = [page.title.strip() for page in pages]
    duplicate_titles = sorted(title for title, count in Counter(titles).items() if title and count > 1)
    checks["structured.page_titles"] = (
        bool(pages) and all(titles) and not duplicate_titles,
        f"{len(titles)} title(s); duplicates: {', '.join(duplicate_titles) or 'none'}",
    )
    missing_language = [str(page.path.relative_to(PUBLIC)) for page in pages if not page.language]
    checks["accessibility.document_language"] = (
        bool(pages) and not missing_language,
        f"{len(missing_language)} page(s) missing lang",
    )
    bad_headings = [str(page.path.relative_to(PUBLIC)) for page in content_pages if not heading_structure_valid(page)]
    checks["accessibility.heading_structure"] = (
        bool(content_pages) and not bad_headings,
        f"{len(bad_headings)} page(s) with invalid heading structure",
    )
    images = [image for page in content_pages for image in page.images]
    missing_alt = [image for image in images if "alt" not in image]
    checks["accessibility.image_alternatives"] = (
        not missing_alt,
        f"{len(images)} image(s); {len(missing_alt)} missing alt attributes",
    )
    checks["seo.page_titles"] = (bool(pages) and all(titles), f"{sum(bool(title) for title in titles)}/{len(titles)} pages titled")
    missing_descriptions = [str(page.path.relative_to(PUBLIC)) for page in content_pages if not page.description.strip()]
    checks["seo.meta_descriptions"] = (
        bool(content_pages) and not missing_descriptions,
        f"{len(missing_descriptions)} content page(s) missing descriptions",
    )
    generic = sorted({label for page in content_pages for label in page.links if label.strip().lower() in GENERIC_LINKS})
    checks["taxonomy.descriptive_links"] = (not generic, f"generic labels: {', '.join(generic) or 'none'}")
    valid_languages = [page.language for page in pages if re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", page.language)]
    checks["localization.language_metadata"] = (
        bool(pages) and len(valid_languages) == len(pages),
        f"{len(valid_languages)}/{len(pages)} pages use recognizable language tags",
    )
    risky = [phrase for phrase in RISKY_PHRASES if phrase in normalized_text]
    checks["localization.risky_phrases"] = (not risky, f"flagged phrases: {', '.join(risky) or 'none'}")
    checks["translation.locale_coverage"] = (None, "no translated locale has been declared")
    checks["ai.llms_exports"] = (
        bool(llms.strip()) and bool(full.strip()),
        f"llms.txt={len(llms)} bytes; llms-full.txt={len(full)} bytes",
    )
    assistant_pages = [page for page in content_pages if not page.redirect]
    without_assistant = [str(page.path.relative_to(PUBLIC)) for page in assistant_pages if not page.assistant]
    checks["ai.assistant_installed"] = (
        bool(assistant_pages) and not without_assistant,
        f"{len(assistant_pages) - len(without_assistant)}/{len(assistant_pages)} non-redirect content pages include the assistant",
    )
    benchmark_failures = []
    for benchmark in benchmarks:
        actual = retrieve(benchmark["question"], sections)
        if benchmark["expectedTitle"] not in actual:
            benchmark_failures.append(f"{benchmark['id']}: expected {benchmark['expectedTitle']!r} in top 3, got {actual!r}")
    checks["ai.retrieval_benchmarks"] = (
        bool(benchmarks) and not benchmark_failures,
        f"{len(benchmarks) - len(benchmark_failures)}/{len(benchmarks)} retrieval benchmarks passed"
        + (f"; {'; '.join(benchmark_failures)}" if benchmark_failures else ""),
    )

    return [
        result(criterion, renderer, *checks.get(criterion["id"], (None, "evaluator not implemented")))
        for criterion in criteria
    ]


def evaluate_aipp(criteria: list[dict], expected_titles: list[str], benchmarks: list[dict]) -> list[dict]:
    directory = PUBLIC / "aipp"
    object_path = directory / "northstar-platform.json"
    object_data = json.loads(object_path.read_text(encoding="utf-8")) if object_path.is_file() else {}
    sections = object_data.get("content", {}).get("sections", [])
    statements = object_data.get("content", {}).get("statements", [])
    citations = object_data.get("content", {}).get("citations", [])
    statements_by_id = {item.get("statement_id"): item for item in statements}
    retrieval_sections = [
        (
            section.get("title", ""),
            "\n".join(
                str(statements_by_id.get(statement_id, {}).get("text", ""))
                for statement_id in section.get("statement_ids", [])
            ),
        )
        for section in sections
    ]
    checks: dict[str, tuple[bool | None, str]] = {}
    overview = directory / "index.html"
    checks["publication.renderer_output"] = (
        overview.is_file(),
        "human-readable AIPP overview published" if overview.is_file() else "AIPP overview missing",
    )
    section_titles = {section.get("title") for section in sections}
    checks["ai.aipp_structured_object"] = (
        object_path.is_file() and set(expected_titles) == section_titles and bool(statements),
        f"{len(sections)}/{len(expected_titles)} canonical sections and {len(statements)} statements compiled",
    )
    citation_ids = {item.get("source_id") for item in citations}
    missing_source_refs = sorted({source_id for item in statements for source_id in item.get("source_ids", []) if source_id not in citation_ids})
    provenance_fields = {"source_id", "source_type", "format", "authority", "owner", "topics", "lifecycle", "locator", "retrieval"}
    incomplete_citations = [item.get("source_id", "<unknown>") for item in citations if not provenance_fields.issubset(item)]
    checks["ai.aipp_source_provenance"] = (
        bool(statements) and all(item.get("source_ids") for item in statements) and not missing_source_refs and not incomplete_citations,
        f"{len(statements)} statements cite {len(citations)} registered sources; missing references: {missing_source_refs or 'none'}; incomplete provenance: {incomplete_citations or 'none'}",
    )
    sidecars = [yaml.safe_load(path.read_text(encoding="utf-8")) for path in sorted((ROOT / "aipp" / "entries").glob("*.yaml"))]
    approved = [item for item in sidecars if item.get("review", {}).get("state") == "approved-for-demo"]
    ai_only_count = sum(len(item.get("aiOnlyStatements", [])) for item in approved)
    checks["ai.aipp_reviewed_sidecars"] = (
        len(approved) == len(expected_titles),
        f"{len(approved)}/{len(expected_titles)} page sidecars approved; {ai_only_count} reviewed AI-only statements",
    )
    unresolved = [item for item in statements if item.get("unresolved") is True]
    checks["ai.aipp_conflict_signaling"] = (
        bool(unresolved),
        f"{len(unresolved)} explicitly unresolved source-conflict statement(s)",
    )
    required_artifacts = (
        "discovery.json", "feed.json", "northstar-platform.json", "source-report.json", "schemas/sidecar.schema.yaml"
    )
    missing_artifacts = [name for name in required_artifacts if not (directory / name).is_file()]
    checks["ai.aipp_discovery_feed"] = (
        not missing_artifacts,
        "all discovery artifacts published" if not missing_artifacts else f"missing: {', '.join(missing_artifacts)}",
    )
    benchmark_failures = []
    for benchmark in benchmarks:
        actual = retrieve(benchmark["question"], retrieval_sections)
        if benchmark["expectedTitle"] not in actual:
            benchmark_failures.append(f"{benchmark['id']}: expected {benchmark['expectedTitle']!r} in top 3, got {actual!r}")
    checks["ai.retrieval_benchmarks"] = (
        bool(benchmarks) and not benchmark_failures,
        f"{len(benchmarks) - len(benchmark_failures)}/{len(benchmarks)} retrieval benchmarks passed"
        + (f"; {'; '.join(benchmark_failures)}" if benchmark_failures else ""),
    )
    return [
        result(criterion, "aipp", *checks.get(criterion["id"], (None, "criterion does not apply to the AIPP knowledge layer")))
        for criterion in criteria
    ]


def scores(results: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in results:
        if item["status"] in {"pass", "fail"} and item["weight"] > 0:
            grouped[item["category"]].append(item)

    def weighted(items: list[dict]) -> float | None:
        denominator = sum(item["weight"] for item in items)
        if not denominator:
            return None
        numerator = sum(item["weight"] for item in items if item["status"] == "pass")
        return round(100 * numerator / denominator, 1)

    evaluated = [item for item in results if item["status"] in {"pass", "fail"} and item["weight"] > 0]
    group_results: dict[str, list[dict]] = defaultdict(list)
    group_totals: Counter[str] = Counter()
    group_evaluated: Counter[str] = Counter()
    for item in results:
        group_totals[item["scoreGroup"]] += 1
        if item["status"] in {"pass", "fail"}:
            group_evaluated[item["scoreGroup"]] += 1
    for item in evaluated:
        group_results[item["scoreGroup"]].append(item)
    return {
        "overall": weighted(evaluated),
        "groups": {group: weighted(items) for group, items in sorted(group_results.items())},
        "groupCoverage": {
            group: {"evaluated": group_evaluated[group], "total": total}
            for group, total in sorted(group_totals.items())
        },
        "categories": {category: weighted(items) for category, items in sorted(grouped.items())},
        "blockingFailures": [item["criterion"] for item in results if item["blocking"] and item["status"] == "fail"],
    }


def prioritized_improvements(renderer_reports: list[dict]) -> list[dict]:
    improvements = []
    for renderer in renderer_reports:
        for item in renderer["results"]:
            recommendation = item.get("recommendation")
            if not recommendation:
                continue
            impact = recommendation["impact"]
            effort = recommendation["effort"]
            feasibility = recommendation["feasibility"]
            priority_score = round(
                10 * IMPACT_VALUE[impact] * FEASIBILITY_VALUE[feasibility] / EFFORT_VALUE[effort],
                1,
            )
            improvements.append(
                {
                    "renderer": renderer["name"],
                    "criterion": item["criterion"],
                    "scoreGroup": item["scoreGroup"],
                    "category": item["category"],
                    "summary": recommendation["summary"],
                    "impact": impact,
                    "effort": effort,
                    "feasibility": feasibility,
                    "providedBy": recommendation["providedBy"],
                    "fixOwner": recommendation["fixOwner"],
                    "scoreOpportunity": item["weight"],
                    "priorityScore": priority_score,
                    "detailAnchor": f"{renderer['name']}-{item['scoreGroup']}-{item['criterion']}",
                }
            )
    improvements.sort(key=lambda item: (-item["priorityScore"], -item["scoreOpportunity"], item["renderer"], item["criterion"]))
    for index, improvement in enumerate(improvements, start=1):
        improvement["priority"] = index
    return improvements


def render_markdown(report: dict) -> str:
    content_score = report["sharedContent"]["scores"]["groups"].get("content")
    lines = [
        "# Northstar documentation scorecard",
        "",
        f"Rubric version: `{report['rubricVersion']}`  ",
        f"Commit: `{report['commit']}`  ",
        f"Generated: `{report['generatedAt']}`",
        "",
        "> Content is scored once. Renderer implementation, AI readiness, and publication operations are scored per renderer. Planned AI and human criteria are not scored.",
        "",
        f"Shared content quality: **{content_score:.1f}** ({report['sharedContent']['scores']['groupCoverage']['content']['evaluated']}/{report['sharedContent']['scores']['groupCoverage']['content']['total']} criteria evaluated)" if content_score is not None else "Shared content quality: **Not evaluated**",
        "",
        "| Implementation / knowledge layer | Renderer implementation | AI readiness | Publication operations | Blocking failures |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for renderer in report["renderers"]:
        groups = renderer["scores"]["groups"]
        coverage = renderer["scores"]["groupCoverage"]
        renderer_score = f"{groups['renderer']:.1f}" if groups.get("renderer") is not None else "Not evaluated"
        ai_score = f"{groups['ai']:.1f}" if groups.get("ai") is not None else "Not evaluated"
        publication_score = f"{groups['publication']:.1f}" if groups.get("publication") is not None else "Not evaluated"
        lines.append(
            f"| {renderer['name']} | {renderer_score} ({coverage['renderer']['evaluated']}/{coverage['renderer']['total']}) | "
            f"{ai_score} ({coverage['ai']['evaluated']}/{coverage['ai']['total']}) | "
            f"{publication_score} ({coverage['publication']['evaluated']}/{coverage['publication']['total']}) | "
            f"{len(renderer['scores']['blockingFailures'])} |"
        )
    lines.extend(["", "## Prioritized improvements", "", "| Priority | Renderer | Improvement | Group | Impact | Effort | Feasibility | Opportunity |", "| ---: | --- | --- | --- | --- | --- | --- | ---: |"])
    for improvement in report["improvements"]:
        lines.append(
            f"| {improvement['priority']} | {improvement['renderer']} | {improvement['summary']} | "
            f"{improvement['scoreGroup']} | {improvement['impact']} | {improvement['effort']} | "
            f"{improvement['feasibility']} | +{improvement['scoreOpportunity']} |"
        )
    lines.extend(["", "## Results by renderer", ""])
    for renderer in report["renderers"]:
        lines.extend([f"### {renderer['name']}", "", "| Status | Group | Category | Criterion | Evidence and recommendation |", "| --- | --- | --- | --- | --- |"])
        for item in renderer["results"]:
            detail = item["evidence"]
            if item.get("recommendation"):
                recommendation = item["recommendation"]
                detail += f" Recommended: {recommendation['summary']} Owner: {recommendation['fixOwner']}."
            lines.append(f"| {item['status']} | {item['scoreGroup']} | {item['category']} | `{item['criterion']}` | {detail.replace('|', '\\|')} |")
        lines.append("")
    return "\n".join(lines)


def render_html(report: dict) -> str:
    content_score = report["sharedContent"]["scores"]["groups"].get("content")
    content_coverage = report["sharedContent"]["scores"]["groupCoverage"]["content"]
    def score_cell(renderer: dict, group: str) -> str:
        score = renderer["scores"]["groups"].get(group)
        coverage = renderer["scores"]["groupCoverage"][group]
        label = f"{score:.1f}" if score is not None else "Not evaluated"
        return f"<td>{label}<small>{coverage['evaluated']}/{coverage['total']} criteria</small></td>"

    matrix_rows = "".join(
        f'<tr><th scope="row"><a href="#{html.escape(renderer["name"])}">{html.escape(renderer["name"])}</a></th>'
        f'{score_cell(renderer, "renderer")}{score_cell(renderer, "ai")}{score_cell(renderer, "publication")}</tr>'
        for renderer in report["renderers"]
    )
    improvement_rows = "".join(
        f'<tr><td>{item["priority"]}</td><td>{html.escape(item["renderer"])}</td>'
        f'<td><a href="#{html.escape(item["detailAnchor"])}">{html.escape(item["summary"])}</a></td>'
        f'<td>{html.escape(item["scoreGroup"])}</td><td>{html.escape(item["impact"])}</td>'
        f'<td>{html.escape(item["effort"])}</td><td>{html.escape(item["feasibility"])}</td>'
        f'<td>{html.escape(item["fixOwner"])}</td><td>+{item["scoreOpportunity"]}</td></tr>'
        for item in report["improvements"]
    ) or '<tr><td colspan="8">No implemented criteria currently require improvement.</td></tr>'
    sections = []
    for renderer in report["renderers"]:
        rows = "".join(
            f'<tr id="{html.escape(renderer["name"] + "-" + item["scoreGroup"] + "-" + item["criterion"])}"><td><span class="{item["status"]}">{html.escape(item["status"].replace("_", " "))}</span></td><td>{html.escape(item["scoreGroup"])}</td><td>{html.escape(item["category"])}</td><td><code>{html.escape(item["criterion"])}</code></td><td>{html.escape(item["evidence"])}{("<br><strong>Recommended:</strong> " + html.escape(item["recommendation"]["summary"]) + "<br><small>Owner: " + html.escape(item["recommendation"]["fixOwner"]) + " · Provided by: " + html.escape(item["recommendation"]["providedBy"]) + "</small>") if item.get("recommendation") else ""}</td></tr>'
            for item in renderer["results"]
        )
        sections.append(f'<section id="{html.escape(renderer["name"])}"><h2>{html.escape(renderer["name"])}</h2><div class="table"><table><thead><tr><th>Status</th><th>Group</th><th>Category</th><th>Criterion</th><th>Evidence</th></tr></thead><tbody>{rows}</tbody></table></div></section>')
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Repeatable documentation quality evidence for the Northstar renderer comparison."><title>Northstar documentation scorecard</title><style>
:root{{font-family:system-ui,sans-serif;color-scheme:light dark}}body{{margin:0;background:#071525;color:#ecf5ff}}nav,main{{max-width:1180px;margin:auto;padding:1.2rem}}a{{color:#78d8ff}}h1{{font-size:clamp(2rem,6vw,4rem);margin:.4rem 0}}.lead{{max-width:850px;color:#b9cee3;font-size:1.1rem}}.shared{{background:#0c2034;border:1px solid #31506c;border-radius:14px;padding:1rem;margin:2rem 0}}.shared strong{{font-size:2rem;color:#77e69b}}section{{margin:3rem 0;scroll-margin-top:1rem}}.table{{overflow:auto}}table{{width:100%;border-collapse:collapse;background:#0c2034}}th,td{{text-align:left;vertical-align:top;padding:.7rem;border-bottom:1px solid #31506c}}thead th{{color:#b9cee3}}td small{{display:block;color:#b9cee3;margin-top:.2rem}}.pass{{color:#77e69b}}.fail{{color:#ff9898}}.not_evaluated{{color:#b9cee3}}code{{white-space:nowrap}}tr:target{{outline:2px solid #78d8ff;outline-offset:-2px}}
</style></head><body><nav><a href="../">← Docs Lab</a> · <a href="../aipp/">AIPP overview</a></nav><main><p>DOCUMENTATION QUALITY</p><h1>Northstar scorecard</h1><p class="lead">Four isolated views under rubric {html.escape(report['rubricVersion'])}: shared content quality, renderer implementation, AI readiness, and publication operations. AIPP is evaluated as a knowledge layer, not as an eighth renderer; non-applicable criteria remain not evaluated.</p><div class="shared"><h2>Shared content quality</h2><strong>{content_score:.1f}</strong><p>{content_coverage['evaluated']} of {content_coverage['total']} criteria evaluated once; this score does not advantage any implementation.</p></div><section><h2>Implementation and knowledge-layer comparison</h2><div class="table"><table><thead><tr><th>Implementation / knowledge layer</th><th>Renderer implementation</th><th>AI readiness</th><th>Publication operations</th></tr></thead><tbody>{matrix_rows}</tbody></table></div></section><section><h2>Prioritized improvements</h2><p>Default priority combines impact, effort, and feasibility. Score opportunity is available rubric weight, not a promised gain.</p><div class="table"><table><thead><tr><th>Priority</th><th>Implementation</th><th>Improvement</th><th>Group</th><th>Impact</th><th>Effort</th><th>Feasibility</th><th>Fix owner</th><th>Opportunity</th></tr></thead><tbody>{improvement_rows}</tbody></table></div></section>{''.join(sections)}<p>Commit {html.escape(report['commit'])} · Generated {html.escape(report['generatedAt'])}. Earlier rubric baselines are disabled because scoring groups and AIPP criteria changed. <a href="scorecard.json">JSON</a> · <a href="scorecard.md">Markdown</a></p></main></body></html>'''


def main() -> int:
    if not PUBLIC.is_dir():
        print("public directory does not exist; build the sites first", file=sys.stderr)
        return 1
    rubric = yaml.safe_load((EVALUATION / "rubric.yaml").read_text(encoding="utf-8"))
    benchmark_data = yaml.safe_load((EVALUATION / "benchmarks" / "retrieval.yaml").read_text(encoding="utf-8"))
    manifest = yaml.safe_load((ROOT / "content" / "manifest.yaml").read_text(encoding="utf-8"))
    criteria = rubric["criteria"]
    groups, recommendations = rubric_metadata(rubric)
    expected_titles = [page["title"] for page in manifest["pages"]]
    benchmarks = benchmark_data["benchmarks"]
    baseline = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.is_file() else {"renderers": {}}
    compatible_baseline = baseline.get("rubricVersion") == str(rubric["rubricVersion"])
    renderer_reports = []
    for renderer in RENDERERS:
        renderer_results = [
            decorate_result(item, groups, recommendations)
            for item in evaluate_renderer(renderer, criteria, expected_titles, benchmarks)
            if groups[item["criterion"]] != "content"
        ]
        renderer_scores = scores(renderer_results)
        baseline_score = baseline.get("renderers", {}).get(renderer) if compatible_baseline else None
        renderer_scores["baseline"] = baseline_score
        renderer_scores["baselineDelta"] = (
            round(renderer_scores["overall"] - baseline_score, 1) if baseline_score is not None else None
        )
        renderer_reports.append({"name": renderer, "scores": renderer_scores, "results": renderer_results})
    aipp_results = [
        decorate_result(item, groups, recommendations)
        for item in evaluate_aipp(criteria, expected_titles, benchmarks)
        if groups[item["criterion"]] != "content"
    ]
    renderer_reports.append({"name": "aipp", "scores": scores(aipp_results), "results": aipp_results})
    content_criteria = [criterion for criterion in criteria if groups[criterion["id"]] == "content"]
    content_results = [
        decorate_result(item, groups, recommendations)
        for item in evaluate_shared_content(content_criteria)
    ]
    content_report = {"scores": scores(content_results), "results": content_results}
    improvements = prioritized_improvements(renderer_reports)
    commit = os.environ.get("GITHUB_SHA")
    if not commit:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    report = {
        "schemaVersion": 1,
        "rubricVersion": str(rubric["rubricVersion"]),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "commit": commit,
        "baseline": str(BASELINE.relative_to(ROOT)) if compatible_baseline else None,
        "baselineCompatibility": "compatible" if compatible_baseline else "incompatible-rubric-version",
        "scoringNote": "Content is scored once. Renderer, AI readiness, and publication operations are scored per renderer. Only implemented automated criteria with positive weights contribute.",
        "scoreGroups": rubric["scoreGroups"],
        "sharedContent": content_report,
        "renderers": renderer_reports,
        "improvements": improvements,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "scorecard.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown = render_markdown(report)
    (OUTPUT / "scorecard.md").write_text(markdown + "\n", encoding="utf-8")
    (OUTPUT / "index.html").write_text(render_html(report), encoding="utf-8")
    failing = [renderer["name"] for renderer in renderer_reports if renderer["scores"]["blockingFailures"]]
    print("Generated scorecards for " + ", ".join(RENDERERS) + ", and the AIPP knowledge layer.")
    if failing:
        print("Blocking scorecard failures: " + ", ".join(failing), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
