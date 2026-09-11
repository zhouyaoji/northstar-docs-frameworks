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

The score is the weighted percentage of implemented automated criteria that pass. Compare category results and individual evidence before using the overall number. Changes to weights or criteria require a `rubricVersion` change so historical results remain interpretable.

`evaluation/baselines/v1.json` records the initial renderer scores. Reports show the change from that baseline. Promote a later result deliberately by adding a new versioned baseline and documenting the associated rubric version; do not silently overwrite history.

## Future AIPP comparison

AIPP will use the same benchmark questions and answer rubric as the human-documentation baseline. A future comparison can evaluate conventional docs, `llms.txt`, and AIPP separately for retrieval, grounded answers, citations, edge cases, and appropriate abstention. Each result will identify its evidence source. This isolates whether AIPP adds useful knowledge rather than merely changing the model or scoring rules.
