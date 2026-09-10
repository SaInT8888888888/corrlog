import json, sys, traceback
from corrlog_core import (generate_keypair, record, retract, unknown, verify,
                          verify_chain, canonical_json, load_private_key,
                          public_key_b64url, JsonlSink, MemorySink)

def hdr(t): print("\n" + "="*72 + f"\n{t}\n" + "="*72)

priv, pub = generate_keypair()
r1 = record(agent_id="agent-A", action_type="db.write", private_key=priv)
c1 = retract(prior_record=r1, reason="wrong value", trigger="check_failed",
             agent_id="agent-A", private_key=priv)
c2 = retract(prior_record=c1, reason="still wrong", trigger="human_flagged",
             agent_id="agent-A", private_key=priv)
chain = [r1, c1, c2]

hdr("P1: truncated chain (root record removed)")
try:
    print("verify_chain([r1,c1,c2]) =", verify_chain(chain))
    print("verify_chain([c1,c2])     =", verify_chain(chain[1:]), "  <-- root dropped")
    print("verify_chain([c2])        =", verify_chain(chain[2:]), "  <-- single orphan correction")
    print("verify_chain([])          =", verify_chain([]), "  <-- EMPTY LIST")
except Exception as e:
    print("EXC", type(e).__name__, e)

hdr("P2: verify() on malformed top-level types")
for bad in [None, [], "a string", 42, True]:
    try:
        print(f"  verify({bad!r:20}) -> {verify(bad)}")
    except Exception as e:
        print(f"  verify({bad!r:20}) -> RAISED {type(e).__name__}: {e}")

hdr("P3: verify() when 'signature' is a non-dict")
for bad_sig in ["abc", 123, [], True]:
    rec = dict(r1); rec["signature"] = bad_sig
    try:
        print(f"  signature={bad_sig!r:8} -> {verify(rec)}")
    except Exception as e:
        print(f"  signature={bad_sig!r:8} -> RAISED {type(e).__name__}: {e}")

hdr("P4: self-authenticating verify accepts a forged record (attacker key)")
att_priv, att_pub = generate_keypair()
forged = record(agent_id="agent-A", action_type="db.write",
                action_result={"stolen": True}, private_key=att_priv)
print("  verify(forged) [no pin]         =", verify(forged))
print("  verify(forged, pinned real pub) =", verify(forged, public_key=pub))

hdr("P5: third party extends someone else's chain with their own key")
ext = retract(prior_record=c2, reason="attacker says: ignore prior",
              trigger="self_correction", agent_id="agent-A", private_key=att_priv)
extended = [r1, c1, c2, ext]
print("  verify_chain(extended) [no pin]     =", verify_chain(extended))
print("  verify_chain(extended, pinned real) =", verify_chain(extended, public_key=pub))

hdr("P6: supersedes.receiptId not cross-checked by verify_chain")
c_mismatch = c1.copy()
print("  c1.supersedes.receiptId =", c1["supersedes"]["receiptId"], " r1.correctionId =", r1["correctionId"])
print("  verify_chain([r1,c1]) =", verify_chain([r1, c1]))
# craft a correction with a WRONG receiptId but correct digest, signed legitimately
import corrlog_core as cc
body = {k: v for k, v in c1.items() if k != "signature"}
body["supersedes"] = dict(c1["supersedes"]); body["supersedes"]["receiptId"] = "TOTALLY-DIFFERENT-ID"
cc._sign(body, priv, public_key_b64url(pub))
print("  crafted: receiptId='TOTALLY-DIFFERENT-ID', digest still correct")
print("  verify(crafted)            =", verify(body, public_key=pub))
print("  verify_chain([r1,crafted]) =", verify_chain([r1, body], public_key=pub))

hdr("P7: agent.publicKey vs signature.publicKey mismatch")
att2_priv, att2_pub = generate_keypair()
m = retract(prior_record=r1, reason="impersonation attempt", trigger="check_failed",
            agent_id="agent-A", private_key=att2_priv)
m["agent"]["publicKey"] = public_key_b64url(pub)   # claim victim identity
cc._sign({k: v for k, v in m.items() if k != "signature"}, att2_priv, public_key_b64url(pub))
print("  agent.publicKey == victim, signature.publicKey == attacker")
print("  verify(m) [no pin]                =", verify(m))
print("  verify(m, pinned victim pub)      =", verify(m, public_key=pub))
print("  verify(m, pinned attacker pub)    =", verify(m, public_key=att2_pub))

hdr("P8: duplicate record IDs / replay at the sink level")
sink = MemorySink()
sink.append(c1); sink.append(c1); sink.append(c1)
print("  MemorySink after 3x append of the SAME record: len =", len(sink.all()))
print("  sink.get(id) returns the first; no duplicate signal available")
import tempfile, os
p = os.path.join(tempfile.mkdtemp(), "s.jsonl")
j = JsonlSink(p); j.append(r1); j.append(r1)
print("  JsonlSink after 2x append of same record: len =", len(j.all()), "damaged =", j.damaged_lines)

hdr("P9: replayed identical record appended to the same FILE (file-level replay)")
print("  no dedup API on either sink: does any core function detect it?",
      "verify_chain catches only in-chain position replay")

hdr("P10: back-dated timestamp accepted")
old = retract(prior_record=r1, reason="backdated", trigger="human_flagged",
              agent_id="agent-A", private_key=priv, timestamp="1999-01-01T00:00:00+00:00")
print("  correction timestamp 1999 (before the action it supersedes):",
      "verify =", verify(old), " verify_chain =", verify_chain([r1, old]))
print("  r1 timestamp =", r1["timestamp"][:19], " c timestamp =", old["timestamp"][:19])

hdr("P11: empty inputs")
try:
    e1 = record(agent_id="", action_type="", private_key=priv)
    print("  record(agent_id='', action_type='') -> created, verify =", verify(e1))
except Exception as e:
    print("  record(agent_id='') RAISED", type(e).__name__, e)
try:
    e2 = retract(prior_record=r1, reason="", trigger="check_failed", agent_id="", private_key=priv)
    print("  retract(reason='') -> created, verify =", verify(e2))
except Exception as e:
    print("  retract(reason='') RAISED", type(e).__name__, e)

hdr("P12: load_private_key prefixes")
raw_seed_b64 = __import__("base64").urlsafe_b64encode(
    priv.private_bytes(__import__("cryptography.hazmat.primitives.serialization", fromlist=['x']).Encoding.Raw,
                       __import__("cryptography.hazmat.primitives.serialization", fromlist=['x']).PrivateFormat.Raw,
                       __import__("cryptography.hazmat.primitives.serialization", fromlist=['x']).NoEncryption())
).decode().rstrip("=")
hex_seed = priv.private_bytes(__import__("cryptography.hazmat.primitives.serialization", fromlist=['x']).Encoding.Raw,
                              __import__("cryptography.hazmat.primitives.serialization", fromlist=['x']).PrivateFormat.Raw,
                              __import__("cryptography.hazmat.primitives.serialization", fromlist=['x']).NoEncryption()).hex()
for name, val in [("bare b64url", raw_seed_b64), ("hex", hex_seed),
                  ("sk_<b64url>", "sk_" + raw_seed_b64), ("priv_<b64url>", "priv_" + raw_seed_b64),
                  ("ed25519:<b64url>", "ed25519:" + raw_seed_b64), ("sk_<hex>", "sk_" + hex_seed)]:
    try:
        k = load_private_key(val)
        ok = public_key_b64url(k.public_key()) == public_key_b64url(pub)
        print(f"  {name:18} -> {'OK' if ok else 'WRONG KEY (silent!)'}")
    except Exception as e:
        print(f"  {name:18} -> RAISED {type(e).__name__}: {str(e)[:60]}")
