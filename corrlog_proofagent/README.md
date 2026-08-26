# corrlog → ProofAgent adapter

Turns a ProofAgent governance gate verdict into a signed ACR correction receipt.

```python
from corrlog_proofagent import gate_to_acr

# gate_result is a ProofAgent GateResult (decision ∈ pass/review/block)
receipt = gate_to_acr(
    gate_result=gate_result,   # or {"decision": "block", "reasons": [...]}
    private_key=operator_key,  # the KEY CONTROLLED BY THE OPERATOR (not the vendor)
    agent_id="my-agent",
)

# receipt is None when decision == "pass" (nothing failed)
# receipt is a signed ACR correction record otherwise (trigger=check_failed)
```

**The mapping (deliberately honest):**

| gate decision | result |
|---|---|
| `pass` | no receipt (nothing failed) |
| `review` | signed correction, `trigger=check_failed` |
| `block` | signed correction, `trigger=check_failed` |

The receipt attests that *ProofAgent caught a failure* and is signed by the
operator's key — so the evaluated vendor can't silently reinterpret or disappear
it, and anyone can verify it against the operator's pinned key with
`verifier/standalone.py`.

It does **not** claim completeness: the operator's key signs what the gate *did*
observe, nothing more (see `SPEC.md` §2, §9).

**Why fix_type is `other`:** a gate verdict is not a replace/delete/rollback — it
is a recorded *detection*. The review-vs-block distinction travels in the record's
`metadata.gate_decision` (human-readable) rather than in the fix type.

**Import-safe:** the adapter parses ProofAgent's output shapes (dataclass or dict)
and never imports ProofAgent itself, so it works whether or not the harness is
installed.
