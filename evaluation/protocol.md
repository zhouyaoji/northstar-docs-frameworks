# AIPP answer-quality evaluation protocol

Protocol version: **1.0.0**

This protocol compares answers grounded in published Northstar documentation with answers grounded in the compiled AIPP knowledge object. It tests whether AIPP changes answer quality; it does not assume that AIPP is better.

## Experimental unit

Each benchmark case is answered once per source condition by every participating generator model:

- `documentation`: published human-facing content or its generated `llms-full.txt` representation
- `aipp`: the compiled AIPP object, including reviewed AI-only statements and provenance

The prompt, question, sampling settings, and output constraints must remain the same across conditions. The source material is the only intentional difference.

## Gold-standard evidence

A gold record is a reviewable evidence contract, not a single mandatory wording. Each case declares:

- atomic claims that evidence can support;
- source IDs supporting each claim;
- claims the answer must not make;
- expected behavior for each source condition;
- an illustrative answer that is never shown to answer-generating models.

Condition-specific expectations prevent unfair scoring. If a fact exists only in AIPP, an assistant using ordinary documentation should receive credit for appropriate abstention instead of being penalized for not inventing the fact.

Gold records must be written before model answers are generated. Changes after answers exist require a new suite version and an explanation.

## Blinding and randomization

Packet generation will replace condition names with opaque labels such as `source-a` and `source-b`. Label assignment and presentation order must be randomized per run and stored separately from judge-facing files.

Model judges and human reviewers receive the question, answer, permitted evidence, and rubric, but not the condition name or generator identity. A person or model that writes an answer must not be its only evaluator.

## Evaluation layers

1. **Deterministic checks** test required claim IDs, citations, prohibited claims, and output structure where those checks are mechanically reliable.
2. **Model judgments** use at least two judge models when resources allow. Prefer judges from different providers and disclose their exact model identifiers and prompts.
3. **Human review** scores the same dimensions and records a role rather than personal data. Human results remain visible separately from automated and model-assisted results.

Scores use a 0–4 scale:

- `0`: unsupported, harmful, or wholly incorrect
- `1`: major errors or omissions
- `2`: partly correct but materially incomplete
- `3`: correct with minor omissions
- `4`: fully supported and useful

The dimensions are factual accuracy, completeness, source attribution, edge-case handling, conflict handling, and appropriate uncertainty. `not_applicable` dimensions are excluded rather than treated as zero.

## Multi-model comparison

Use the same source packets for every generator. Report results by generator, condition, case category, evaluator type, and individual case. Do not publish only a combined score.

For a small initial dataset, publish paired score differences and raw evaluator disagreement. Do not claim statistical significance. Repeated runs and confidence intervals belong in a later phase after the suite is large enough.

## Reproducibility record

Every run must record:

- suite and protocol versions;
- generator provider, model identifier, interface, and parameters;
- judge provider, model identifier, prompt version, and parameters;
- source artifact checksums;
- timestamp and run identifier;
- token usage and latency when the interface exposes them;
- human reviewer role, rubric version, and review date.

Never commit API keys, access tokens, personal reviewer information, or hidden chain-of-thought.

## Response format

Every generator returns one JSON object per case and blinded condition using `schemas/response.schema.json`. The same contract applies to API output and answers copied from a subscription-based file-reading assistant. Assistants return only their answer and citations; they do not receive gold claims, example answers, condition mappings, or completed judgments.
