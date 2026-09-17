#!/usr/bin/env python3
"""Compile approved Northstar documentation and sidecars into AIPP artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
AIPP = ROOT / "aipp"
OUTPUT = ROOT / "public" / "aipp"
SITE_URL = os.environ.get("NORTHSTAR_SITE_URL", "https://zhouyaoji.github.io/northstar-docs-frameworks").rstrip("/")


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def revision() -> str:
    return os.environ.get("GITHUB_SHA") or subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def main() -> None:
    manifest = load_yaml(ROOT / "content" / "manifest.yaml")
    registry = load_yaml(AIPP / "sources.yaml")
    sources = {source["id"]: source for source in registry["sources"]}
    entries = {
        entry["documentId"]: entry
        for path in sorted((AIPP / "entries").glob("*.yaml"))
        if (entry := load_yaml(path)).get("review", {}).get("state") == "approved-for-demo"
    }
    sections, statements = [], []
    used_sources: set[str] = set()
    for page in manifest["pages"]:
        page_id = page["id"]
        entry = entries[page_id]
        markdown_path = ROOT / "content" / page["sources"]["markdown"]
        markdown = markdown_path.read_text(encoding="utf-8")
        human_id = "doc-" + page_id.replace("/", "-")
        section_ids = [human_id]
        statements.append({
            "statement_id": human_id,
            "kind": "human_document",
            "text": markdown,
            "human_render": True,
            "source_ids": entry["sourceIds"],
            "source_path": str(markdown_path.relative_to(ROOT)),
        })
        used_sources.update(entry["sourceIds"])
        for statement in entry.get("aiOnlyStatements", []):
            compiled = dict(statement)
            compiled["statement_id"] = compiled.pop("id")
            compiled["source_ids"] = compiled.pop("sourceIds")
            compiled["human_render"] = False
            statements.append(compiled)
            section_ids.append(compiled["statement_id"])
            used_sources.update(compiled["source_ids"])
        sections.append({"section_id": page_id, "title": page["title"], "statement_ids": section_ids})

    commit = revision()
    generated_at = datetime.now(timezone.utc).isoformat()
    citations = []
    source_report = []
    for source_id in sorted(used_sources):
        source = sources[source_id]
        locator = source["locator"]
        record = {
            "source_id": source_id,
            "name": source["name"],
            "source_type": source["sourceType"],
            "format": source["format"],
            "authority": source["authority"],
            "owner": source["owner"],
            "topics": source["topics"],
            "lifecycle": source["lifecycle"],
            "locator": locator,
            "retrieval": source["retrieval"],
        }
        if locator["kind"] == "path":
            path = ROOT / locator["value"]
            if path.is_file():
                record["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            else:
                record["revision"] = commit
        citations.append(record)
        source_report.append(record)

    obj = {
        "schema_version": 1,
        "object_id": "urn:org:northstar-demo:product:northstar-platform",
        "version": commit,
        "type": "product.knowledge",
        "title": "Northstar Platform knowledge source",
        "publisher": {"publisher_id": "urn:org:northstar-demo", "name": "Northstar documentation framework comparison"},
        "approval": {"state_at_publication": "approved-for-demo", "note": "Fictional demonstration content"},
        "provenance": {"generated_at": generated_at, "git_commit": commit},
        "content": {"sections": sections, "statements": statements, "citations": citations},
        "renderings": {"documentation_lab": f"{SITE_URL}/", "llms": f"{SITE_URL}/llms.txt"},
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    object_name = "northstar-platform.json"
    (OUTPUT / object_name).write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
    (OUTPUT / "source-report.json").write_text(json.dumps({"generated_at": generated_at, "sources": source_report}, indent=2) + "\n", encoding="utf-8")
    discovery = {"schema_version": 1, "objects": [{"object_id": obj["object_id"], "url": f"{SITE_URL}/aipp/{object_name}", "state": "approved-for-demo"}]}
    feed = {"schema_version": 1, "events": [{"event": "published", "object_id": obj["object_id"], "version": commit, "url": f"{SITE_URL}/aipp/{object_name}"}]}
    (OUTPUT / "discovery.json").write_text(json.dumps(discovery, indent=2) + "\n", encoding="utf-8")
    (OUTPUT / "feed.json").write_text(json.dumps(feed, indent=2) + "\n", encoding="utf-8")
    print(f"Compiled {len(statements)} AIPP statements from {len(sections)} documents.")


if __name__ == "__main__":
    main()
