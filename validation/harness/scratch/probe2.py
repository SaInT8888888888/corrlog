import json, sys
import rfc8785
sys.path.insert(0, "/home/shane/corrlog-validation/cleanroom/env-clean/lib/python3.13/site-packages")
from corrlog_core import canonical_json, generate_keypair, record, retract

def cmp(name, obj):
    ours = canonical_json(obj)
    try:
        theirs = rfc8785.dumps(obj)
    except Exception as e:
        theirs = f"<oracle error: {type(e).__name__}: {e}>".encode()
    same = ours == theirs
    print(f"\n{name}")
    print(f"  ours   : {ours[:160]}")
    print(f"  oracle : {theirs[:160] if isinstance(theirs,bytes) else theirs}")
    print(f"  MATCH  : {same}")
    return same

print("="*72); print("RFC 8785 CONFORMANCE vs independent oracle (rfc8785 0.1.4)"); print("="*72)
results = []
results.append(cmp("ASCII basic", {"b": 1, "a": 2}))
results.append(cmp("non-ASCII string (e-acute)", {"note": "café"}))
results.append(cmp("non-ASCII (euro sign)", {"amount": "€100"}))
results.append(cmp("CJK", {"name": "日本語"}))
results.append(cmp("emoji astral", {"emoji": "\U0001F600"}))
results.append(cmp("control chars", {"t": "a\tb\nc\rd\x00e"}))
results.append(cmp("float 1.5", {"x": 1.5}))
results.append(cmp("float 1e16", {"x": 1e16}))
results.append(cmp("float 1e-7", {"x": 1e-7}))
results.append(cmp("float 0.1", {"x": 0.1}))
results.append(cmp("int", {"x": 12345}))
results.append(cmp("NFC vs NFD", {"x": "café", "y": "café"}))
# non-BMP key ordering (UTF-16 code unit order vs code point order)
key_obj = {"�": "replacement", "\U0001F600": "emoji"}
results.append(cmp("key order: BMP U+FFFD vs astral U+1F600", key_obj))

print("\n" + "="*72); print("SUMMARY"); print("="*72)
print(f"  {sum(results)}/{len(results)} canonicalization cases byte-identical to the oracle")

print("\n" + "="*72); print("SCHEMA CONFORMANCE of produced records"); print("="*72)
import jsonschema
schema = json.load(open("/home/shane/corrlog-validation/cleanroom/env-clean/lib/python3.13/site-packages/corrlog_core/schema/acr-v1.json"))
priv, pub = generate_keypair()
r1 = record(agent_id="agent-A", action_type="db.write", private_key=priv)
c1 = retract(prior_record=r1, reason="wrong value", trigger="check_failed", agent_id="agent-A", private_key=priv)
u1 = __import__("corrlog_core").unknown(agent_id="a", private_key=priv, subject="s")
for name, rec in [("record() action record", r1), ("retract() correction", c1), ("unknown() record", u1)]:
    errs = sorted(jsonschema.Draft202012Validator(schema).iter_errors(rec), key=lambda e: e.path)
    print(f"\n  {name}: {'SCHEMA-VALID' if not errs else 'SCHEMA-INVALID'}")
    for e in errs[:6]:
        print(f"     - {'/'.join(str(p) for p in e.path) or '<root>'}: {e.message[:110]}")

print("\n" + "="*72); print("EMPTY-INPUT records vs schema"); print("="*72)
e1 = record(agent_id="", action_type="", private_key=priv)
e2 = retract(prior_record=r1, reason="", trigger="check_failed", agent_id="", private_key=priv)
for name, rec in [("record(agent_id='',action_type='')", e1), ("retract(reason='')", e2)]:
    errs = list(jsonschema.Draft202012Validator(schema).iter_errors(rec))
    print(f"  {name}: verify={__import__('corrlog_core').verify(rec)}  schema={'VALID' if not errs else 'INVALID (' + '; '.join(e.message[:60] for e in errs[:3]) + ')'}")

print("\n" + "="*72); print("agent.publicKey vs signature.publicKey mismatch (properly crafted+signed)"); print("="*72)
import corrlog_core as cc
victim_priv, victim_pub = generate_keypair()
att_priv, att_pub = generate_keypair()
body = retract(prior_record=r1, reason="signed by attacker, claims victim identity",
               trigger="check_failed", agent_id="agent-A", private_key=att_priv)
body["agent"]["publicKey"] = cc.public_key_b64url(victim_pub)   # claim victim's identity
del body["signature"]
cc._sign(body, att_priv, cc.public_key_b64url(victim_pub))
print("  agent.publicKey     =", body["agent"]["publicKey"][:24], "(VICTIM)")
print("  signature.publicKey =", body["signature"]["publicKey"][:24], "(ATTACKER)")
print("  verify(no pin)                 =", cc.verify(body))
print("  verify(pinned victim)          =", cc.verify(body, public_key=victim_pub))
print("  verify(pinned attacker)        =", cc.verify(body, public_key=att_pub))
print("  -> a consumer reading agent.publicKey sees the VICTIM; verification used the ATTACKER key")

print("\n" + "="*72); print("TIMESTAMP plausibility + duplicate id semantics"); print("="*72)
print("  record() emits trigger='supersede', reason='' for a plain ACTION record:")
print("   ", json.dumps({k: r1[k] for k in ("reason", "trigger")}))
