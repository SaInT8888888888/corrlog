# CorrLog 0.2.2 / corrlog-inspect 0.1.3 release notes

**Status: release candidate under review. Not published. Draft pull request only.**

This candidate hardens the signed-record implementation. It fixes a canonicalization
defect in 0.2.1 that produced records no conforming RFC 8785 implementation could
reproduce. It is deliberately narrow: see "What this release does and does not claim".

---

## Read this first: compatibility break

0.2.2 changes the canonical bytes that signatures cover. A record signed by 0.2.1
verifies under 0.2.2 only when its signed content is unaffected by the changes below.

Measured against the published 0.2.1 canonicalizer over a set of representative
record shapes: **11 of 20 byte-identical, 9 break.** The break is wider than the
Unicode case alone. It also covers two number classes.

### 1. Unicode

- 0.2.1 escaped every non-ASCII character as `\uXXXX` (`ensure_ascii=True`). RFC 8785
  requires those characters emitted as raw UTF-8. That is the root defect.
- Any 0.2.1-signed record whose signed content contains a non-ASCII character, in a
  value **or** a key, will not verify. This includes accented Latin (`café`), CJK
  (`日本語`), emoji and other astral-plane characters, and non-ASCII object keys.
- Key ordering also changes. 0.2.1 sorted object keys by Unicode code point. RFC 8785
  requires UTF-16 code unit order. The two agree for BMP keys and diverge as soon as a
  key lies outside the BMP.

### 2. Number formats inside signed content

- **Integral floats**: 0.2.1 wrote `56.0`, 0.2.2 writes `56`.
- **Exponent forms**: 0.2.1 wrote `1e-07` and `1e+16`, 0.2.2 writes `1e-7` and
  `10000000000000000`.
- Non-integral decimals such as `0.1` are unaffected.
- ACR core fields carry non-integers as strings, so in practice this bites metadata and
  extension content that carries raw JSON numbers.

### 3. Unsafe integers

- Integers with `|n| >= 2**53` are now **rejected** with `ValueError` and must be
  represented as strings.
- 0.2.1 accepted and signed them. Such a value cannot be re-signed by 0.2.2 without
  changing its representation, which is itself a new assertion about the data.

### No silent fallback

- There is no compatibility shim and no automatic migration.
- Re-signing a legacy record creates a new signed assertion. It does not make the
  original signature conformant, and it cannot restore anything the original did not
  record.
- Preserve the original receipt archives and the key material that signed them.
- Verify legacy records with the version that produced them. Verify records newly
  signed under 0.2.2 with any conforming implementation.

---

## Publish order is mandatory

**`corrlog-core` 0.2.2 MUST be published before `corrlog-inspect` 0.1.3.**

`corrlog-inspect` 0.1.3 declares `corrlog-core>=0.2.2` for its `core` extra. If inspect
is published first, `pip install corrlog-inspect[core]==0.1.3` cannot resolve, because
no such core version exists on the index yet.

Recommended sequence:

1. Publish `corrlog-core` 0.2.2.
2. Confirm it resolves from the index in a clean environment.
3. Publish `corrlog-inspect` 0.1.3.

---

## Dependency change

`corrlog-core` now depends on `jsonschema[format-nongpl]>=4.18,<5` in addition to
`cryptography`. Schema validation runs at record construction and at verification.
Environments that pin dependencies should expect additional transitive packages.

---

## What this release does and does not claim

**Does claim**

- Signed records of disclosed corrections.
- Per-record tamper detection against an independently trusted public key. Changes to
  signed canonical content are detected. Whitespace and member order are not signed
  distinctions.
- Schema-enforced records, with the same schema enforced by the core library and by
  the standalone verifier.
- Correction chain checking: unique IDs, predecessor ID and digest, rooted genesis,
  and optional trusted checkpoints binding length, genesis and head.
- Opt-in replay admission via a persistent guard on protected shared state.
- Independent offline verification, requiring an independently provisioned trusted key
  and verifier dependencies.

**Does not claim**

- A tamper-evident ledger or an immutable audit trail. JSONL files are untrusted
  transport and storage.
- Automatic replay prevention, or exactly-once processing.
- Guaranteed or durable delivery.
- Proof that a statement is true, or that every event has been recorded.
- Complete correction history without a separately trusted checkpoint.
- Trusted timestamps, semantic deduplication, distributed replay protection, witness
  consistency or external anchoring.
- Regulatory compliance.
- Production readiness.

---

## Verification in this candidate

Local evidence on Linux, in an independent review of this branch:

- Full CI step sequence green on **Python 3.10, 3.11, 3.12 and 3.13** (all 12 steps on
  each), with **70 tests passing** on every version.
- RFC 8785 Appendix B number samples: **26/26**, checked against the RFC text directly.
- Official JCS conformance vectors: **6/6** byte-exact.
- Differential fuzz against the independent `rfc8785` implementation:
  **99,956 of 100,000** randomized binary64 draws byte-identical, with 44 non-finite
  values correctly rejected.
- Structural fuzz over nested objects with non-ASCII and astral keys: matched.
- UTF-16 key ordering with a non-BMP key now correct.
- Lone surrogates rejected. Unsafe integers rejected. Safe boundary integers accepted.
- End-to-end: a record containing non-ASCII content verifies offline with the
  standalone verifier, and tampering with either a signed field or metadata is rejected.

Finite randomized testing is strong regression evidence, not exhaustive proof over all
binary64 values. Cross-platform CI (Windows, macOS) runs on the draft pull request and
its result is reported separately. Local results above are Linux only.
