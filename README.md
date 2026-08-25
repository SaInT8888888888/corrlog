# corrlog — the Agent Correction Record (ACR) SDK

**A cryptographically signed, tamper-evident record of an agent's self-disclosed
mistakes and the corrective action taken.**

`corrlog` extends the [AAR receipt spec](https://github.com/Cyberweasel777/agent-action-receipt-spec)
with the one thing every receipt standard is missing: a **correction record** — an agent
signing "I did X, X was wrong, here's the fix and why." Receipts prove what happened;
corrections prove you aren't hiding what went wrong.

- **`corrlog-core`** — framework-independent sign / verify / record / retract, Ed25519 over
  canonical JSON (JCS), hash-chained. Single dependency: `cryptography`.
- **`corrlog-crewai`** — drop-in CrewAI tool-call hooks (import-safe).
- **`corrlog-langchain`** / **`corrlog-claude-code`** — next (see SPEC.md).

## Why

Every agent vendor sells "our agent is reliable" and hides mistakes. An auditor cannot
distinguish "a system that never erred" (impossible) from "a system that hid its errors."
A signed correction log is proof of *disclosure*, not proof of failure.

## The honesty rule

An LLM does not reliably detect its own mistakes. So a correction is written when it is
**detected** — by a supersede, a failed check, or a human flag — never by an LLM's unaided
conscience. The agent's key signs it either way.

| `trigger` | meaning |
|---|---|
| `supersede` | newer write replaced an older one |
| `check_failed` | a guard/validator/policy rejected an action |
| `human_flagged` | a person marked a prior output wrong |
| `self_correction` | the agent detected it (weakest) |

## Quick start

```python
from corrlog_core import generate_keypair, record, retract, verify, verify_chain, MemorySink

priv, _ = generate_keypair()
sink = MemorySink()

# 1. Agent acts
r1 = record(agent_id="forecast-agent", action_type="memory.write",
            action_args={"project": "zespri", "topic": "yield"},
            action_result={"yield": 1420}, private_key=priv)

# 2. A check catches it's wrong -> signed correction
c1 = retract(prior_record=r1, reason="wrong unit (kg vs tonne)",
             trigger="check_failed", agent_id="forecast-agent", private_key=priv,
             fix_type="replace", corrected_content={"yield": 1.42})

# 3. Verify — offline, no trusted storage
assert verify(c1)              # signature valid
assert verify_chain([r1, c1])  # hash-linked, tamper-evident

# 4. Tamper-evident: mutate the record and verification fails
r1["reason"] = "tampered"
assert not verify(r1)
```

Run the full demo: `python3 examples/demo.py`

## CrewAI

```python
from corrlog_crewai import CrewAICorrectionLog, install
from corrlog_core import generate_keypair, JsonlSink

priv, _ = generate_keypair()
log = CrewAICorrectionLog(JsonlSink("corrections.jsonl"), priv, agent_id="my-agent")
install(log)   # registers before/after tool-call hooks globally

# A human can flag a prior record wrong at any time:
log.mark_wrong(prior_record, "wrong amount", fix_note="corrected")
```

## Compliance mapping (honest)

ACR *supports* — it does not certify — EU AI Act duties for in-scope systems:
Art 26(5) monitor/suspend, Art 26(6) log retention ≥6 months, Art 20 corrective actions,
Art 73 serious-incident reporting; NIST AI RMF MANAGE 4.3. See SPEC.md §8 for what we can
and cannot claim.

## Status

`corrlog-core` + `corrlog-crewai` implemented and tested. `corrlog-langchain`,
`corrlog-claude-code`, `corrlog-autogen` on the roadmap (SPEC.md documents the integration
points for each).

## Tests

```
python3 tests/test_core.py
```
