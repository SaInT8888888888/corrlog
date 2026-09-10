# CorrLog release-readiness review — 10 September 2026

## Decision

**0.2.2 is a reviewed remediation candidate, not approved for publication.** Local
verification supports releasing the narrowly scoped signed-record implementation
once the updated cross-platform CI passes and the maintainer accepts/discloses the
legacy-signature compatibility change. **Unqualified production readiness: no.**
A tamper-evident ledger, automatic replay prevention, guaranteed delivery and
complete audit history are not implemented. No release, tag or remote push was made.

This review starts from master `b85910dcbd9091cbb80583ca858e4286ecbc3815`, matching
the handover exactly, on branch `remediation/release-readiness`. The supplied patch
was inspected and checked against the base before application; it was then revised.
The authoring machine's live checkout was not available. This repository reproduces
its supplied patch, not any changes made there after the handover.

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
updated to run the new tests but has not been executed remotely in this task.

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

1. **Release gate:** run the updated cross-platform/Python CI before publication.
   Local Python 3.12 results do not establish every supported platform's behavior.
2. **Release gate:** explicitly approve the release and disclose 0.2.1 compatibility
   break. Legacy non-ASCII signatures cannot be retroactively made RFC-conformant.
   Preserve archives; re-signing creates a new assertion. No silent fallback exists.
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
