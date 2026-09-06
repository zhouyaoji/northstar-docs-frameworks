#!/usr/bin/env python3
"""Check local links in the generated static site."""

from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag in {"a", "link"} and attributes.get("href"):
            self.links.append(attributes["href"] or "")
        if tag in {"img", "script", "source"} and attributes.get("src"):
            self.links.append(attributes["src"] or "")


def link_target(page: Path, href: str) -> Path | None:
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc or href.startswith(("mailto:", "tel:", "data:")):
        return None
    path_text = unquote(parsed.path)
    if not path_text:
        return None
    if path_text.startswith("/"):
        # Published URLs include /northstar-docs-frameworks/ as the Pages base path.
        prefix = "/northstar-docs-frameworks/"
        if path_text.startswith(prefix):
            path_text = path_text[len(prefix) :]
        else:
            return None
        target = PUBLIC / path_text
    else:
        target = page.parent / path_text
    return target.resolve()


def exists_as_static_target(target: Path) -> bool:
    if target.is_file():
        return True
    if target.is_dir() and (target / "index.html").is_file():
        return True
    if target.suffix == "" and target.with_suffix(".html").is_file():
        return True
    return False


def main() -> int:
    if not PUBLIC.is_dir():
        print("public directory does not exist; build the sites first", file=sys.stderr)
        return 1

    errors: list[str] = []
    pages = sorted(PUBLIC.rglob("*.html"))
    for page in pages:
        page_text = page.read_text(encoding="utf-8", errors="replace")
        if "</body>" in page_text and "data-northstar-assistant" not in page_text:
            errors.append(
                f"{page.relative_to(PUBLIC)}: documentation assistant was not injected"
            )
        parser = LinkParser()
        parser.feed(page_text)
        for href in parser.links:
            target = link_target(page, href)
            if target is None:
                continue
            try:
                target.relative_to(PUBLIC.resolve())
            except ValueError:
                errors.append(f"{page.relative_to(PUBLIC)}: link escapes public/: {href}")
                continue
            if not exists_as_static_target(target):
                errors.append(f"{page.relative_to(PUBLIC)}: missing target: {href}")

    if errors:
        print("Generated-site link check failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(f"Checked local links and assets in {len(pages)} generated HTML pages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
