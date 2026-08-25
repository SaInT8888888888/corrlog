# ProofAgent outreach — draft for Shane's review

**To:** ProofAgent Harness maintainers (`ProofAgent-ai/proofagent-harness`)
**Channel:** GitHub issue on their repo (public, linkable, shows up in their history)
**Issue title:** [idea] When a run returns `review`/`block`, emit a signed "correction receipt"

---

## Body

Hi — I'm the author of corrlog, a small open-source spec + reference implementation for a
cryptographically signed "Agent Correction Record" (ACR): when an agent action is later
found to be wrong, the *detector* can emit a signed, hash-chained receipt recording the
failure, the reason, the trigger (`check_failed` / `human_flagged` / `supersede`), and the
fix.

Repo (MIT): https://github.com/SaInT8888888888/corrlog
— spec (`SPEC.md`), JSON Schema, and an independent verifier with frozen test vectors
(`verifier/`) that shares zero code with the SDK.

**Why I'm writing to you:** ProofAgent already does the hard part. Your harness runs
adversarial multi-turn scenarios, scores behaviour with the evidence behind every result,
and emits a **pass / review / block** verdict with CI exit codes. What that verdict produces
today is an *internal* report. If, on a `review` or `block`, the harness emitted one signed
ACR receipt — signed by the harness's own key — that verdict would become a tamper-evident,
independently-verifiable artifact the evaluated vendor can't silently reinterpret or
disappear.

This is a very small ask, not "adopt our standard": **could a `review`/`block` verdict
optionally emit one ACR-compatible receipt?** The `block`/`review` verdict is the
`check_failed` trigger; your key signs it; anyone can verify it with the standalone verifier
against your pinned key. I'll do the integration work (a tiny adapter, tested against your
output) if you're open to the experiment.

Two things that I hope signal this is security engineering, not an AI-governance manifesto:

1. While building the independent verifier we found that self-authenticating receipts allow
   **key substitution** — an attacker signs a record with their own key and embeds that key,
   and a naive verifier accepts it. The spec now separates *signature validity* from *signer
   trust* and supports pinned verifier keys. Documented in `SECURITY.md`:
   https://github.com/SaInT8888888888/corrlog/blob/master/SECURITY.md

2. The correction record is deliberately honest about scope: it proves integrity +
   attribution, not completeness (SPEC §2, §9), and it *evidences* — never certifies —
   compliance duties. I noticed your docs make the same distinction ("as what a transcript
   can prove — never as certification"), which is part of why this felt like a natural fit.

If a "your `block` verdict becomes a signed receipt" integration is interesting, I'd love to
sketch the adapter in a thread here. If not a fit right now, no worries — and I'd welcome a
steer on who *would* find it useful.

Thanks for building ProofAgent.

---

## Notes for Shane

- **Every ProofAgent fact above is verified this turn** against their live repo
  (`ProofAgent-ai/proofagent-harness`, 26★, Apache-2.0): "adversarial multi-turn scenarios
  in CI", pass/review/block exit codes (0/1/2), `--governance-profile`, EU AI Act + NIST AI
  RMF + ISO 42001 + SOC 2 + GDPR, `proof crosswalk`, and the "evidence, never certification"
  line.
- **The integration seam is real and specific:** their `block` verdict (exit 2) maps
  cleanly to our `check_failed` trigger. This is the keyed-detector idea made concrete.
- **Small ask**, not "require ACR" — "could a review/block emit one receipt, I'll do the
  integration."
- **Their own language echoed back** ("evidence, never certification") is the trust bridge —
  it shows we read their docs, not that we mass-messaged a shortlist.
- **Still held — not sent.** Two decisions from you before it goes:
  1. Send from your identity or a project identity? (written neutral, works either way)
  2. Confirm GitHub issue is the channel you want (vs. their contact/Discord if they list one).
- **Order stays ProofAgent → Inspect**, per ChatGPT — I won't draft Inspect until ProofAgent
  responds, so we can open with "we already integrated with an adversarial harness."
