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
mkdocs build --strict --config-file "$repo_root/sites/mkdocs/mkdocs.yml" --site-dir "$public_dir/mkdocs"
sphinx-build -W --keep-going -b html -c "$repo_root/sites/sphinx-rest" "$repo_root/content/restructuredtext" "$public_dir/sphinx-rest"
sphinx-build -W --keep-going -b html "$repo_root/sites/sphinx-myst" "$public_dir/sphinx-myst"

touch "$public_dir/.nojekyll"
