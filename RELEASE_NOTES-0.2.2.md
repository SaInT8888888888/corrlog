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

### 3. Unsafe integers

- Integers with `|n| >= 2**53` are now **rejected** with `ValueError` and must be
  represented as strings.
- 0.2.1 accepted and signed them. Such a value cannot be re-signed by 0.2.2 without
  changing its representation, which is itself a new assertion about the data.

### Measured effect on existing records

Seven representative record shapes were signed with the published `corrlog-core` 0.2.1
from PyPI, then verified with the built 0.2.2 wheel and with the standalone verifier.
**Two still verify. Five do not.**

| Record content | Verifies under 0.2.2 |
|---|---|
| ASCII-only strings | Yes |
| Non-ASCII value (`Zürich café`) | No |
| Non-ASCII object key | No |
| Non-integral float (`0.1`) | Yes |
| Integral float (`56.0`) | No |
| Exponent float (`1e16`) | No |
| Integer at or above 2^53 | No |

A wider byte-level comparison over 20 shapes gave 11 identical and 9 differing. The
record-level table above is the more useful measure, because it reflects what a stored
record actually contains.

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
across all four supported Python versions. **12 of 12 jobs pass**, conclusion `success`.

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
| `corrlog_core-0.2.2-py3-none-any.whl` | `a7806502e7f9e10f2dcbae6816bbe7f827c659a21f03c9b654ebdd0e2481f0ec` |
| `corrlog_inspect-0.1.3-py3-none-any.whl` | `5cec1bd1eeec6ea1f9a1161217b1c88b577c61daeee7e5a5ed077e76a5489274` |

- **Installed packages**: full suite run against the installed wheels, from a test tree
  containing no package source. **70 passed.** `pip check` clean.
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
- Lone surrogates rejected. Unsafe integers rejected. Safe boundary integers accepted.

Finite randomized testing is strong regression evidence, not exhaustive proof over all
binary64 values. The compatibility matrix covers seven representative record shapes, not
every possible record. Local Linux results and the fresh-environment package tests were run
on the review host; the macOS and Windows results come only from CI.
