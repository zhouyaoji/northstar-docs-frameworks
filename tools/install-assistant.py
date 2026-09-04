#!/usr/bin/env python3
"""Copy and inject the shared assistant widget into rendered HTML."""

import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
ASSETS = PUBLIC / "assistant"
MARKER = "data-northstar-assistant"


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "assistant/widget.js", ASSETS / "widget.js")
    endpoint = os.environ.get("NORTHSTAR_ASSISTANT_API_URL", "")
    (ASSETS / "config.js").write_text(
        f"window.NORTHSTAR_ASSISTANT_API_URL = {json.dumps(endpoint)};\n",
        encoding="utf-8",
    )
    count = 0
    for html_file in PUBLIC.rglob("*.html"):
        text = html_file.read_text(encoding="utf-8")
        if MARKER in text or "</body>" not in text:
            continue
        relative = os.path.relpath(ASSETS, html_file.parent).replace(os.sep, "/")
        scripts = (
            f'<script src="{relative}/config.js" defer></script>\n'
            f'<script src="{relative}/widget.js" defer {MARKER}></script>\n'
        )
        html_file.write_text(text.replace("</body>", scripts + "</body>"), encoding="utf-8")
        count += 1
    print(f"Installed the documentation assistant on {count} HTML pages.")


if __name__ == "__main__":
    main()
