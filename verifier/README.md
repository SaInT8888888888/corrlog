# Verifier — independent verification of ACR records

This directory contains a **standalone verifier** that shares *no code* with the
corrlog SDK. It exists so a third party can check our claims without importing our
library — the difference between "trust us, it verifies" and "here, verify it yourself."

## What's here

- `standalone.py` — reimplements RFC 8785 (JCS) canonicalization + Ed25519 verify +
  the supersedes hash-chain walk, from the spec text alone. Imports only stdlib +
  `cryptography`. ~200 lines, readable in one sitting.
- `generate_vectors.py` — uses the corrlog SDK to produce deterministic, frozen test
  vectors (fixed key seed, fixed ids/timestamps) into `vectors/`.
- `vectors/` — the frozen vectors:
  - `key.json` — the public key.
  - `action.json` — a signed action record.
  - `correction.json` — a signed correction superseding it.
  - `tampered.json` — the action record with the signed body mutated (MUST FAIL).
  - `wrong_key.json` — a record signed by a different key (MUST FAIL when pinned).

## How a third party checks us

```bash
# 1. Verify the action record's signature
python3 verifier/standalone.py verifier/vectors/action.json

# 2. Verify the full correction chain (action -> correction)
python3 verifier/standalone.py --chain verifier/vectors/action.json verifier/vectors/correction.json

# 3. Confirm a tampered record is rejected
python3 verifier/standalone.py verifier/vectors/tampered.json   # must FAIL

# 4. Confirm a wrong-key substitution is rejected when trust is pinned
python3 verifier/standalone.py --key verifier/vectors/key.json verifier/vectors/wrong_key.json
# must FAIL
```

## Why the `--key` flag matters

Without pinning, the verifier trusts the key embedded in the record (self-authenticating).
That is convenient but vulnerable to **key substitution**: an attacker signs a record with
their own key and embeds that key. A self-authenticating check accepts it. Pinning to the
known key (`key.json`) rejects it. A serious audit pins trust to a known key — this is the
same reason TLS pins CAs and SSH shows host-key fingerprints.

## The point

If our SDK ever produced a bad signature, `standalone.py` — which shares no code with it —
would reject it. The two agreeing on frozen vectors is the cross-implementation proof that
the signatures are real, not self-referential.
