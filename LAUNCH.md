# corrlog — LAUNCH POST (draft for Shane's review)

## HN title (the headline is the whole game)
**Show HN: corrlog — agents cryptographically sign their own mistakes**

## HN body

Every agent vendor sells the same story: "our agent is reliable." They hide mistakes.
But here's the thing an auditor knows that nobody's marketing admits: every production
agent makes mistakes, and a *mature* system is one that caught them — not one that has
none.

Receipts already prove what an agent did (AAR, Microsoft's toolkit). But there's no
standard for the other half: the correction. When an agent does X, and X turns out to be
wrong, there's no standard way to record *that the fix happened, who/what caught it, and
why* — as a signed, tamper-evident record.

corrlog is an **open proposal + reference implementation** for that: the Agent Correction
Record (ACR). It extends the AAR receipt spec rather than competing with it:

- **A correction record** with a `supersedes` hash-pointer to the prior record (bound to its
  actual bytes, not just an id), a `reason`, a `trigger` (supersede | check_failed |
  human_flagged | self_correction), and the fix.
- **Ed25519 signatures over RFC 8785 (JCS) canonical JSON**, hash-chained so the whole
  ledger verifies offline — no trusted storage, and byte-identical across languages.
- **Drop-in adapters** for CrewAI, LangChain/LangGraph, Claude Code, and AutoGen.

The honesty rule baked in: an LLM doesn't reliably detect its own mistakes, so a correction
is written when it's *detected* (a failed check, a supersede, or a human flag) — never by
an agent's unaided conscience. And the scope is stated plainly: ACR proves *integrity* and
*attribution*, not *completeness* — a party that controls its own key can always choose not
to write a correction. The spec's §9 lays out the layers (gapless sequence, external anchor,
keyed detectors) that narrow that gap. I'd rather be honest about the boundary than
overclaim like most of the AI-governance tools out there.

Why this matters right now: the EU AI Act's deployer duties (monitor, suspend, retain logs
≥6 months, report incidents) went live on 2 August 2026. Every vendor is leaving the
corrective-action and incident-reporting obligations to a manual, non-cryptographic process.
A signed correction log is the artifact that evidences them — and it *supports* those duties
without pretending to certify them.

Core is ~200 lines, MIT licensed, with a spec and a JSON Schema you can implement yourself:
https://github.com/SaInT8888888888/corrlog

I'd genuinely welcome attacks on the spec — that's the point. Especially: the completeness
boundary (where tamper-evidence ends and disclosure-evidence needs independent observers),
and the RFC 8785 canonicalisation. Tell me what breaks.

## Subreddit posts (same core, tuned per community)

**r/LocalLLaMA / r/MachineLearning** — title:
"corrlog: an open proposal for cryptographically verifiable agent corrections (extends AAR, RFC 8785)"

**r/crewai** — title:
"corrlog: signed correction records for CrewAI tool calls (drop-in hook, ~80 lines)"

**r/LangChain / r/LangGraph** — title:
"corrlog: a correction-log middleware for LangGraph with native rollback via Command"

## Notes for Shane
- Positioned as "open proposal + reference implementation" (not "the missing standard") —
  per the external reviews, this is the honest framing that invites attack rather than
  overclaiming.
- Dropped "proves you aren't hiding what went wrong" — that's a completeness claim, and it
  was wrong. Now: integrity + attribution, with the completeness boundary stated openly.
- The "challenge in the comments" is now specific (completeness boundary, RFC 8785) — this
  is more honest and *more* engaging, because it signals we know where the weak points are.
