"""End-to-end demo of the correction ledger. Run: python3 examples/demo.py"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from corrlog_core import generate_keypair, record, retract, verify, verify_chain, JsonlSink
import tempfile

priv, _ = generate_keypair()

print("=" * 60)
print("corrlog — the correction ledger")
print("=" * 60)

# --- The scenario: a forecast agent writes a wrong number, then a guard
# --- catches it, then a human catches a second issue in the correction.
r1 = record(
    agent_id="forecast-agent",
    agent_name="Zespri Forecast Agent",
    principal_id="mssap",
    action_type="memory.write",
    action_args={"project": "zespri", "record_type": "note", "topic": "orchard_yield"},
    action_result={"yield_forecast": 1420},
    private_key=priv,
)

c1 = retract(
    prior_record=r1,
    reason="yield figure used wrong unit (kg vs tonne)",
    trigger="check_failed",
    agent_id="forecast-agent",
    private_key=priv,
    fix_type="replace",
    corrected_content={"yield_forecast": 1.42},
    fix_note="converted kg to tonnes",
)

c2 = retract(
    prior_record=c1,
    reason="human review: forecast window was FY25, not FY26",
    trigger="human_flagged",
    agent_id="forecast-agent",
    private_key=priv,
    fix_type="replace",
    corrected_content={"fiscal_year": "FY26"},
    fix_note="corrected fiscal year",
)

chain = [r1, c1, c2]

print()
print("Ledger (3 records, hash-linked):")
for i, r in enumerate(chain):
    trig = r.get("trigger", "action")
    reason = r.get("reason") or "(initial action)"
    print(f"  {i}. [{trig:14s}] {r['action']['type']:12s} | {reason}")

print()
print("Verification:")
print(f"  all signatures valid:        {all(verify(r) for r in chain)}")
print(f"  chain hash-linked + valid:   {verify_chain(chain)}")

# Tamper demonstration
tampered = dict(r1)
tampered["action"] = {**r1["action"], "type": "payment.execute"}
print(f"  tampered record verifies:    {verify(tampered)}  (must be False)")

# Durable sink (fresh file each run)
path = os.path.join(tempfile.gettempdir(), f"corrlog-demo-{os.getpid()}.jsonl")
sink = JsonlSink(path)
for r in chain:
    sink.append(r)
reloaded = sink.all()
print(f"  durable sink round-trip:     {len(reloaded) == 3 and all(verify(r) for r in reloaded)}  ({path})")

print()
print("The story this tells an auditor:")
print("  'We caught a unit error (auto) and a fiscal-year error (human),")
print("   and both corrections are cryptographically signed and disclosed.'")
print("=" * 60)
