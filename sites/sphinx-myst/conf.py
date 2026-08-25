project = "Northstar Platform Docs"
author = "Joe Catera"
copyright = "2026, Joe Catera"

extensions = ["myst_parser"]
source_suffix = {".md": "markdown"}
exclude_patterns = ["README.md"]
html_theme = "alabaster"
html_theme_options = {
    "extra_nav_links": {
        "All renderers": "https://zhouyaoji.github.io/northstar-docs-frameworks/"
    }
}
html_title = "Northstar · Sphinx MyST"
html_baseurl = "https://zhouyaoji.github.io/northstar-docs-frameworks/sphinx-myst/"
