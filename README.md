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

### Moving the pipeline to Jenkins or another CI/CD service

GitHub Actions is a CI/CD pipeline engine, not a substitute for one. Jenkins,
GitLab CI/CD, Azure Pipelines, CircleCI, Buildkite, and other corporate systems
can run the same Northstar pipeline because the repository keeps its important
operations in executable scripts rather than embedding them in GitHub-specific
actions.

The portable pipeline contract is:

```text
install dependencies
        ↓
python tools/validate-content.py
        ↓
./tools/build-sites.sh
        ↓
python tools/check-built-links.py
        ↓
retain public/ as an artifact
        ↓
approved main-branch build → deploy public/
```

To migrate, replace the orchestration in `.github/workflows/pages.yml`, but keep
the manifest, scripts, pinned dependencies, and `public/` artifact contract. A
Jenkins Declarative Pipeline could use this structure:

```groovy
pipeline {
  agent { label 'linux-node22-python312' }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Install dependencies') {
      steps {
        sh 'npm ci --prefix sites/antora'
        sh 'npm ci --prefix sites/docusaurus'
        sh 'npm ci --prefix sites/redocly'
        sh 'python -m pip install --requirement requirements.txt'
      }
    }

    stage('Validate content') {
      steps { sh 'python tools/validate-content.py' }
    }

    stage('Render documentation') {
      steps { sh './tools/build-sites.sh' }
    }

    stage('Verify rendered site') {
      steps { sh 'python tools/check-built-links.py' }
    }

    stage('Publish') {
      when { branch 'main' }
      steps {
        // This script belongs to the company deployment platform. It might
        // publish to an internal web server, S3, Artifactory, or Kubernetes.
        sh './company-ci/deploy-docs.sh public'
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'public/**/*', fingerprint: true,
        allowEmptyArchive: true
    }
  }
}
```

The example deployment command is intentionally not included in this
repository because it depends on the company's hosting platform. In a real
Jenkins installation, the agent image would provide Node.js 22 and Python 3.12,
or the pipeline would run inside a pinned container image containing those
runtimes.

The same stages map directly to other services:

| Pipeline concern | GitHub Actions | Jenkins | Other hosted CI systems |
| --- | --- | --- | --- |
| Definition | `.github/workflows/pages.yml` | `Jenkinsfile` | Service-specific YAML |
| Execution environment | GitHub-hosted runner | Managed agent or Kubernetes pod | Hosted or self-hosted runner |
| Dependency reuse | `setup-node` and `setup-python` caches | Jenkins cache, persistent volume, or artifact proxy | Service cache directives |
| Pull-request validation | `pull_request` trigger | Multibranch Pipeline | Merge-request or pull-request trigger |
| Build output | Actions artifact | `archiveArtifacts` or artifact repository | Service artifact feature |
| Deployment approval | GitHub environment | `input` gate or release job | Protected environment or manual gate |
| Credentials | GitHub secrets or OIDC | Jenkins Credentials Binding | Secret store or workload identity |
| Public deployment | GitHub Pages | Company deployment script | Pages, object storage, CDN, or Kubernetes |

A corporate implementation would commonly extend the demonstration with:

- ephemeral containerized agents rather than mutable long-lived build servers;
- an internal npm and Python package proxy for availability and dependency
  governance;
- software-composition analysis, license checks, secret scanning, and a software
  bill of materials;
- protected branches, required reviews, and separate development, staging, and
  production environments;
- short-lived workload identity or a credential manager rather than secrets in
  repository files or command-line arguments;
- artifact promotion, so production receives the exact previously tested
  `public/` artifact instead of rebuilding source;
- retention policies, audit logs, notifications, deployment rollback, and
  service-level monitoring;
- self-hosted agents when documentation sources, APIs, or deployment targets are
  available only on the corporate network.

This separation is the main portability feature: the repository defines how to
validate and render the documentation, while the selected CI/CD service decides
when and where those commands run, how artifacts are governed, and who may
approve deployment.

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
