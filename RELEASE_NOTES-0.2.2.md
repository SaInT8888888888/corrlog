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
- Key ordering can also change. 0.2.1 sorted object keys by Unicode code point. RFC 8785
  requires UTF-16 code unit order. The two orders are identical for keys inside the BMP.
  They can differ when a non-BMP key is present, depending on the keys it is compared
  against. The presence of a non-BMP key does not by itself guarantee a different order.

### 2. Number formats inside signed content

- **Integral floats**: 0.2.1 wrote `56.0`, 0.2.2 writes `56`.
- **Exponent forms**: 0.2.1 wrote `1e-07` and `1e+16`, 0.2.2 writes `1e-7` and
  `10000000000000000`.
- Non-integral decimals such as `0.1` are unaffected.
- ACR core fields carry non-integers as strings, so in practice this bites metadata and
  extension content that carries raw JSON numbers.

### 3. Integers and the binary64 numeric contract

- Wire-format numbers carry binary64 semantics, as ECMAScript `JSON.parse` and RFC 8785
  specify. A parsed integer literal is interpreted as the binary64 value it denotes.
- Constructors refuse to sign a Python integer that cannot be represented exactly:
  `2**53 + 1`, `10**20 + 1` and `10**400` are rejected before signing, including inside
  metadata, action arguments, action results and corrected content. Exact decimal
  quantities and identifiers belong in strings.
- A consequence worth understanding rather than discovering: two literals that map to the
  same binary64 have identical canonical bytes and therefore the same signature.
  `9007199254740992` and `9007199254740993` verify under one signature. That is a property
  of binary64 JSON numbers, shared with every conforming implementation, and it is stated
  here rather than implied away. Sign strings when the exact decimal digits matter.
- 0.2.1 accepted and signed integers of any magnitude and canonicalized some of them to
  different bytes. Such a value cannot be re-signed by 0.2.2 without changing its
  representation, which is itself a new assertion about the data.

### Measured effect on existing records

Seven representative record shapes were signed with the published `corrlog-core` 0.2.1
from PyPI and then verified three ways: 0.2.1's own verifier, the 0.2.2 core and standalone
verifier, and an independent native JavaScript canonicalizer with Node's Ed25519 primitive
(calibrated against the six JCS fixtures and all 26 Appendix B samples).

| Record content | 0.2.1 self-verify | 0.2.2 | Independent JS |
|---|---|---|---|
| ASCII-only strings | PASS | PASS | PASS |
| Non-integral float `0.1` | PASS | PASS | PASS |
| Integer `2**53` | PASS | PASS | PASS |
| Non-ASCII value | PASS | FAIL | FAIL |
| Non-ASCII object key | PASS | FAIL | FAIL |
| Integral float `56.0` | PASS | FAIL | FAIL |
| Exponent float `1e16` | PASS | FAIL | FAIL |

0.2.2 agrees with the independent implementation on all seven shapes. A wider byte-level
comparison over 20 shapes gave 11 identical and 9 differing. The record-level table is the
more useful measure, because it reflects what a stored record actually contains.

### What the break costs, stated accurately

Two things are true, and both belong in any disclosure:

1. **In the seven legacy fixtures tested, 0.2.2's results match the independent
   JavaScript signature checker.** This is not a general compatibility guarantee. Users
   of 0.2.1 can still face verification changes, including changes caused by schema
   enforcement. Preserve original archives and trusted public keys, and assess legacy
   records before upgrading.
2. **Users of 0.2.1's own verifier do face a real behaviour change.** 0.2.1's in-library
   verification accepted all seven shapes, including the four whose serialization was
   nonconforming. A record that verified under 0.2.1's own verifier may now fail. That is
   a compatibility break regardless of which side was conformant, and it must not be
   described as though nothing was lost.

Caveats to keep: this is seven representative shapes rather than an exhaustive sweep, and
0.2.2 enforces the record schema at verification time, so a legacy record that violates the
tightened schema could be rejected even with conformant signature bytes.

### Disclosure wording

> This update changes verification behavior. Some records that verified with 0.2.1 will no
> longer verify with 0.2.2. The causes are corrected Unicode serialization, corrected
> number serialization, and schema enforcement. Some affected signatures were
> nonconforming; do not assume every newly rejected signature was invalid under RFC 8785.
> Preserve original archives and trusted public keys, and assess legacy data before
> upgrading. Re-signing is a new assertion, not a repair of the historical signature.

### No silent fallback

- There is no compatibility shim and no automatic migration.
- Re-signing a legacy record creates a new signed assertion. It does not make the
  original signature conformant, and it cannot restore anything the original did not
  record.
- Preserve the original receipt archives and, critically, the **trusted public keys**.
  Verification needs the public key that the verifier is asked to trust. The private
  signing key is not required in order to verify an existing record, and holding it does
  not make a legacy signature conformant.
- Verify legacy records with the version that produced them. Verify records newly
  signed under 0.2.2 with any conforming implementation.

---

## Numeric contract (adopted from the lifecycle repair)

Two rules, split by where the risk sits:

- **Wire format and canonicalization use binary64 semantics**, as ECMAScript `JSON.parse`
  and RFC 8785 require. A parsed integer literal is interpreted as the binary64 value it
  denotes, so the codec invariant holds:

  ```
  canonical(parse(canonical(value))) == canonical(value)
  ```

- **Constructors apply an input guard before signing.** A Python integer that cannot be
  represented exactly as a finite binary64 is refused in the signed body and in dictionary
  content passed for hashing, so a caller cannot silently lose precision at creation time.

Both halves are needed. Without the first, the codec rejects valid canonical JSON: the
shortest decimal spelling of a binary64 is often not its exact mathematical integer
(`float(2**68)` spells as `295147905179352830000` while it is exactly
`295147905179352825856`). Without the second, an application could sign a rounded number
without noticing.

This is the third and adopted version of this rule for the candidate. The first rejected any
Python integer with `|n| >= 2**53` at canonicalization but not at construction, so the
library could accept `1e16`, sign it, write `10000000000000000`, and then reject that same
record once the JSON was parsed back. The second tried to admit a parsed integer only when
it equalled the double's exact value or the canonical spelling of it, which still rejected
three of the 24 finite Appendix B samples and 687 of 99,958 random draws. Both earlier
versions were reproduced and measured before being replaced, and their failure cases are
retained as regression tests.

The independent verifier delegates canonicalization to `rfc8785` and normalises received
numbers into the same binary64 domain, including Python tuples as arrays, so an in-memory
record verifies identically in both implementations. Cross-implementation agreement is
checked against a native JavaScript canonicalizer: 99,962 cases, zero mismatches.

Regression coverage: `tests/test_numeric_roundtrip.py` (round-trips over canonical and
ordinary JSON, wire-spelling equivalence, the CLI path, the constructor guard, and a seeded
closure fuzz), `tests/test_appendix_b_roundtrip.py` (every finite Appendix B sample through
signing, serialization, parsing and the CLI), `tests/test_chain_serialization.py` (chain and
checkpoint survival across serialization, with tamper rejection) and
`tests/test_lifecycle_contract.py` (whole-lifecycle contract, the same-binary64 boundary,
different-binary64 tamper rejection, and exact-string tamper rejection).

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

### Cross-platform CI

The draft pull request runs `.github/workflows/ci.yml` on all three operating systems
across all four supported Python versions. **12 of 12 jobs pass**, conclusion `success`,
on reconciled revision `2f485cf` (run `34441415484`).

| | 3.10 | 3.11 | 3.12 | 3.13 |
|---|---|---|---|---|
| Ubuntu | pass | pass | pass | pass |
| macOS | pass | pass | pass | pass |
| Windows | pass | pass | pass | pass |

A first run on an earlier revision of this branch failed all four Windows jobs at the new
full-suite step (`1 failed, 69 passed`). The cause was not a canonicalization defect: the
test read a JCS fixture with `read_text()` and no encoding, and Windows decodes with the
locale encoding (cp1252), mangling the non-ASCII bytes in `french.json`. Only that one
fixture contains raw non-ASCII, which is why exactly one test failed on Windows. Reading
the same file as UTF-8 reproduces the expected canonical bytes exactly. The same pattern
in the standalone verifier and the schema loads was a genuine defect and is fixed, with
the isolation notes below.

### Release packages in fresh environments

The 0.2.2 core wheel and the 0.1.3 Inspect wheel were built from this revision and tested
in four clean environments:

| Artifact | SHA-256 |
|---|---|
| `corrlog_core-0.2.2-py3-none-any.whl` | `59e448fb68efe08666468153082048784e360d655011257aa899da8cae7e80d8` |
| `corrlog_inspect-0.1.3-py3-none-any.whl` | `99241f1faddb3d086316354d3b37a9ccf30aebb8b291429de6b70b6188ecbc93` |

These are the artifacts of the current revision, which carries the adopted numeric contract.

- **Installed packages**: full suite run against the installed wheels, from a test tree
  containing no package source. **257 passed.** `pip check` clean. The suite grew from 70
  cases to 257 through the numeric regressions, the Appendix B lifecycle cases, the chain
  serialization cases and the lifecycle contract tests.
- **Numeric contract**: the retest's own reproduction passes. Every finite Appendix B sample
  survives signing, serialization, parsing and verification, 24 of 24. The closure fuzz,
  seed 20260910, shows **0 failures in 99,958 finite draws**. All CLI fixtures pass in both
  normal and canonical form. Canonical output matches an independent native JavaScript
  canonicalizer across **99,962 cases with 0 mismatches**.
- **Boundary behaviour, stated for users**: a literal that maps to the same binary64 as the
  signed value verifies, because the canonical bytes are identical. A literal that maps to a
  different binary64 is rejected, and tampering with a signed string is rejected. Sign
  strings when exact decimal digits must be authenticated.
- **Independent verifier environment**: `rfc8785`, `jsonschema` and `cryptography` only,
  with CorrLog absent (`find_spec("corrlog_core") is None`). `pip check` clean.
- **Inspect without core**: `corrlog-inspect` 0.1.3 installs and imports with no core
  present. `pip check` clean.
- **Legacy environment**: published `corrlog-core` 0.2.1 installed from PyPI, used to sign
  the compatibility matrix above. `pip check` clean.

### Standalone verifier behaviour

Run from the environment with no CorrLog installed, against records produced by the
installed 0.2.2 wheel:

| Case | Exit code | Result |
|---|---|---|
| Raw UTF-8 record, trusted key | 0 | PASS, valid under pinned key |
| Same record with `\uXXXX` escaping | 0 | PASS, valid under pinned key |
| Raw UTF-8 record, non-UTF-8 default locale | 0 | PASS, valid under pinned key |
| Wrong trusted key | 1 | FAIL, untrusted signer |
| Tampered signed field | 1 | FAIL |
| Tampered metadata | 1 | FAIL |
| Tampered signature | 1 | FAIL |

Storage escaping and locale do not affect the outcome, which is the intended behaviour:
the signature covers the parsed object, not the file bytes.

### Independent conformance checks

- RFC 8785 Appendix B number samples: **26/26**, checked against the RFC text directly.
- Official JCS conformance vectors: **6/6** byte-exact.
- Differential fuzz against the independent `rfc8785` implementation:
  **99,956 of 100,000** randomized binary64 draws byte-identical, with 44 non-finite
  values correctly rejected.
- Structural fuzz over nested objects with non-ASCII and astral keys: matched.
- UTF-16 key ordering with a non-BMP key: matches the independent implementation.
- Lone surrogates rejected. Constructors reject inexact application integers; the
  codec and verifier interpret received numbers as binary64. Exactly representable
  integer inputs are accepted by constructors.

Finite randomized testing is strong regression evidence, not exhaustive proof over all
binary64 values. The compatibility matrix covers seven representative record shapes, not
every possible record. Local Linux results and the fresh-environment package tests were run
on the review host; the macOS and Windows results come only from CI.
