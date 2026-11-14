# Manual Codex and Gemini pilot

This pilot collects answers from Codex and Gemini without API calls. It uses the existing blinded packets, response schema, deterministic importer, and human-review workflow. Subscription access may be used, but the pilot must not request, store, or commit API keys.

## What the pilot tests

The pilot asks the same two assistants to answer every benchmark case under both blinded source conditions. The source material is the only intentional difference. The pilot is exploratory: the initial suite is too small to support claims of statistical significance.

## Before starting

- Use a run generated from the same commit for both assistants.
- Record the exact model label shown by each product and the date of the session.
- Use a new chat or session for each assistant. Do not include prior Northstar or AIPP conversation history.
- Give each assistant only the generated `share/` directory. Do not provide `private/condition-map.json`, gold answers, judgments, or comparison results.
- Do not tell either assistant which source label represents AIPP.
- Do not use web search, outside knowledge, or a second assistant to repair an answer.

## 1. Generate the pilot run

Build the current sources and create a fresh run. Record the commit SHA, run ID, seed, suite version, and protocol version in your pilot notes.

```bash
./tools/build-sites.sh
python3 tools/generate-evaluation-packets.py \
  --run-id manual-pilot-001 \
  --seed 20261101 \
  --output evaluation/runs/manual-pilot-001
```

The generated `share/instructions.md` is the controlling instruction set. If it conflicts with this page, stop and resolve the conflict before collecting answers.

## 2. Collect Codex responses

Start a new Codex session and attach only `evaluation/runs/manual-pilot-001/share/`. Use this request:

> Follow `instructions.md` exactly. Answer every packet using only the source included in that packet. Do not use web search or outside knowledge. Return one complete JSON response file per packet, following its response template. Use the exact model label shown in this session and set the interface to `assistant-file-review`. Do not identify or guess what `source-a` or `source-b` represents.

Save the returned JSON files under:

```text
evaluation/runs/manual-pilot-001/responses/codex/
```

Do not edit the wording of an answer after seeing Gemini's answers or the private condition map. Mechanical repairs to invalid JSON are allowed only if they do not change the answer or citations; record every repair in the pilot notes.

## 3. Collect Gemini responses

Start a new Gemini session and repeat the same procedure with the same `share/` directory and prompt. Save its files under:

```text
evaluation/runs/manual-pilot-001/responses/gemini/
```

Do not show Gemini the Codex responses, and do not show Codex the Gemini responses.

## 4. Check completeness before unblinding

Confirm that each assistant returned one response for every packet and that each response preserves the packet's `runId`, `suiteVersion`, `caseId`, and `blindedCondition`. The `responseId` must be unique, and the generator metadata must identify the actual provider, displayed model label, and `assistant-file-review` interface.

Do not open either private mapping while answers are still missing. Missing or invalid answers must remain visible; do not silently replace or discard them.

## 5. Import and run deterministic checks

```bash
python3 tools/import-evaluation-responses.py \
  --run evaluation/runs/manual-pilot-001
```

Review `results/import-report.json`. Resolve only file-format or metadata problems that can be corrected without changing answer content. Deterministic checks verify structure, packet identity, completeness, and citation identifiers; they do not judge natural-language accuracy or usefulness.

## 6. Prepare human review

Use a new seed and give reviewers only the generated `human-review/share/` directory:

```bash
python3 tools/prepare-human-review.py \
  --run evaluation/runs/manual-pilot-001 \
  --seed 20261102
```

Reviewers must not be told the answer generator or source condition. They score response completeness and helpfulness against the common verified requirements, then score source handling against the information available in the supplied source. These groups remain separate in the reports. A person who helped produce or repair an answer must not be that answer's only reviewer. Store completed judgment files in `human-review/judgments/`.

## 7. Generate reports

```bash
python3 tools/generate-evaluation-comparison.py \
  --run evaluation/runs/manual-pilot-001
```

Read the Markdown report for discussion and retain the JSON report for automation or later analysis. Keep deterministic and human results distinct. Report missing reviews, disagreements, individual cases, paired differences, and limitations instead of publishing only an overall average.

## Pilot completion checklist

- [ ] Both assistants received the same blinded `share/` directory.
- [ ] Fresh sessions were used, with no private mapping or prior AIPP context.
- [ ] Exact provider and displayed model labels were recorded.
- [ ] Every expected response is present, or its absence is recorded.
- [ ] Any mechanical JSON repairs are documented.
- [ ] The deterministic import completed and its report was retained.
- [ ] Human-review packets were generated with a different seed.
- [ ] Reviewers remained blinded to generator and source condition.
- [ ] JSON and Markdown comparison reports were generated.
- [ ] Conclusions disclose the small suite, missing data, disagreement, and recognizable source-format limitations.

## What not to commit

Generated runs are ignored by Git. Do not commit private condition maps, private review maps, incomplete responses, personal reviewer information, API keys, access tokens, or hidden chain-of-thought. Publish a sanitized result set only after deciding which artifacts can be shared without breaking the evaluation or disclosing private data.
