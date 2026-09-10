# corrlog — the Agent Correction Record (ACR) SDK

**A cryptographically signed, tamper-evident record of corrections to agent actions,
plus the corrective action taken.**

CorrLog records signed assertions about actions, corrections and uncertainty.
Individual records can be verified offline against a separately trusted public key.
Signatures do not prove the assertions true or that every event was recorded.
JSONL storage is not a tamper-evident ledger.

- **`corrlog-core`** — Ed25519 signing, RFC 8785 canonicalization, schema validation,
  explicit trusted verification, rooted correction-chain checks and optional replay admission.
  Runtime dependencies: `cryptography`, `jsonschema`.
- **`corrlog-crewai`** — drop-in CrewAI tool-call hooks (import-safe).
- **`corrlog-langchain`** — `AgentMiddleware` for LangChain/LangGraph (native rollback via `Command`).
- **`corrlog-claude-code`** — hook CLI + `hooks.json` plugin.
- **`corrlog-autogen`** — `GuardedTool` wrapper over `run_json` (greenfield — no merged hook yet).
- **`corrlog-proofagent`** — governance gate verdict (pass/review/block) → signed `check_failed`
  receipt, signed by the *operator's* key (import-safe, parses dataclass or dict).
- **`corrlog-inspect`** — `Hooks` extension for UK AISI Inspect: emits a signed receipt on an
  `INCORRECT` score, agent identity from `spec.model` (extension package, no core changes).

## Why

A correction record preserves a signer's account of a detected mistake and the
reported response. It gives a reviewer evidence to verify and investigate, while
keeping the distinction between a signed assertion and proof of its truth.

## The honesty rule

An LLM does not reliably detect its own mistakes. So a correction is written when it is
**detected** — by a supersede, a failed check, or a human flag — never by an LLM's unaided
conscience. The key that holds authority over the action signs it either way (the agent's
key, or the runtime that holds it). The signature proves *who recorded the correction*, not
that the model recognised its own error.

**Scope, stated plainly:** ACR proves *integrity* (records weren't altered) and
*attribution* (which key signed). It does **not** prove *completeness* (that no mistakes
were hidden) — a party that controls its own key can simply never write a correction. See
SPEC.md §2 and §9 for the full boundary and the layers that narrow it.

> **Security:** the independent verifier surfaced a key-substitution vulnerability in
> self-authenticating verification; the spec now separates signature validity from trust
> and supports pinned keys. See [SECURITY.md](SECURITY.md).

| `trigger` | meaning |
|---|---|
| `supersede` | newer write replaced an older one |
| `check_failed` | a guard/validator/policy rejected an action |
| `human_flagged` | a person marked a prior output wrong |
| `self_correction` | the agent detected it (weakest) |

## Quick start

```bash
pip install corrlog-core
```

```python
from corrlog_core import generate_keypair, record, retract, unknown, verify_trusted, verify_chain, chain_checkpoint, MemorySink

priv, trusted_key = generate_keypair()
sink = MemorySink()

# 1. Agent acts
r1 = record(agent_id="forecast-agent", action_type="memory.write",
            action_args={"project": "zespri", "topic": "yield"},
            action_result={"yield": 1420}, private_key=priv)

# 2. A check catches it's wrong -> signed correction WITH the source of truth
c1 = retract(prior_record=r1, reason="wrong unit (kg vs tonne)",
             trigger="check_failed", agent_id="forecast-agent", private_key=priv,
             fix_type="replace", corrected_content={"yield": 1.42},
             source_type="schema", source_reference="zespri/yield.fields")

# 3. Or the agent declines to guess -> a signed "I don't know" record
u1 = unknown(agent_id="forecast-agent", private_key=priv,
             subject="zespri.yield unit", note="not confirmed against the schema")

# 4. This demo already knows its signing key. In a real consumer, provision the
# public key and latest checkpoint separately through authenticated channels.
checkpoint = chain_checkpoint([r1, c1])
assert verify_trusted(c1, trusted_key)
assert verify_chain([r1, c1], trusted_key, checkpoint=checkpoint)
assert verify_trusted(u1, trusted_key)

# 5. Tamper-evident: mutate the record and verification fails
r1["reason"] = "tampered"
assert not verify_trusted(r1, trusted_key)
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

## Trust, replay and limitations

`verify(record)` remains a signature-consistency check using the embedded key;
it does not establish signer trust. Prefer `verify_trusted` as above. Obtain a
public key from authenticated operator configuration, never from the record under test.

A chain without a separately trusted checkpoint can be a valid prefix of a longer
history. JSONL files do not detect line deletion, reordering, truncation or replay.
For persistent consumer admission:

```python
from corrlog_core.replay import ReplayGuard
admissions = ReplayGuard("protected-admissions.sqlite")
if admissions.accept(c1, trusted_key):
    print("First admission of this correction ID")
```

Retain and protect the database across restarts. This provides at-most-once admission
per ID, not exactly-once processing or detection of equivalent events with fresh IDs.
Inspect emission does not automatically use this guard. See SPEC.md and SECURITY.md.

## Candidate status and compatibility

This is unreleased remediation for 0.2.2. Do not assume the published 0.2.1 package
contains these fixes. Install the reviewed source/wheel for testing. No production
readiness or release approval is implied. See RELEASE_READINESS.md for evidence.

The canonicalization correction can reject historical 0.2.1 records. Schema validation
also rejects malformed records previously accepted. Preserve legacy archives; do not
silently re-sign them. CorrLog does not certify compliance or implement retention policy.

## Tests

Install test dependencies (`pytest`, `rfc8785`, `inspect-ai`) in addition to the package,
then run `python -m pytest tests -q`. See validation/ for the separate clean-room evidence.
