# CorrLog release-readiness review — 10 September 2026

## Decision

**0.2.2 remains a reviewed remediation candidate, not approved for publication.**

Status of the release gates:

1. **Cross-platform CI — closed.** Passes 12 of 12 jobs on Ubuntu, macOS and Windows across
   Python 3.10 to 3.13, on the revision containing the F-01 numeric fix (`3c2d6ed`, run
   `34437939325`).
2. **Packages built and tested in fresh environments — closed.** Wheels built from the tested
   revision, installed into clean environments, suite green, `pip check` clean, verifier
   accept/reject confirmed.
3. **Maintainer approval and disclosure of the compatibility change — open.** This is a
   decision, not a test. The disclosure wording is drafted in `RELEASE_NOTES-0.2.2.md` and
   was corrected after retest finding F-02 (see below).

A final independent retest of the previous revision found a high-severity numeric
round-trip defect (F-01) and a disproven compatibility claim (F-02). Both are fixed in this
revision and the claim has been withdrawn. The earlier passing results were genuine but did
not exercise the round-trip case, which is why the finding stood as a blocker.

**Unqualified production readiness: no.** A tamper-evident ledger, automatic replay
prevention, guaranteed delivery, complete disclosure of every event, truthfulness and
complete audit history are not implemented. No merge, tag or PyPI publication has been
performed. A branch push and a draft pull request were made so the Windows and macOS CI
legs could run.

This review starts from master `b85910dcbd9091cbb80583ca858e4286ecbc3815`, matching
the handover exactly, on branch `remediation/release-readiness`. The supplied patch
was inspected and checked against the base before application; it was then revised.
The authoring machine's live checkout was not available to the original review. This
repository reproduces its supplied patch, not any changes made there after the handover.
See "Final revision and platform results" below for what has since been added on top.

## Final revision and platform results

Tested code revision: `3c2d6ed`, the revision the CI matrix and the fresh-environment package
tests below were run against, on the branch `remediation/release-readiness` (draft pull
request against `master`, `https://github.com/SaInT8888888888/corrlog/pull/6`).
Documentation-only commits may sit above it; they change no packaged file, so the wheel
hashes recorded below remain the tested artifacts. History on top of the base:

- `505832c` code and tests: verification, schema, trust and replay hardening
- `cfb4ca5` evidence and the original release-readiness report
- `b38f6e3` `RELEASE_NOTES-0.2.2.md`
- `f92e510` tests read fixtures as UTF-8 explicitly
- `c0043fe` verifier inputs and schemas read as UTF-8 explicitly
- `3c2d6ed` numeric domain consistency in core and verifier (F-01), plus
  `tests/test_numeric_roundtrip.py`

### Cross-platform CI

`.github/workflows/ci.yml` run `34437939325` on revision `3c2d6ed` (the numeric fix):
conclusion `success`, **12 of 12 jobs pass** — Ubuntu, macOS and Windows, each on Python
3.10, 3.11, 3.12 and 3.13. Run `34434986898` on `c0043fe` passed the same matrix before the
numeric fix.

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
| `corrlog_core-0.2.2-py3-none-any.whl` | `d9a1330eb4b409077fdfcdb2cb228a348b2069adfff9bf8cb37c27c086e378eb` |
| `corrlog_inspect-0.1.3-py3-none-any.whl` | `20f59fe08100d3200495522e44b9e7acba714d78e52081653bfb93b5c13bbe65` |

- Installed-wheel suite, run from a test tree with no package source present: **131 passed**.
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

**What the break costs.** Each legacy record was checked three ways: 0.2.1's own verifier,
0.2.2, and an independent native JavaScript canonicalizer with Node's Ed25519 primitive
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

0.2.2 agrees with the independent implementation on all seven shapes. This is the result for
these seven fixtures, not a general compatibility guarantee: users of 0.2.1 can still face
verification changes, including changes caused by schema enforcement.

**Correction to an earlier claim in this report.** A previous revision of this report, and
of the release notes, stated that the break "removes no capability that was actually
working" and that every affected record was already unverifiable independently. Retest
finding F-02 disproved that, and the claim has been withdrawn:

- The claim rested on the Python `rfc8785` package rejecting integers at or above `2**53`.
  That is a restriction of one Python implementation, not an RFC 8785 requirement. `2**53`
  is exactly representable as binary64, and the JavaScript checker verifies a
  published-0.2.1 record containing it. The earlier text treated an implementation
  limitation as a specification fact.
- Separately, 0.2.1's own in-library verification accepted all seven shapes. A record that
  verified under 0.2.1's verifier can fail under 0.2.2, which is a real compatibility break
  irrespective of which side was conformant.

After the F-01 numeric fix, the counterexample is resolved at the source rather than by
softening the wording: `2**53` now verifies under both 0.2.2 implementations, and 0.2.2
agrees with the independent JavaScript checker on every shape tested.

Caveats to carry: seven representative shapes rather than an exhaustive sweep, and 0.2.2
enforces the record schema at verification time, so a legacy record violating the tightened
schema could be rejected even with conformant signature bytes.

## Final retest round and remediation (2026-09-10)

An independent retest of revision `3c9e27f` raised two findings. Both are accepted and
addressed in this revision.

### F-01: an accepted signed record failed canonical JSON round-trip (high)

A record built with `metadata={"value": 1e16}` verified, but the same record re-parsed from
its own canonical wire form did not, and the standalone verifier rejected the canonical file
while accepting the ordinary one.

Reproduced on the installed wheel: `test_numeric_roundtrip.py` equivalents failed for `1e16`
and `1e20`, and the report's CLI commands reproduced `1e+16-canonical.json` exiting 1 while
`1e+16-normal.json` exited 0.

Root cause: the numeric domain was applied inconsistently. Construction accepted a float
`1e16`, canonicalization wrote `10000000000000000`, and Python re-parses that literal as an
`int`. The old integer rule rejected any Python integer with `|n| >= 2**53`, so the library
invalidated a record it had accepted and signed. The standalone verifier failed from the
other side, because the `rfc8785` Python package rejects large `int` values while accepting
the equivalent `float`.

Fix, one policy applied at construction, canonicalization, parsing and verification: a JSON
number is accepted when it is exactly representable as an IEEE 754 binary64 value. Exactly
representable integers, including `2**53` and `10**16`, are normalised to that double and
serialize per ES6 rules. Integers that would need rounding, such as `2**53 + 1`, are
rejected rather than rounded. The verifier normalises parsed integers into the same domain
before delegating to `rfc8785`, so independence is preserved and both implementations share
one domain.

Verification after the fix:

- All ten of the report's CLI cases pass, including both canonical files that previously
  failed.
- Round-trip holds for 15 values through canonical JSON, ordinary JSON and the CLI.
- Wire-spelling pairs (`1e+16` and `10000000000000000`, `56.0` and `56`, and six more) are
  byte-identical and verify with the same signature.
- Inexact integers are rejected at canonicalization and at construction.
- Canonical output is byte-identical to the independent JavaScript canonicalizer for every
  spelling tested.

### F-02: the compatibility disclosure overstated what is preserved (accepted)

The release notes claimed the break "removes no capability that was actually working" and
that affected records were already unverifiable independently. That is withdrawn and
replaced. The claim rested on a Python package's integer-domain restriction being treated as
an RFC 8785 requirement, and it ignored that 0.2.1's own verification was working behaviour.
Details and the corrected wording are in the legacy section above and in
`RELEASE_NOTES-0.2.2.md`.

### Regression coverage added

`tests/test_numeric_roundtrip.py`, 61 cases: canonical and ordinary JSON round-trips across
15 values, eight wire-spelling pairs asserted to canonicalize identically, the CLI path for
both file forms, inexact-integer rejection at both entry points, and agreement between
exactly representable integers and their double spellings. The existing suite's expectation
that `2**53` must be rejected was updated to the corrected policy, with `2**53 + 1` and
`2**64 + 1` retaining rejection.

Suite after the change: **131 passed** (was 70).

### F-01 second round: the first fix was itself incomplete

A further retest of `a683162` showed F-01 partially fixed: signed round-trips of the finite
RFC 8785 Appendix B samples gave 21 of 24, and 687 of 99,958 canonicalization round-trip
draws failed.

Reproduced exactly, failing on the three samples named: bits `4430000000000000`
(`float(2**68)`), `444b1ae4d6e2ef4e` and `444b1ae4d6e2ef4f`.

Cause of the incomplete fix: the corrected numeric rule required
`int(float(n)) == n` for a parsed integer, which demands that the integer equal the exact
mathematical value of its binary64. RFC 8785 instead mandates the SHORTEST decimal spelling
that round-trips, and for `float(2**68)` that spelling is `295147905179352830000` while the
double's exact value is `295147905179352825856`. The check therefore rejected a spelling the
RFC requires. The two conditions being conflated are "the integer is not the double's exact
value" (normal and correct) and "the value would change on the wire" (the actual rejection
criterion).

Corrected rule, applied in `corrlog_core._jcs_integer` and in the verifier's
`_to_double_domain`: admit a parsed integer when it is either the double's exact value or
the canonical shortest-round-trip spelling of that double. Reject only values that would
change, so `2**53 + 1` and `10**20 + 1` are still refused and nothing is silently rounded.
The verifier obtains the spelling from `rfc8785` itself, preserving its independence.

Verified after the correction:

| Check | Before | After |
|---|---|---|
| Their `test_signed_rfc_roundtrip.py`, installed wheel | 3 failed, 21 passed | **24 passed** |
| Signed round-trip of the finite Appendix B samples | 21/24 | **24/24** |
| Their closure fuzz, seed 20260910, 100k draws | 687 failed of 99,958 | **0 failed of 99,958** |
| Their CLI fixtures (ten files, both forms) | 2 canonical files failed | **all exit 0** |
| Suite | 131 passed | **224 passed** |

Regression coverage added: `tests/test_appendix_b_roundtrip.py` (76 cases over every finite
Appendix B sample, including the canonical-file CLI path) and
`tests/test_chain_serialization.py` (chain and checkpoint survival after canonical and
ordinary serialization, tamper rejection, and the CLI chain plus checkpoint path), plus the
shortest-spelling cases in `tests/test_numeric_roundtrip.py`. The fuzz invariant
`canonical(parse(canonical(value))) == canonical(value)` is asserted in the suite and
re-checked over 100,000 draws.

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
