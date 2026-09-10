# CorrLog release-readiness review — 10 September 2026

## Decision

**0.2.2 remains a reviewed remediation candidate, not approved for publication.**

Two of the three original release gates are now closed. The cross-platform CI matrix has
been executed and passes on all three operating systems across all four supported Python
versions, and the release packages have been built and tested in fresh environments. The
one gate still open is a maintainer decision: explicit approval of the release and
disclosure of the legacy-signature compatibility change.

**Unqualified production readiness: no.** A tamper-evident ledger, automatic replay
prevention, guaranteed delivery and complete audit history are not implemented. No merge,
tag or PyPI publication has been performed. A branch push and a draft pull request were
made so that the Windows and macOS CI legs could run.

This review starts from master `b85910dcbd9091cbb80583ca858e4286ecbc3815`, matching
the handover exactly, on branch `remediation/release-readiness`. The supplied patch
was inspected and checked against the base before application; it was then revised.
The authoring machine's live checkout was not available to the original review. This
repository reproduces its supplied patch, not any changes made there after the handover.
See "Final revision and platform results" below for what has since been added on top.

## Final revision and platform results

Tested code revision: `c0043fe`, the revision the CI matrix and the fresh-environment
package tests below were run against, on the branch `remediation/release-readiness`
(draft pull request against `master`, `https://github.com/SaInT8888888888/corrlog/pull/6`).
Documentation-only commits may sit above it; they change no packaged file, so the wheel
hashes recorded below remain the tested artifacts. History on top of the base:

- `505832c` code and tests: verification, schema, trust and replay hardening
- `cfb4ca5` evidence and the original release-readiness report
- `b38f6e3` `RELEASE_NOTES-0.2.2.md`
- `f92e510` tests read fixtures as UTF-8 explicitly
- `c0043fe` verifier inputs and schemas read as UTF-8 explicitly

### Cross-platform CI

`.github/workflows/ci.yml` run `34434986898`, conclusion `success`, **12 of 12 jobs pass**:
Ubuntu, macOS and Windows, each on Python 3.10, 3.11, 3.12 and 3.13.

An earlier run (`34434602489`, revision `b38f6e3`) passed Linux and macOS and **failed all
four Windows jobs** at the `Complete suite including release security gates` step, with
`1 failed, 69 passed`.

Root cause, established rather than assumed: `tests/test_release_security.py` read a JCS
fixture with `path.read_text()` and no encoding. Windows decodes text with the locale
encoding, cp1252, which mangled the non-ASCII bytes in `input/french.json` so the
canonical bytes no longer matched the expected vector. Of the six JCS input fixtures only
`french.json` contains raw non-ASCII, which is exactly why one test failed on Windows and
none on Linux or macOS. It was a test portability defect, not a canonicalization defect.

The same pattern appeared in shipped code and was a real defect: the standalone verifier
read record files and its schema with the locale encoding, so on Windows a valid record
containing raw non-ASCII would decode to mojibake and the signature check would return a
**false FAIL**, contradicting the cross-implementation verification claim. Verified against
the original failing case with a non-UTF-8 default encoding:

```
before: FAIL: 'ascii' codec can't decode byte 0xc3 in position 354
after:  PASS valid under pinned key
```

Both fixes specify UTF-8 explicitly and change no behaviour on Linux or macOS, where UTF-8
is already the default. `JsonlSink` already specified UTF-8 and was unaffected.

### Release packages in fresh environments

Built from `c0043fe` and installed into four clean environments:

| Artifact | SHA-256 |
|---|---|
| `corrlog_core-0.2.2-py3-none-any.whl` | `a7806502e7f9e10f2dcbae6816bbe7f827c659a21f03c9b654ebdd0e2481f0ec` |
| `corrlog_inspect-0.1.3-py3-none-any.whl` | `5cec1bd1eeec6ea1f9a1161217b1c88b577c61daeee7e5a5ed077e76a5489274` |

- Installed-wheel suite, run from a test tree with no package source present: **70 passed**.
- Independent verifier environment containing `rfc8785`, `jsonschema` and `cryptography`
  only, with CorrLog absent: `find_spec("corrlog_core") is None`.
- Inspect installed without core: imports cleanly with no core present.
- Published `corrlog-core` 0.2.1 installed from PyPI for the legacy matrix.
- `pip check` reports no broken requirements in any of the four environments.

### Verifier accept/reject behaviour

Executed from the environment with no CorrLog installed, against records produced by the
installed 0.2.2 wheel:

| Case | Exit | Result |
|---|---|---|
| Raw UTF-8 record under a trusted key | 0 | PASS |
| Same record with `\uXXXX` escaping | 0 | PASS |
| Raw UTF-8 record under a non-UTF-8 default locale | 0 | PASS |
| Wrong trusted key | 1 | FAIL, untrusted signer |
| Tampered signed field | 1 | FAIL |
| Tampered metadata | 1 | FAIL |
| Tampered signature | 1 | FAIL |

### Legacy compatibility, measured

Seven representative record shapes were signed with the published `corrlog-core` 0.2.1
from PyPI and verified with the built 0.2.2 wheel and the standalone verifier. **Two still
verify, five do not.**

| Record content | 0.2.2 verdict |
|---|---|
| ASCII-only strings | PASS |
| Non-ASCII value | FAIL |
| Non-ASCII object key | FAIL |
| Non-integral float `0.1` | PASS |
| Integral float `56.0` | FAIL |
| Exponent float `1e16` | FAIL |
| Integer at or above 2^53 | FAIL |

This is wider than the Unicode-only framing in the supplied migration evidence. A
byte-level comparison over 20 shapes gave 11 identical and 9 differing. Disclosure to
users should cover all three classes: Unicode, number formats, and unsafe integers.

**What the break costs, measured with an independent implementation.** Each legacy record
was checked against `rfc8785` plus `cryptography`, with no CorrLog code involved, to ask
whether a conforming third party could ever have verified it under 0.2.1. The two shapes
that still verify under 0.2.2 (ASCII-only, non-integral float) are exactly the two an
independent implementation could verify. All five that break were already unverifiable
outside 0.2.1, because 0.2.1's non-conformant canonicalization is what produced them. On
this evidence the compatibility break removes no working capability.

Caveats to carry: the conclusion rests on seven representative shapes rather than an
exhaustive sweep, and 0.2.2 enforces the record schema at verification time, so a legacy
record violating the tightened schema could in principle be rejected even with conformant
signature bytes.

## Fixes and review of the supplied patch

- Accepted the Unicode escaping/UTF-16 ordering corrections. Rejected silent rounding
  of unsafe Python integers; they now raise and must be represented as strings.
- Replaced the standalone verifier's duplicated canonicalization algorithm with the
  independent `rfc8785` library. It has no CorrLog imports. Both verifiers enforce
  the same published schema and reject inconsistent agent/signature keys.
- Extended chain validation beyond the patch: unique IDs, predecessor ID and digest,
  rooted genesis, safe malformed-input rejection, and optional trusted checkpoints
  binding length, genesis and head. A checkpoint requires a pinned key.
- Added schema validation at construction and verification. Expanded the schema to
  explicitly cover the already-public action/correction/uncertainty family. This is
  a format-profile clarification, not evidence that the old correction-only schema
  was adequate. Installed JSON Schema format dependencies are required and declared.
- Retained the sk_ prefix fix, missing-core enabled() fix and subject_ref preservation.
  The authoritative subject_ref now overwrites conflicting caller metadata.
- MemorySink copies inputs/outputs and rejects duplicate correctionIds. Added a
  persistent transactional ReplayGuard for explicit trusted consumer admission.
- Made trusted-key APIs, CLI key requirements, checkpoint trust establishment and
  the optional replay design explicit. Kept unpinned verify() only as a documented
  signature-consistency API for compatibility.
- Scoped JSONL to untrusted transport. Removed broader ledger claims from README,
  SPEC, SECURITY, Inspect docs, examples and launch/outreach copy. Updated package
  candidates to core 0.2.2 / Inspect 0.1.3, with Inspect's core extra requiring 0.2.2.

## Evidence

Evidence is in `validation/evidence/`. These are local results on macOS arm64,
Python 3.12. The full Ubuntu/Windows/macOS × Python 3.10–3.13 CI matrix has been
updated to run the new tests. That matrix has since been executed on the draft pull
request and passes 12 of 12 jobs; see "Final revision and platform results" above.

| Verification | Result | Evidence |
|---|---|---|
| Full existing suite plus new gates | 70 passed | security-tests.log |
| Fresh installed wheels, tests copied outside source; no core source in test tree | 70 passed | installed-tests.log |
| Official JCS project fixtures | 6/6 | test_jcs_official_and_differential; core matrix C2-05 |
| RFC 8785 Appendix B numeric samples | 26/26 including rejection of NaN/infinity | test_rfc8785_appendix_b |
| Independent canonicalization fuzz | 9,994 finite cases matched byte-for-byte from 10,000 seeded binary64 draws | test_jcs_official_and_differential; seed 8785 |
| Historical core matrix | 78/91 PASS; 13 remaining historical FAIL labels classified below | matrix.json; core-matrix.log |
| Real Inspect CLI matrix | 9/10; remaining check demands a nonexistent receipt-file chain | matrix_inspect.json; inspect-matrix.log |
| Independent offline gate | PASS with socket creation disabled and CorrLog absent | offline.log |
| Clean install / dependency resolution | core+Inspect, oracle-only, Inspect without core and published 0.2.1 installed; pip check passed for core+Inspect and no-core | requirements-*.txt; reproduction evidence |
| Migration | ASCII examples remain valid; four non-ASCII legacy cases rejected; all six newly signed cases verify | migration.log |
| Deterministic fixtures | byte-for-byte unchanged on regeneration | test_vectors_are_deterministic |

The JCS fixtures came from the handover, attributed there to cyberphone's
json-canonicalization repository at commit 19d51d7; their license is retained.
Numeric samples were checked against [RFC 8785 Appendix B](https://www.rfc-editor.org/rfc/rfc8785.html#appendix-B).
Fuzz comparison uses Trail of Bits `rfc8785==0.1.4`. Finite randomized testing is
strong regression evidence, not exhaustive proof over all binary64 values.

The Inspect CLI initially failed because this session could not write Inspect's
standard macOS application-data directory. Additional access was not granted.
The successful run uses `validation/inspect-path-shim.py` to redirect only
platformdirs data/cache paths into the workspace. It still executes the actual
installed `inspect eval` CLI, mock model, scorers, discovery entry point, signing
hook, JSONL sink and separate verifier processes. It is not evidence of an
unmodified macOS deployment or a real paid model-provider integration. No live
provider or client data was used.

A second complete run through `validation/run_current.py` reproduced the same
70/70, 78/91 and 9/10 results and passed all four environment dependency checks
and the independent offline gate. Its logs and exit codes are retained under
`validation/evidence/reproduced/`.

The installed-wheel test run initially emitted a harmless pytest cache-path warning;
no tests failed. The reproduction runner disables pytest's cache provider.

## Proven claims and boundaries

| Claim | Proven? | Exact evidence | Limitation / safe wording |
|---|---|---|---|
| Open source | Yes for reviewed source | Repository contains MIT LICENSE and readable implementation | Publication of these changes is pending; do not imply PyPI already contains them |
| Signed correction records | Yes | existing round-trip tests; Inspect C10-02–05 | “Signed records of disclosed corrections” |
| Correction history | Conditional | chain attack tests, predecessor ID/digest checks | “Verify a supplied linear correction chain”; complete only relative to a trusted checkpoint |
| Provenance | Assertion only | signed principal/agent/source fields; tamper matrix | “Records who the signer claims acted and the cited source”; no independent truth check |
| Per-record tamper detection | Yes | tamper matrix, independent offline gate | Changes to signed canonical content are detected under a trusted key; whitespace/member order are not signed distinctions |
| Ledger tamper evidence | No; withdrawn | explicit JSONL mutation tests, historical C5 and C10-06 | “JSONL receipt storage”; never “tamper-evident ledger” |
| Replay protection | Conditional and opt-in | persistent concurrent ReplayGuard test; primary-key transaction | “Unique correction-ID admission using protected shared state”; not automatic for sinks/Inspect, not semantic or exactly-once processing |
| Independent offline verification | Yes | oracle-only environment; offline gate; real Inspect C10-09 | Requires independently provisioned trusted key and verifier dependencies; schema is shared specification data |
| Trusted-key verification | Yes | wrong-key tests and offline attacker rejection | “Verification against an independently trusted public key”; key-to-operator/agent authorization remains external |
| Inspect integration | Yes, tested scope | 9 passing real CLI checks with path shim | Signed receipts on failed samples; no retained predecessor, receipt chain or guaranteed delivery |
| Schema-enforced records | Yes | three constructor types; signed invalid schema tests; packaged schema checks | Revised record-family schema; unknown extensions allowed and signed; input size limits external |
| Production readiness | No blanket claim | operational boundaries below | “Unreleased candidate with local validation evidence” |

## Every remaining historical matrix label

The original harness contains hard-coded False verdicts and assumptions that
invalid constructors always succeed. Minimal adaptations allow it to complete
without changing its ledger expectations. It is retained as an audit trail, not
presented as an all-green acceptance suite.

| ID | Current disposition |
|---|---|
| C2-02 | Unpinned signature consistency deliberately accepts any valid signer. Trusted API and CLI pinning reject attacker keys; README now leads with trusted verification. |
| C4-09 | Timestamps are signed claims; chronological plausibility/clock trust is not enforced. Declared limitation, not a cryptographic completeness claim. |
| C4-10 | Contradictory sibling corrections may individually verify; they fail a linear-chain check. Semantic contradiction resolution is not implemented. |
| C5-02 | JSONL line deletion undetected per record; ledger claim withdrawn. Trusted checkpoint chain test detects deletion for a supplied linear chain. |
| C5-03 | JSONL line reordering undetected per record; ledger claim withdrawn. Chain order check rejects reordered linked records. |
| C5-04 | JSONL truncation undetected per record; checkpoint gate rejects a truncated expected chain. No automatic file checkpointing. |
| C5-05 | Damaged lines counted, not fatal; permissive transport behavior documented. Readers are not security verification. |
| C5-06 | JSONL file is rewritable and not fsync-backed; no append-only enforcement or power-loss promise. |
| C6-02 | JSONL permits replay. Consumers must opt into ReplayGuard; tested persistent admission is separate. |
| C6-04 | JSONL permits duplicate IDs; get() returns first match. Never use it as trusted admission. ReplayGuard rejects same-ID replacement and replay. |
| C7-12 | Wholly malformed JSONL reads as empty with damaged_lines > 0. Transport scope, not valid-history evidence. |
| C9-05 | kid is signed metadata, not an authorization/key-resolution service. Trusted key is supplied explicitly; documented in SPEC. |
| C9-06 | Historical hard-coded FAIL despite observed verify=False for key inconsistency. Fixed in both verifiers. |
| C10-06 | Inspect receipt file is not a chain; claim withdrawn. Superseded action is not retained. |

## Unresolved blockers and limitations, ranked

1. **Release gate (closed):** run the updated cross-platform/Python CI before publication.
   Done: run `34434986898` passes 12 of 12 jobs on Ubuntu, macOS and Windows across Python
   3.10 to 3.13. The first attempt failed the Windows legs and exposed a locale-encoding
   defect, fixed in `f92e510` and `c0043fe`. See "Final revision and platform results".
2. **Release gate:** explicitly approve the release and disclose 0.2.1 compatibility
   break. Legacy non-ASCII signatures cannot be retroactively made RFC-conformant.
   Preserve archives; re-signing creates a new assertion. No silent fallback exists.
   Disclosure wording is drafted in `RELEASE_NOTES-0.2.2.md`. Two points to carry into any
   disclosure: the break also covers number formats and unsafe integers, not Unicode alone
   (measured: two of seven representative 0.2.1 records still verify), and verification of
   legacy records requires retaining the trusted **public** keys.
3. **High if ledger/complete-history assurance is required:** JSONL is not a
   tamper-evident ledger. That product capability is excluded from this release scope.
4. **High if automatic consumer protection is assumed:** replay state, key
   authorization, checkpoint freshness, revocation, resource limits and side-effect
   transaction design must be provided by the deployment. Do not operate on unpinned
   verify() or trust a checkpoint/key supplied with untrusted evidence.
5. **High if lossless Inspect delivery is required:** signing/write failures are
   logged and do not fail evals; predecessor actions are not retained; no fsync.
   Deployment must monitor/reconcile delivery or use another storage architecture.
6. **Limitations:** no proof of truth, undisclosed events, trusted timestamps,
   semantic deduplication, distributed replay protection, witness consistency,
   external anchoring, exactly-once processing, or regulatory compliance. Auxiliary
   content hashes of non-dictionary inputs retain Python string serialization;
   do not claim language-neutral reproduction of those auxiliary hashes.

No known failing new release security gate remains on the tested platform. The
remaining high-impact needs above are outside the explicitly selected per-record
scope; they prohibit broad production-assurance claims, not a claim that the tests
proved a general-purpose ledger secure.

## Exact website wording

Use only when clearly describing this reviewed candidate or after the corresponding
release is published and deployed:

> CorrLog creates signed records of agent actions, corrections and uncertainty.
> Individual records can be verified offline against an independently trusted public
> key to detect changes to their signed content. Verification does not prove that
> a statement is true or that every event has been recorded. JSONL receipt files
> are not tamper-evident ledgers.

Optional Inspect line:

> The Inspect integration emits operator-signed receipts for failed evaluation
> samples. These are individual receipts, not a hash-chained or complete audit log.

Before publication, label the above **“remediation candidate under review”** and
avoid implying the older installed/published versions provide the corrected behavior.

## Exact claims to avoid

- “Tamper-evident ledger” / “immutable audit trail”.
- “Hash-chained Inspect receipts” / “deletion or truncation cannot go undetected”.
- “Independent verification establishes trust without a pre-established key”.
- “Automatically prevents replay” / “exactly-once corrections”.
- “Proves what the agent did” / “proves the correction is true”.
- “Complete correction history” without a trusted checkpoint and bounded scope.
- “Guaranteed durable delivery” / “production-grade assurance” / “production ready”.
- “Certifies compliance” or “0.2.2 is already available on PyPI”.

## Reproduction

Release packages were built and tested in fresh environments from revision `c0043fe`:

```sh
python -m build --outdir wheels .
python -m build --outdir wheels ./corrlog_inspect
```

Install both wheels into a clean environment, copy `tests/` and `verifier/` outside the
source tree, and run `python -m pytest tests -q`. Verifier behaviour is checked with
`verifier/standalone.py --key <trusted-public-key.json> <record.json>`, which should be run
from an environment that has `rfc8785`, `jsonschema` and `cryptography` but no CorrLog.

From a checkout of the review branch, using Python 3.12:

```sh
python validation/run_current.py --work /absolute/path/to/new-empty-validation-directory
```

On a restricted macOS host, add `--redirect-inspect-data`. The runner creates fresh
venvs, builds/install wheels, verifies dependencies, runs the full installed suite,
core and real Inspect matrices, migration checks, and a network-disabled independent
verification gate. It writes exit codes and outputs under the new directory. The
historical core matrix's nonzero exit is recorded; inspect the classified failures.
The historical `harness/run_all.sh` is preserved for original handover reproduction,
not for validating current source (it resets its separate clone to the old commit).
