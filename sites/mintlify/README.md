# Mintlify adapter

- Source format: generated MDX from canonical Markdown
- Renderer: Mintlify headless integration for Astro
- Public URL: `/northstar-docs-frameworks/mintlify/`
- Status: deployable through the shared GitHub Pages pipeline

`tools/prepare-mintlify.py` creates disposable MDX beneath `docs/` before the
build. Mintlify processes the content into Astro's content collection, and the
static Astro output is assembled beneath `public/mintlify/`. The shared
post-build steps then generate `llms.txt` and `llms-full.txt` and inject the
same local-search assistant used by every other renderer.

This headless build intentionally uses the repository's assistant rather than
Mintlify's hosted assistant so the comparison uses the same retrieval behavior
and corpus across all renderers.

## Dependency note

As of September 2026, `@mintlify/astro` 1.0 requires Astro 5. npm reports
remaining advisories in that supported dependency line, including advisories
fixed only in later Astro major versions. This project renders trusted,
repository-controlled content to static HTML and does not run an Astro server
in production. Mermaid and Sharp are overridden to patched compatible releases;
the remaining advisories should be revisited when Mintlify supports a patched
Astro major version rather than bypassing its declared peer requirements.
