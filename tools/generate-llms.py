#!/usr/bin/env python3
"""Generate framework-neutral llms.txt exports for every rendered site."""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
PUBLIC = ROOT / "public"
MANIFEST = CONTENT / "manifest.yaml"
DEFAULT_SITE_URL = "https://zhouyaoji.github.io/northstar-docs-frameworks"
SITE_URL = os.environ.get("NORTHSTAR_SITE_URL", DEFAULT_SITE_URL).rstrip("/")

RENDERERS = {
    "docusaurus": {
        "name": "Docusaurus",
        "page_url": lambda page_id: "" if page_id == "overview" else f"{page_id}/",
    },
    "mkdocs": {
        "name": "MkDocs",
        "page_url": lambda page_id: f"{page_id}/",
    },
    "sphinx-rest": {
        "name": "Sphinx reStructuredText",
        "page_url": lambda page_id: f"{page_id}.html",
    },
    "sphinx-myst": {
        "name": "Sphinx MyST",
        "page_url": lambda page_id: f"content/{page_id}.html",
    },
    "antora": {
        "name": "Antora AsciiDoc",
        "page_url": lambda page_id: (
            "northstar/" if page_id == "overview" else f"northstar/{page_id}.html"
        ),
    },
}


def without_frontmatter(markdown: str) -> str:
    if markdown.startswith("---\n"):
        _, _, remainder = markdown.partition("\n---\n")
        return remainder.lstrip()
    return markdown


def description(markdown: str) -> str:
    body = without_frontmatter(markdown)
    paragraphs = re.split(r"\n\s*\n", body)
    for paragraph in paragraphs:
        if paragraph.startswith(("#", "```", "- ")):
            continue
        text = re.sub(r"\[([^]]+)]\([^)]+\)", r"\1", paragraph)
        text = re.sub(r"[*_`]", "", text)
        return " ".join(text.split())
    return ""


def renderer_index(renderer: str, name: str, pages: list[dict[str, str]]) -> str:
    base = f"{SITE_URL}/{renderer}"
    lines = [
        f"# Northstar Platform — {name}",
        "",
        "> Fictional platform documentation rendered as part of the Northstar documentation framework comparison.",
        "",
        "## Documentation",
        "",
    ]
    page_url = RENDERERS[renderer]["page_url"]
    for page in pages:
        relative_url = page_url(page["id"])
        url = f"{base}/{relative_url}"
        lines.append(f'- [{page["title"]}]({url}): {page["description"]}')
    lines.extend(
        [
            "",
            "## Optional",
            "",
            f"- [Complete documentation context]({base}/llms-full.txt): All Northstar pages in one Markdown file.",
            f"- [Renderer comparison]({SITE_URL}/): Return to the documentation renderer lab.",
            "",
        ]
    )
    return "\n".join(lines)


def combined_context(pages: list[dict[str, str]]) -> str:
    sections = [
        "# Northstar Platform documentation",
        "",
        "> Complete canonical Markdown context for the fictional Northstar Platform documentation.",
    ]
    for page in pages:
        sections.extend(["", "---", "", page["markdown"].rstrip()])
    sections.append("")
    return "\n".join(sections)


def write_renderer_files(pages: list[dict[str, str]]) -> None:
    full_context = combined_context(pages)
    for renderer, config in RENDERERS.items():
        output = PUBLIC / renderer
        output.mkdir(parents=True, exist_ok=True)
        (output / "llms.txt").write_text(
            renderer_index(renderer, config["name"], pages), encoding="utf-8"
        )
        (output / "llms-full.txt").write_text(full_context, encoding="utf-8")

    redocly = PUBLIC / "redocly"
    redocly.mkdir(parents=True, exist_ok=True)
    redocly_index = "\n".join(
        [
            "# Northstar Platform — Redocly API reference",
            "",
            "> Interactive reference for the fictional Northstar OpenAPI description.",
            "",
            "## API reference",
            "",
            f"- [Northstar API reference]({SITE_URL}/redocly/): Browse the rendered OpenAPI reference.",
            f"- [OpenAPI source]({SITE_URL}/redocly/openapi.yaml): Read the OpenAPI 3.1 source.",
            "",
        ]
    )
    (redocly / "llms.txt").write_text(redocly_index, encoding="utf-8")
    (redocly / "llms-full.txt").write_text(full_context, encoding="utf-8")
    (redocly / "openapi.yaml").write_text(
        (ROOT / "sites/redocly/openapi.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )


def write_root_files() -> None:
    lines = [
        "# Northstar documentation renderer lab",
        "",
        "> The same fictional product documentation rendered with multiple documentation frameworks and markup formats.",
        "",
        "## Documentation renderers",
        "",
    ]
    for renderer, config in RENDERERS.items():
        lines.append(
            f'- [{config["name"]}]({SITE_URL}/{renderer}/llms.txt): AI-readable index for this rendering.'
        )
    lines.append(
        f"- [Redocly API reference]({SITE_URL}/redocly/llms.txt): AI-readable OpenAPI reference index."
    )
    lines.extend(
        [
            "",
            "## Optional",
            "",
            f"- [Complete canonical context]({SITE_URL}/llms-full.txt): All Northstar pages in one Markdown file.",
            "",
        ]
    )
    (PUBLIC / "llms.txt").write_text("\n".join(lines), encoding="utf-8")


def validate_local_links() -> None:
    errors = []
    for llms_file in PUBLIC.rglob("llms*.txt"):
        text = llms_file.read_text(encoding="utf-8")
        for url in re.findall(r"\[[^]]+]\(([^)]+)\)", text):
            if not url.startswith(f"{SITE_URL}/"):
                continue
            relative = unquote(urlsplit(url).path).removeprefix(
                urlsplit(SITE_URL).path.rstrip("/") + "/"
            )
            target = PUBLIC / relative
            if target.is_file() or (target.is_dir() and (target / "index.html").is_file()):
                continue
            if target.suffix == "" and target.with_suffix(".html").is_file():
                continue
            errors.append(f"{llms_file.relative_to(PUBLIC)}: missing target for {url}")

    if errors:
        raise SystemExit("Invalid llms.txt links:\n  - " + "\n  - ".join(errors))


def main() -> None:
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    pages = []
    for entry in manifest["pages"]:
        markdown = without_frontmatter(
            (CONTENT / entry["sources"]["markdown"]).read_text(encoding="utf-8")
        )
        pages.append(
            {
                "id": entry["id"],
                "title": entry["title"],
                "description": description(markdown),
                "markdown": markdown,
            }
        )

    write_renderer_files(pages)
    write_root_files()
    (PUBLIC / "llms-full.txt").write_text(combined_context(pages), encoding="utf-8")
    validate_local_links()
    print(f"Generated llms.txt and llms-full.txt exports for {len(RENDERERS) + 1} renderers.")


if __name__ == "__main__":
    main()
