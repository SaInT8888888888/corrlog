# ProofAgent outreach — draft for Shane's review

**To:** ProofAgent maintainers (via their GitHub repo issue, or contact listed on their site)
**Subject line (issue title):** [idea] Emit a signed "correction receipt" when an adversarial eval catches a failure

---

## Body

Hi — I'm the author of corrlog, a small open-source spec + reference implementation for a
cryptographically signed "Agent Correction Record" (ACR): when an agent action is later
found to be wrong, the *detector* can emit a signed, hash-chained receipt recording the
failure, the reason, the trigger (check_failed / human_flagged / supersede), and the fix.

Repo (MIT, ~200 lines of core, with an independent verifier + frozen test vectors):
https://github.com/SaInT8888888888/corrlog

**Why I'm writing to you specifically:** your harness already does the hard part — it
adversarially tests agents and produces evidence-backed findings. What it produces today is
an *internal* finding. If, when a test fails, ProofAgent emitted a portable signed
correction receipt (the ACR format), that finding would become a tamper-evident artifact the
evaluated vendor can't silently reinterpret or disappear. "ProofAgent caught this, here's the
signed record" is a stronger governance claim than "here's our internal report."

I'm not asking you to adopt or require ACR. The ask is much smaller: **could your
detector/verdict step emit one ACR-compatible receipt when it identifies a failed agent
action?** I'll do the integration work — a tiny adapter, tested against your output — if
you're open to the experiment.

Two things I hope signal this is serious engineering, not an AI-governance manifesto:

1. While building an independent verifier (which shares zero code with the SDK) against
   frozen test vectors, we found that self-authenticating receipts allow key substitution —
   an attacker can sign a record with their own key and embed that key, and a naive verifier
   accepts it. The spec now separates *signature validity* from *trust* and supports pinned
   verifier keys. Documented here: https://github.com/SaInT8888888888/corrlog/blob/master/SECURITY.md

2. The correction record is deliberately honest about scope: it proves integrity +
   attribution, not completeness (see SPEC §2 and §9) — it doesn't claim to certify EU AI
   Act compliance, only to evidence the corrective-action duties.

If a "your failed test becomes a signed receipt" integration is interesting, I'd love a
15-minute call or a thread here to sketch the adapter. If it's not a fit right now, no
worries — and I'd welcome any steer on who *would* find this useful.

Thanks for the work on ProofAgent.

---

## Notes for Shane

- **Small ask, not "adopt my standard."** The ask is "emit one ACR-compatible receipt," not
  "require ACR." This is the lowest-friction entry per ChatGPT's advice.
- **Why the framing works:** it positions ProofAgent as *strengthening* their existing
  value (evidence-backed findings → tamper-evident findings), not asking them to endorse us.
- **The key-substitution story is the opener's engine.** It signals real security work and
  gives a concrete, verifiable reason to click through to the repo.
- **Honest scope note included** — matches the discipline both external reviewers praised.
- **Send via:** their GitHub repo (open an issue) is the most public, findable channel; if
  they have a contact/Discord, that's more direct. I'd do issue first — it's linkable and
  shows up in their public record.
- **One thing I need from you before sending:** whether to send from your identity or a
  project identity, and which channel. I've written it neutral so it works either way.
