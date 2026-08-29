# Northstar documentation framework comparison

This repository will render the same fictional Northstar Platform documentation
with several markup languages and documentation generators. It is designed as a
small, inspectable comparison rather than as a production product site.

## Documentation renderers

| Site | Primary source format | Status |
| --- | --- | --- |
| Docusaurus | Markdown | Deployable |
| Redocly | OpenAPI 3.1 YAML | Deployable |
| MkDocs | Markdown | Deployable |
| Sphinx | reStructuredText | Deployable |
| Sphinx with MyST | MyST Markdown | Deployable |
| Mintlify | MDX | Scaffolded |
| Antora | AsciiDoc | Deployable |

The human-maintained source variants live beneath `content/`. Stable page IDs,
titles, and equivalent source files are declared in `content/manifest.yaml`.
The manifest gives automation a framework-neutral way to confirm that every
documented page exists in Markdown, reStructuredText, and AsciiDoc.

## Repository layout

```text
content/       Shared content, organized by markup format
sites/         Configuration and theme adapters for each generator
tools/         Build, content-validation, and generated-link tooling
aipp/          Reserved for a future AI Publication Protocol source
assistant/     Reserved for a future framework-neutral docs assistant
```

## CI/CD automation

GitHub Actions is both the continuous integration (CI) and continuous delivery
(CD) service for this project. The complete pipeline is defined in
`.github/workflows/pages.yml`; no separate Jenkins server or other CI service is
required.

The workflow starts in three ways:

- Every pull request runs CI and produces a downloadable preview artifact.
- Every push to `main` runs CI and, if every check passes, deploys GitHub Pages.
- `workflow_dispatch` permits an authorized maintainer to run the pipeline
  manually from the Actions page.

### Pipeline sequence

The build job runs these stages in order:

1. **Check out the commit.** The runner receives the exact repository revision
   being tested.
2. **Prepare and cache runtimes.** Node.js 22 and Python 3.12 are configured.
   npm caches are keyed from the three lockfiles, and pip caching is derived
   from `requirements.txt`. A cache can make dependency installation faster,
   but a cache miss does not change the result of the build.
3. **Install pinned dependencies.** `npm ci` installs the Antora, Docusaurus,
   and Redocly lockfiles exactly. pip installs the versions pinned in
   `requirements.txt`.
4. **Validate the content model.** `tools/validate-content.py` reads
   `content/manifest.yaml` and rejects duplicate page IDs, missing files,
   unexpected source formats, paths outside `content/`, or titles that differ
   between the manifest and a source document. Every listed page must have a
   Markdown, reStructuredText, and AsciiDoc representation.
5. **Build every renderer.** `tools/build-sites.sh` creates a fresh `public/`
   directory, adds the landing page, and builds Docusaurus, Redocly, Antora,
   MkDocs, Sphinx reStructuredText, and Sphinx MyST. Redocly lints the OpenAPI
   description before rendering. MkDocs uses strict mode, and both Sphinx builds
   treat warnings as errors.
6. **Check the assembled site.** `tools/check-built-links.py` parses every
   generated HTML file and verifies that local links, scripts, stylesheets, and
   images resolve inside `public/`. External URLs are not requested during this
   check, so the result is deterministic and does not depend on another site
   being available.
7. **Publish an artifact.** Pull requests retain `public/` as a downloadable
   `rendered-documentation` artifact for seven days. This lets a reviewer inspect
   the exact output without deploying it publicly.
8. **Deploy after merge.** For pushes to `main`, the build job uploads a GitHub
   Pages artifact. A separate deployment job runs only after the build succeeds
   and publishes that artifact to the `github-pages` environment.

The dependency between the build and deployment jobs is the release gate: a
manifest problem, invalid OpenAPI file, renderer warning, build error, or broken
local link stops deployment. Pull requests never deploy the public site.

### Public output paths

The single Pages artifact contains a landing page and one directory per static
renderer:

```text
public/
├── index.html
├── antora/
├── docusaurus/
├── mkdocs/
├── redocly/
├── sphinx-myst/
└── sphinx-rest/
```

This layout gives each experiment a stable public path beneath
`https://zhouyaoji.github.io/northstar-docs-frameworks/` while keeping one
deployment and one Pages project.

### Run the pipeline locally

Use the same commands as CI from the repository root:

```bash
npm ci --prefix sites/antora
npm ci --prefix sites/docusaurus
npm ci --prefix sites/redocly
python -m pip install --requirement requirements.txt
python tools/validate-content.py
./tools/build-sites.sh
python tools/check-built-links.py
```

Open `public/index.html` after the commands finish to inspect the assembled
site. Generated output is disposable: the next build replaces `public/` and the
temporary Markdown copies used by MkDocs and Sphinx MyST.

### Adding or changing content

When a page is added, update `content/manifest.yaml` with its stable ID, title,
and source path for all three maintained formats. CI then verifies coverage and
title parity before any renderer starts. A change to existing content needs no
manual deployment action: opening a pull request renders and validates it, and
merging the passing pull request causes the `main` deployment.

The AIPP source and assistant are intentionally deferred. Their reserved
directories document the intended boundaries so they can be added without a
later repository reorganization.

## License

The demonstration content and code are available under the MIT License.
