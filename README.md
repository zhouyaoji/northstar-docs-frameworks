# Northstar documentation framework comparison

This repository will render the same fictional Northstar Platform documentation
with several markup languages and documentation generators. It is designed as a
small, inspectable comparison rather than as a production product site.

## Planned renderers

| Site | Primary source format | Status |
| --- | --- | --- |
| Docusaurus | Markdown | Deployable |
| Redocly | Markdown or Markdoc | Scaffolded |
| MkDocs | Markdown | Deployable |
| Sphinx | reStructuredText | Deployable |
| Sphinx with MyST | MyST Markdown | Deployable |
| Mintlify | MDX | Scaffolded |
| Antora | AsciiDoc | Scaffolded |

The initial human-maintained source is in `content/markdown`. Stable page IDs
are listed in `content/manifest.yaml`. Other format directories are reserved for
generated or deliberately converted variants.

## Repository layout

```text
content/       Shared content, organized by markup format
sites/         Configuration and theme adapters for each generator
tools/         Future conversion and parity tooling
aipp/          Reserved for a future AI Publication Protocol source
assistant/     Reserved for a future framework-neutral docs assistant
```

## Publishing plan

The Pages workflow builds each static site independently, copies the results
beneath a common output directory, and deploys that single artifact to GitHub
Pages. A landing page links to each renderer.

The AIPP source and assistant are intentionally deferred. Their reserved
directories document the intended boundaries so they can be added without a
later repository reorganization.

## License

The demonstration content and code are available under the MIT License.
