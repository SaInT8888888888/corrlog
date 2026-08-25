# Inspect (UK AISI) outreach — draft for Shane's review

**To:** UK AISI Inspect maintainers (`UKGovernmentBEIS/inspect_ai`, MIT, 2.6k★)
**Channel:** GitHub issue (their extension ecosystem is public and example-driven)
**Issue title:** [idea] A `Hooks` subclass that emits a signed correction receipt on a failing score

**Status:** DRAFT — hold. Do NOT send until ProofAgent responds (per ChatGPT's sequencing:
fire with the social-proof line on a ProofAgent *yes*, or the standalone version on a
ProofAgent *stall* — not on a mere reply).

---

## Body

Hi — I maintain corrlog, an open (MIT) spec for Agent Correction Records: Ed25519-signed,
tamper-evident receipts of a detected agent failure, verifiable offline against a pinned key.

[**if ProofAgent yes:** The ProofAgent harness is adding these to its review/block verdicts,
and Inspect feels like the natural second home.]

[**if standalone:** Inspect's transcript-level auditability is exactly the ethos the format
was built for.]

The ask is deliberately small: a `Hooks` subclass — on `on_sample_end`, if
`data.sample.scores` contains an `INCORRECT` value, optionally emit one ACR-compatible
receipt signed by the eval run's key. No core changes; it ships as an extension package
(like the existing `wandb_weave.py` / `mlflow_tracking.py` hook examples). An `INCORRECT`
score maps to our `check_failed` trigger. I'll do the integration.

While building an independent verifier we found that self-authenticating receipts allowed
key substitution — an attacker signs a record with their own key and embeds that key, and a
naive verifier accepts it. The spec now separates *signature validity* from *signer trust*
via key pinning. Documented in `SECURITY.md`:
https://github.com/SaInT8888888888/corrlog/blob/master/SECURITY.md

Would a hook like this be something you'd consider?

---

## Notes for Shane

- **Every Inspect fact verified this turn** against their live docs, not the external
  review's characterization:
  - Hooks: `from inspect_ai.hooks import Hooks, hooks`, subclass `Hooks`, override
    `on_sample_end(self, data: SampleEnd)` — and their own W&B example reads
    `data.sample.scores` and extracts `v.value`. (extensions-hooks.html.md)
  - Scorers: `from inspect_ai.scorer import CORRECT, INCORRECT, Score`; a scorer yields
    `Score(value=INCORRECT)`. (custom-scorers.html.md)
  - Extensions are real: "Extensions to Inspect … can be provided by other Python packages."
    (README), and there's a documented extensions-hooks page.
- **The seam is exact:** `on_sample_end` → check for `INCORRECT` → emit ACR receipt signed
  by the run key. This is the keyed-detector idea, and it's a *hook*, not a core change.
- **Repo is MIT (not Apache** as Claude said) — 2,627 stars, pushed 2026-08-25.
- **Bracketed opener** — two variants, swap in at send time based on ProofAgent's answer.
- **Still held.** Same two sending decisions as ProofAgent (identity + channel) apply.

## Verified shortlist status (all checked against live sources this turn)

| Target | Repo | Verified | Fit |
|---|---|---|---|
| ProofAgent | `ProofAgent-ai/proofagent-harness` (26★, Apache-2.0, Dr. Fouad Bousetouane, ProofAI LLC) | ✅ pass/review/block exit 0/1/2, EU AI Act + NIST + ISO + SOC 2 + GDPR, "evidence never certification" | Best — detector + verdict + gate |
| Inspect | `UKGovernmentBEIS/inspect_ai` (2,627★, MIT) | ✅ Hooks lifecycle + Score CORRECT/INCORRECT + extension packages | Strong — transcript-level auditability |
| DeepEval / promptfoo | — | ⏳ not yet checked | Good — pass/fail CI assertions |
| Harness / SAP / observability | — | ⏳ not yet checked | Later adopters |
