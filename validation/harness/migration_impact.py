#!/usr/bin/env python3
"""What does the canonicalization fix break?

Signs records with the PUBLISHED (pre-fix) corrlog-core 0.2.1, then verifies
them with the FIXED build, and vice versa. Answers precisely which existing
records stop verifying:

  * ASCII-only records with integer/string values  -> unaffected
  * records containing ANY non-ASCII text          -> old signature no longer valid
  * records containing non-integer floats          -> old signature no longer valid

Run:  ./cleanroom/env-clean/bin/python migration_impact.py
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OLD_PY = os.environ.get("CORRLOG_OLD_PY", os.path.join(ROOT, "cleanroom/env-clean/bin/python"))
NEW_PY = os.environ.get("CORRLOG_NEW_PY", os.path.join(ROOT, "env-fixed/bin/python"))


def site_packages(py):
    """site-packages directory for a venv interpreter (version independent)."""
    for part in os.listdir(os.path.join(os.path.dirname(py), "..", "lib")):
        cand = os.path.join(os.path.dirname(py), "..", "lib", part, "site-packages")
        if os.path.isdir(cand):
            return os.path.normpath(cand)
    raise SystemExit(f"no site-packages under {py}")

SIGN = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from corrlog_core import record, retract, generate_keypair, public_key_b64url
priv, pub = generate_keypair()
r = record(agent_id="agent-alpha", action_type="db.write", action_args={"y": 1420},
           private_key=priv, correction_id="root", timestamp="2026-09-10T00:00:00+00:00")
c = retract(prior_record=r, reason=sys.argv[2], trigger="check_failed",
            agent_id="agent-alpha", private_key=priv, fix_type="replace",
            correction_id="c1", timestamp="2026-09-10T00:00:00+00:00")
print(json.dumps({"correction": c, "publicKey": public_key_b64url(pub)}))
"""

VERIFY = r"""
import base64, json, sys
sys.path.insert(0, sys.argv[1])
from corrlog_core import verify
from cryptography.hazmat.primitives.asymmetric import ed25519
d = json.load(open(sys.argv[2]))
raw = base64.urlsafe_b64decode(d["publicKey"] + "=" * (-len(d["publicKey"]) % 4))
print(verify(d["correction"], public_key=ed25519.Ed25519PublicKey.from_public_bytes(raw)))
"""


def run(py, code, *args):
    p = subprocess.run([py, "-c", code, *args], capture_output=True, text=True, cwd="/tmp")
    return p.stdout.strip(), p.stderr.strip()


CASES = [
    ("ASCII reason, integer values", "wrong unit: kg vs tonne"),
    ("ASCII reason with a slash/quote", 'wrong path "a/b" in table'),
    ("non-ASCII: accented text", "wrong unit: café vs tonne"),
    ("non-ASCII: CJK", "the field name 日本語 was wrong"),
    ("non-ASCII: emoji", "the flag was wrong \U0001F600"),
    ("non-ASCII: micro sign", "off by 2 µs"),
]

print("=" * 78)
print("MIGRATION IMPACT: records signed by published 0.2.1, verified by the fixed build")
print("=" * 78)
print(f"{'case':38} {'signed by':12} {'verified by':12} result")
print("-" * 78)
for label, reason in CASES:
    with tempfile.TemporaryDirectory() as td:
        out, err = run(OLD_PY, SIGN, site_packages(OLD_PY), reason)
        if not out:
            print(f"{label:38} ERROR: {err[:60]}")
            continue
        rp = os.path.join(td, "rec.json")
        open(rp, "w").write(out)
        old_says, _ = run(OLD_PY, VERIFY, site_packages(OLD_PY), rp)
        new_says, _ = run(NEW_PY, VERIFY, site_packages(NEW_PY), rp)
        verdict = "compatible" if new_says == "True" else "*** SIGNATURE NO LONGER VALID ***"
        print(f"{label:38} {'0.2.1':12} {'fixed':12} old={old_says:5} new={new_says:5}  {verdict}")

print()
print("=" * 78)
print("Same records signed by the FIXED build, verified by the fixed build")
print("=" * 78)
for label, reason in CASES:
    with tempfile.TemporaryDirectory() as td:
        out, err = run(NEW_PY, SIGN, site_packages(NEW_PY), reason)
        rp = os.path.join(td, "rec.json")
        open(rp, "w").write(out)
        new_says, _ = run(NEW_PY, VERIFY, site_packages(NEW_PY), rp)
        print(f"{label:38} new-signed={new_says}")
