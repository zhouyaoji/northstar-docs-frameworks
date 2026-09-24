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
