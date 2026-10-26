# Northstar documentation scorecard

The scorecard applies a versioned rubric to every published renderer. It is designed to show progress and regression under declared rules, not to claim that documentation quality is objectively reducible to one number.

## Evidence types

- **Automated** checks are deterministic and contribute to the current score.
- **AI-assisted** checks must record the model, prompt, rubric version, and evidence. They are planned and do not affect the current score.
- **Human** checks must record the reviewing role and decision. They are planned and do not affect the current score.

An unevaluated criterion is reported as `not_evaluated`; it is never silently treated as a pass or failure.

## Run locally

Build the sites first, then generate the report:

```bash
./tools/build-sites.sh
python tools/generate-scorecard.py
```

The command writes `public/scorecard/index.html`, `scorecard.json`, and `scorecard.md`. GitHub Actions publishes the HTML report with the Docs Lab and uploads the machine-readable files in the rendered-documentation artifact.

## Interpreting the score

Rubric 1.2 separates one shared **Content quality** score from implementation-specific **Renderer implementation**, **AI readiness**, and **Publication operations** scores. AIPP appears as a knowledge layer, not as an eighth renderer. Criteria that do not apply remain `not_evaluated`, so compare coverage and individual evidence rather than treating the table as a universal ranking.

Failed implemented criteria produce recommendations with impact, effort, feasibility, capability provider, fix owner, and available score opportunity. The priority table is a default triage view; teams should still apply their own requirements and constraints.

`evaluation/baselines/v1.json` preserves the Rubric 1.0 renderer scores. Rubric 1.1 does not compare its newly separated groups with that incompatible baseline. Promote a later 1.1 result deliberately by adding a new versioned baseline and documenting the associated rubric version; do not silently overwrite history.

## AIPP comparison

AIPP uses the same deterministic retrieval questions as the renderer exports and adds checks for its structured object, source provenance, reviewed sidecars, conflict signaling, and discovery/feed artifacts. Renderer-specific criteria do not apply to AIPP, while AIPP-specific criteria do not apply to renderers. A future model-assisted phase can evaluate grounded answers, citations, edge cases, and appropriate abstention while recording the model, prompt, and evidence.

## Answer-quality evaluation contract

`protocol.md` defines the blinded, multi-model, and human-review procedure for comparing ordinary documentation with AIPP. The initial gold-standard suite is `benchmarks/answer-quality.yaml`. Its expectations are condition-specific, so a documentation-only assistant can receive credit for appropriate abstention when a fact exists only in AIPP.

The schemas in `schemas/` define benchmark suites, model responses, and deterministic, model, or human judgments. Codex, Gemini, API adapters, and local models should all return response files that conform to `schemas/response.schema.json`. The provider-neutral example in `examples/response.example.json` can be copied as a template. Fields for token usage and latency are optional because file-reading assistants do not always expose them.

Validate the contract and example response without calling any model:

```bash
python tools/validate-evaluation.py
```

The evaluation tools are local and deterministic. They do not call model APIs. Human review and optional model judging remain separate later phases.

## Generate blinded packets

Build the documentation sites first so the published `llms-full.txt` and compiled AIPP object are current. Then generate a run with an explicit ID and randomization seed:

```bash
./tools/build-sites.sh
python tools/generate-evaluation-packets.py \
  --run-id pilot-001 \
  --seed 20261012 \
  --output evaluation/runs/pilot-001
```

The generator creates two deliberately separated areas:

- `share/` contains randomized `source-a` and `source-b` packets, a manifest, response templates, and instructions. Give only this directory to Codex, Gemini, or another answer generator.
- `private/condition-map.json` records which label represents documentation or AIPP, the seed, source paths, and checksums. Keep it away from answer generators and blinded evaluators until judging is complete.

Every packet is validated against `schemas/packet.schema.json`; its embedded response template is validated against `schemas/response.schema.json`. The generated run directory is ignored by Git so incomplete responses and the private condition map are not committed accidentally. The response importer preserves completed response JSON files as evaluation artifacts.

## Import and check responses

Place completed JSON responses in the run's `responses/` directory. Files can be nested by provider or model. Import them only after every answer generator has received the blinded `share/` directory:

```bash
python tools/import-evaluation-responses.py \
  --run evaluation/runs/pilot-001
```

The importer writes a new `results/` directory containing:

- byte-for-byte copies of valid responses, named by response ID;
- one deterministic judgment per imported response;
- `import-report.json`, with generator-level completeness, missing packets, invalid files, checksums, and deterministic decisions.

The import fails for malformed JSON, schema violations, mismatched run metadata, unknown packets, duplicate response IDs, or duplicate answers from the same generator. Missing responses are preserved in the report rather than silently discarded.

Deterministic judgments check only what software can establish reliably: response structure, packet identity, allowed citation IDs, and required citation IDs. They deliberately mark accuracy, completeness, edge-case handling, conflict handling, and uncertainty as `not_applicable`. A deterministic pass is therefore not a claim that the answer text is correct; those dimensions remain for blinded model and human review.

For reproducible imports, supply an explicit timestamp:

```bash
python tools/import-evaluation-responses.py \
  --run evaluation/runs/pilot-001 \
  --evaluated-at 2026-10-19T00:00:00Z
```

The CI smoke test generates synthetic responses locally and verifies complete imports plus deterministic failure for a citation that was not present in its packet. It does not contact Codex, Gemini, or any paid service.

## Conduct blinded human review

After importing responses, create randomized review packets with a different seed from the answer-packet run:

```bash
python tools/prepare-human-review.py \
  --run evaluation/runs/pilot-001 \
  --seed 20261026
```

Give reviewers only `human-review/share/`. Each packet includes the question, answer, supplied source, condition-specific gold requirements, scoring anchors, and a judgment template. It excludes the answer generator, source-condition name, and original response ID. Keep `human-review/private/review-map.json` private until every review is returned.

Reviewers save completed judgment JSON files in `human-review/judgments/`. They identify themselves by role, such as `documentation-reviewer`, rather than by personal name. More than one reviewer can evaluate the same blinded response as long as their role identifiers differ.

## Generate the comparison report

After collecting human judgments, unblind and aggregate the results:

```bash
python tools/generate-evaluation-comparison.py \
  --run evaluation/runs/pilot-001
```

The command writes machine-readable JSON and a Markdown report to `comparison/`. The report includes:

- review coverage and missing human judgments;
- separate deterministic and human aggregates by generator, source condition, and case category;
- descriptive paired AIPP-versus-documentation differences for each generator and case;
- individual results and reviewer disagreement;
- explicit limitations, including the small initial suite and potentially recognizable source formats.

The report never claims statistical significance. Averages exclude `not_applicable` dimensions, and deterministic scores remain separate from human scores. CI exercises the full workflow with synthetic responses and judgments but does not call any AI provider.
