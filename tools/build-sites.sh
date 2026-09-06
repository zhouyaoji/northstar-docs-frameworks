#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
public_dir="$repo_root/public"
mkdocs_content="$repo_root/sites/mkdocs/docs"
myst_content="$repo_root/sites/sphinx-myst/content"

rm -rf "$public_dir" "$mkdocs_content" "$myst_content"
mkdir -p "$public_dir" "$mkdocs_content" "$myst_content"

cp "$repo_root/sites/landing/index.html" "$public_dir/index.html"
cp -R "$repo_root/content/markdown/." "$mkdocs_content/"
cp "$repo_root/sites/mkdocs/index.md" "$mkdocs_content/index.md"
cp -R "$repo_root/content/markdown/." "$myst_content/"

npm run build --prefix "$repo_root/sites/docusaurus" -- --out-dir "$public_dir/docusaurus"
npm run lint --prefix "$repo_root/sites/redocly"
npm run build --prefix "$repo_root/sites/redocly"
npm run build --prefix "$repo_root/sites/antora"
mkdocs build --strict --config-file "$repo_root/sites/mkdocs/mkdocs.yml" --site-dir "$public_dir/mkdocs"
sphinx-build -W --keep-going -b html -c "$repo_root/sites/sphinx-rest" "$repo_root/content/restructuredtext" "$public_dir/sphinx-rest"
sphinx-build -W --keep-going -b html "$repo_root/sites/sphinx-myst" "$public_dir/sphinx-myst"
python3 "$repo_root/tools/generate-llms.py"
python3 "$repo_root/tools/install-assistant.py"

touch "$public_dir/.nojekyll"
