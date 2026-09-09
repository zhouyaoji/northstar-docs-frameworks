#!/usr/bin/env python3
"""Generate Mintlify-compatible MDX from the canonical Markdown source."""

from pathlib import Path
import re
import shutil
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
MARKDOWN = CONTENT / "markdown"
DOCS = ROOT / "sites/mintlify/docs"
PUBLIC_BASE = "/northstar-docs-frameworks/mintlify"


def mintlify_links(text: str, source: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        path_text, anchor = match.group(1), match.group(2) or ""
        resolved = (source.parent / f"{path_text}.md").resolve()
        page_id = resolved.relative_to(MARKDOWN.resolve()).with_suffix("").as_posix()
        public_path = "" if page_id == "overview" else f"/{page_id}/"
        return f"({PUBLIC_BASE}{public_path}{anchor})"

    return re.sub(r"\(([^)]+)\.md(#[^)]+)?\)", replace, text)


def main() -> None:
    for child in DOCS.iterdir():
        if child.name == "docs.json":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    manifest = yaml.safe_load((CONTENT / "manifest.yaml").read_text(encoding="utf-8"))
    for page in manifest["pages"]:
        source = CONTENT / page["sources"]["markdown"]
        text = source.read_text(encoding="utf-8")
        text = mintlify_links(text, source)
        target_id = "index" if page["id"] == "overview" else page["id"]
        target = DOCS / f"{target_id}.mdx"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    print(f"Prepared {len(manifest['pages'])} Mintlify MDX pages.")


if __name__ == "__main__":
    main()
