# Northstar AIPP foundation

Northstar compiles writer- and SME-approved documentation knowledge into an AI
Publication Protocol (AIPP) demonstration object. Human documentation remains
writer-controlled. AIPP adds reviewed provenance and optional AI-only facts; it
does not silently rewrite the documentation.

## Authoring model

- `sources.yaml` registers authoritative inputs.
- `entries/*.yaml` associates a human document with sources and approved
  AI-only statements.
- `sample-sources/` contains explicitly fictional internal material that makes
  the collection workflow demonstrable without external credentials.
- `tools/validate-aipp.py` checks sources, entries, citations, review state, and
  identifiers.
- `tools/generate-aipp.py` creates disposable artifacts under `public/aipp/`.

Only entries with `review.state: approved-for-demo` enter the compiled object.
The pipeline creates the same preview on a pull request and refreshes the
published AIPP files after the approved commit is merged to `main`.

## Source locations

Every source uses the same metadata for authority, ownership, topics, and
lifecycle. Only its `locator` and `retrieval` configuration differ. Local
demonstrations use `locator.kind: path`; production sources can use
`locator.kind: url`. A URL alone is not sufficient: the retrieval adapter, a
stable source identifier, and an optional credential environment-variable name
tell a future collector how to retrieve it. Credentials never belong here.

See `sample-sources/source-registry.example.yaml` for Confluence, Jira, and Word
document examples. A collector should preserve the retrieved revision,
timestamp, and content hash as review evidence.

## Commands

```bash
python tools/validate-aipp.py
python tools/generate-aipp.py
```

The first version intentionally performs no model calls and fetches no external
systems. Source collection skills and AIPP-aware assistant comparisons can be
added without changing the reviewed entry format.
