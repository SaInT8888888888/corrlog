# Security note: self-authenticating verification vs key substitution

**Status:** resolved. This documents a real vulnerability the independent verifier
surfaced, the fix, and why the verifier is not ceremonial.

## The finding

When building the independent verifier (`verifier/standalone.py`), a wrong-key test
vector *passed* verification. A record signed by an attacker's key — with that key
embedded in the record's `signature.publicKey` — was accepted as valid.

This is **key substitution**. A self-authenticating verifier (one that trusts the key
embedded in the record) cannot distinguish "signed by the party we trust" from "signed by
whoever wrote this record." The attacker controls both the record and the embedded key, so
they produce a signature that the verifier happily accepts. The record is *self-consistent*
but not *authentic to us*.

The corrlog SDK's own test suite did not catch this, because the SDK and its verifier
share the same assumption (trust the embedded key). It was only exposed by re-implementing
verification independently, from the spec, and testing the two against each other.

## Why this matters

Integrity (was the record altered?) and attribution (which key signed it?) are only
meaningful if the key is *trusted*. A self-authenticating check answers "does this record
carry a valid signature?" — which is not the question an auditor asks. The auditor asks
"does this record carry *the right party's* signature?" Those are different questions, and
only key pinning answers the second.

## The fix

The spec now separates two concepts that are easy to conflate:

1. **Signature validity** — the signature is correct for *some* key. This is what a
   self-authenticating check does, and it is still useful (transport, quick sanity checks).
2. **Trust** — the signature is correct for a *known, pinned* key. This is what an audit
   requires.

The standalone verifier supports both:

- Without `--key`: self-authenticating (trusts the embedded key).
- With `--key key.json`: pinned (rejects any record not signed by that exact key).

```bash
# Self-authenticating: accepts a wrong-key record (the embedded key is "valid").
python3 verifier/standalone.py verifier/vectors/wrong_key.json

# Pinned: rejects it, because the known key did not sign it.
python3 verifier/standalone.py --key verifier/vectors/key.json verifier/vectors/wrong_key.json
```

This is the same trust model as TLS pinning CAs, or SSH showing a host-key fingerprint on
first connect: the *channel* of trust is explicit, not inferred from the record itself.

## Test coverage

`tests/test_fixture.py::test_standalone_rejects_wrong_key_when_pinned` locks this in: the
wrong-key vector MUST fail when pinned to the real key. If that regression ever reopens,
the fixture fails.

## Why this validates the architecture

The bug is not the interesting part — self-authenticating verification being vulnerable to
key substitution is well known. The interesting part is *how it was found*: not by the SDK
testing itself, but by an independent verifier that shares no code with the SDK, checked
against frozen vectors. That is exactly what the independent verifier is for, and it is why
it is a first-class artifact, not a demo prop.
