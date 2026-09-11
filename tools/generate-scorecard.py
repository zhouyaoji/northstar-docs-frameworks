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
    return {
        "overall": weighted(evaluated),
        "categories": {category: weighted(items) for category, items in sorted(grouped.items())},
        "blockingFailures": [item["criterion"] for item in results if item["blocking"] and item["status"] == "fail"],
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Northstar documentation scorecard",
        "",
        f"Rubric version: `{report['rubricVersion']}`  ",
        f"Commit: `{report['commit']}`  ",
        f"Generated: `{report['generatedAt']}`",
        "",
        "> Scores represent repeatable conformance to declared automated criteria. Planned AI and human criteria are not scored.",
        "",
        "| Renderer | Automated score | Change from baseline | Blocking failures |",
        "| --- | ---: | ---: | ---: |",
    ]
    for renderer in report["renderers"]:
        delta = renderer["scores"].get("baselineDelta")
        delta_text = "N/A" if delta is None else f"{delta:+.1f}"
        lines.append(f"| {renderer['name']} | {renderer['scores']['overall']:.1f} | {delta_text} | {len(renderer['scores']['blockingFailures'])} |")
    lines.extend(["", "## Results by renderer", ""])
    for renderer in report["renderers"]:
        lines.extend([f"### {renderer['name']} - {renderer['scores']['overall']:.1f}", "", "| Status | Category | Criterion | Evidence |", "| --- | --- | --- | --- |"])
        for item in renderer["results"]:
            lines.append(f"| {item['status']} | {item['category']} | `{item['criterion']}` | {item['evidence'].replace('|', '\\|')} |")
        lines.append("")
    return "\n".join(lines)


def render_html(report: dict) -> str:
    cards = "".join(
        f'<article class="card"><h2>{html.escape(renderer["name"])}</h2><p class="score">{renderer["scores"]["overall"]:.1f}</p><p>Automated score · {renderer["scores"].get("baselineDelta", 0):+.1f} from baseline</p><a href="#{html.escape(renderer["name"])}">View evidence</a></article>'
        for renderer in report["renderers"]
    )
    sections = []
    for renderer in report["renderers"]:
        rows = "".join(
            f'<tr><td><span class="{item["status"]}">{html.escape(item["status"].replace("_", " "))}</span></td><td>{html.escape(item["category"])}</td><td><code>{html.escape(item["criterion"])}</code></td><td>{html.escape(item["evidence"])}</td></tr>'
            for item in renderer["results"]
        )
        sections.append(f'<section id="{html.escape(renderer["name"])}"><h2>{html.escape(renderer["name"])}: {renderer["scores"]["overall"]:.1f}</h2><div class="table"><table><thead><tr><th>Status</th><th>Category</th><th>Criterion</th><th>Evidence</th></tr></thead><tbody>{rows}</tbody></table></div></section>')
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Repeatable documentation quality evidence for the Northstar renderer comparison."><title>Northstar documentation scorecard</title><style>
:root{{font-family:system-ui,sans-serif;color-scheme:light dark}}body{{margin:0;background:#071525;color:#ecf5ff}}nav,main{{max-width:1100px;margin:auto;padding:1.2rem}}a{{color:#78d8ff}}h1{{font-size:clamp(2rem,6vw,4rem);margin:.4rem 0}}.lead{{max-width:800px;color:#b9cee3;font-size:1.1rem}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:1rem;margin:2rem 0}}.card{{background:#0c2034;border:1px solid #31506c;border-radius:14px;padding:1rem}}.card h2{{margin:0;font-size:1rem}}.score{{font-size:2.5rem;font-weight:750;margin:.6rem 0 0}}section{{margin:3rem 0}}.table{{overflow:auto}}table{{width:100%;border-collapse:collapse;background:#0c2034}}th,td{{text-align:left;vertical-align:top;padding:.7rem;border-bottom:1px solid #31506c}}.pass{{color:#77e69b}}.fail{{color:#ff9898}}.not_evaluated{{color:#b9cee3}}code{{white-space:nowrap}}
</style></head><body><nav><a href="../">← Docs Lab</a></nav><main><p>DOCUMENTATION QUALITY</p><h1>Northstar scorecard</h1><p class="lead">Consistent evidence of progress and regression under rubric version {html.escape(report['rubricVersion'])}. Automated, AI-assisted, and human evaluation remain distinct.</p><div class="grid">{cards}</div>{''.join(sections)}<p>Commit {html.escape(report['commit'])} · Generated {html.escape(report['generatedAt'])}. <a href="scorecard.json">JSON</a> · <a href="scorecard.md">Markdown</a></p></main></body></html>'''


def main() -> int:
    if not PUBLIC.is_dir():
        print("public directory does not exist; build the sites first", file=sys.stderr)
        return 1
    rubric = yaml.safe_load((EVALUATION / "rubric.yaml").read_text(encoding="utf-8"))
    benchmark_data = yaml.safe_load((EVALUATION / "benchmarks" / "retrieval.yaml").read_text(encoding="utf-8"))
    manifest = yaml.safe_load((ROOT / "content" / "manifest.yaml").read_text(encoding="utf-8"))
    criteria = rubric["criteria"]
    expected_titles = [page["title"] for page in manifest["pages"]]
    benchmarks = benchmark_data["benchmarks"]
    baseline = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.is_file() else {"renderers": {}}
    renderer_reports = []
    for renderer in RENDERERS:
        renderer_results = evaluate_renderer(renderer, criteria, expected_titles, benchmarks)
        renderer_scores = scores(renderer_results)
        baseline_score = baseline.get("renderers", {}).get(renderer)
        renderer_scores["baseline"] = baseline_score
        renderer_scores["baselineDelta"] = (
            round(renderer_scores["overall"] - baseline_score, 1) if baseline_score is not None else None
        )
        renderer_reports.append({"name": renderer, "scores": renderer_scores, "results": renderer_results})
    commit = os.environ.get("GITHUB_SHA")
    if not commit:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    report = {
        "schemaVersion": 1,
        "rubricVersion": str(rubric["rubricVersion"]),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "commit": commit,
        "baseline": str(BASELINE.relative_to(ROOT)) if BASELINE.is_file() else None,
        "scoringNote": "Only implemented automated criteria with positive weights contribute to scores.",
        "renderers": renderer_reports,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "scorecard.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown = render_markdown(report)
    (OUTPUT / "scorecard.md").write_text(markdown + "\n", encoding="utf-8")
    (OUTPUT / "index.html").write_text(render_html(report), encoding="utf-8")
    failing = [renderer["name"] for renderer in renderer_reports if renderer["scores"]["blockingFailures"]]
    print("Generated scorecards for " + ", ".join(RENDERERS) + ".")
    if failing:
        print("Blocking scorecard failures: " + ", ".join(failing), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
