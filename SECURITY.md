# Security Model — Signature Validity and Signer Trust

This note documents the trust boundary of Agent Correction Records (ACRs), a
key-substitution weakness found while building an independent verifier, and the
mitigation now required by the spec. It is deliberately narrow: it describes what
verification does and does not establish, so that anyone consuming an ACR knows what a
passing check actually proves.

## Two distinct properties

Verifying an ACR involves two separate questions that must not be conflated:

1. **Signature validity** — is this record internally consistent, and does its signature
   match the public key presented with it? This is self-contained and checkable offline
   with no external state.
2. **Authenticity / trust** — was this record signed by a party the verifier has
   independent reason to trust? This cannot be answered by the record alone.

A record can be signature-valid and still untrustworthy. Treating (1) as if it answered (2)
is the core mistake described below.

## The finding: key substitution

Early verification was *self-authenticating*: the verifier trusted the public key embedded
in the record and checked the signature against that same key.

This accepts a forged record. An attacker constructs any record they like, signs it with a
key they control, and embeds that key alongside the signature. The signature is valid *for
the embedded key*, so a self-authenticating verifier accepts it. The check confirms only
that whoever wrote the record also signed it — which is trivially true for any author,
honest or not.

This surfaced when an ACR signed by an attacker-controlled key passed the standalone
verifier. It was not caught by the SDK's own tests, because the SDK and its in-tree
verifier shared the same assumption. An implementation that shares no code with the SDK —
reimplementing the spec from its text alone — was required to expose it. This is the
general reason a spec's guarantees should be validated by an independent implementation,
not only by the reference code.

## The mitigation: key pinning

Trust must be anchored to a public key the verifier already holds, supplied out of band
rather than read from the record under inspection. The verifier is given one or more
expected public keys (the `--key` pin) and rejects any record not signed by a pinned key,
regardless of whether the record's own signature is internally valid.

This is the same pattern as pinning a TLS chain to a known set of certificate authorities,
or verifying an SSH host by a previously recorded key fingerprint: the signature math is
necessary but not sufficient; trust derives from a prior, independent commitment to a
specific key.

With pinning, the substituted-key record correctly fails: its signature is valid for its
embedded key, but that key is not pinned, so verification rejects it.

## What a passing verification proves

A verification that passes against a pinned key establishes:

- **Integrity** — the record has not been altered since signing.
- **Attribution** — it was signed by the holder of the pinned key.
- **Chain consistency** — within a presented sequence, records are hash-linked in order
  with no undetected edits or reordering.

It does **not** establish:

- **Completeness** — that every relevant event was recorded. A key-holder can decline to
  write a record; a signed log proves nothing about what was never entered into it.
  Bounding this gap requires mechanisms outside signing — external anchoring, independent
  co-signers, and counterparty reconciliation — documented separately in SPEC.md §9.
- **Correctness of content** — that the recorded claim is true; only that the pinned
  key-holder asserted it.

Attribution and completeness are independent problems. Key pinning closes the attribution
gap. It does not touch the completeness gap, and no signature scheme can.

## Reporting

Security issues can be reported by opening an issue on the repository or contacting the
maintainer directly. Please do not disclose a suspected verification bypass publicly until
a fix is available.
