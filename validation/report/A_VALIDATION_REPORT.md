# CorrLog Validation Report

Date: 2026-09-10
Target: `/home/shane/corrlog-sdk` at HEAD `b85910d`, plus the published `corrlog-core 0.2.1` from PyPI
Method: adversarial, deterministic, automated. No LLM judged whether anything "looked correct".

---

## 1. Executive summary

CorrLog was tested against 10 claims with 101 automated tests, every one of them
executing real code and recording machine-checkable output. The tests are
deterministic: they sign, tamper, verify, and compare bytes. Nothing in this
report rests on a model reading a record and judging it plausible.

**Headline result before any fix: 57 of 91 core tests passed.** The failures were
not cosmetic. The most serious was that CorrLog's canonicalization was not
RFC 8785, which meant a conforming third party **could not verify any CorrLog
record containing non-ASCII text**, which is precisely the "independently
verifiable" property the project exists to sell. The project's own shipped
standalone verifier made the same wrong choice, so it agreed with the SDK and
could not detect the divergence: the same structural failure mode that
`SECURITY.md` had already documented for key substitution (an in-tree checker
validates the code, not the assumptions).

Six production defects were found, root-caused, fixed, and re-verified, plus one
set of false documentation claims that was withdrawn. The
matrix went from 57 to 72 of 91 passing with **zero regressions**. A genuinely
independent verifier, built on a third-party RFC 8785 implementation and sharing
no code with CorrLog, now verifies real records produced by a real Inspect run.

**Result after fixes: 81 of 101 tests pass. 20 remain open, none of them
fixable by a small edit.** They are not scattered bugs; they cluster into six
themes, and two of them are architectural (the JSONL ledger is not tamper
evident, and the Inspect receipts file is not a hash chain despite documentation
that said it was). The open findings are enumerated in section 5.

One of the twenty open findings, C10-06, is a *documentation claim that was
never true*: the Inspect receipts file was described as "hash-chained by file
order". The false claim has been withdrawn and replaced with an accurate
statement of the limitation in all three files that carried it (section 4, F5).
The underlying capability gap remains open.

**Bottom line: the core cryptographic primitive is now sound and genuinely
third-party verifiable. The ledger and durability layer is not. CorrLog is not
ready to claim tamper detection or production use, and the recommendation in
deliverable D is calibrated accordingly.**

---

## 2. What "independently verifiable" actually means here, proven

This claim deserved to be attacked with the most force, because it is the
product's central promise. It was tested by writing a second verifier
(`harness/independent_verifier.py`) that:

- shares no code with `corrlog_core` or `verifier/standalone.py`;
- delegates all canonicalization to `rfc8785` (Trail of Bits), a third-party
  implementation written independently of CorrLog;
- uses only stdlib, `cryptography` (the raw Ed25519 primitive), and `rfc8785`;
- runs offline, with no CorrLog instance, service, network call, or storage in
  the loop;
- supports pinning trust to a known public key.

**Result: PASS, with one hard precondition.**

- Records produced by the fixed build, including receipts written by a real
  `inspect eval` run, verify under the pinned key in this third-party verifier
  (evidence: `matrix_inspect.json`, test C10-09).
- Tampering with a single field makes it reject the record (C10-05).
- A record was copied to a separate clean directory and verified there by a
  separate process with a separately derived public key (C10-09).

**The precondition.** Nothing inside a record establishes *which key should be
trusted*. A verification that does not pin a key accepts a record signed by any
key embedded in that record, so an attacker can forge a complete, internally
consistent record with their own key and it will "verify". CorrLog documents
this in `SECURITY.md`, but its README quick start uses the unpinned form
(`verify(c1)`) as the primary example, so the hazard is the default. Independent
verifiability is real, but it is only a security property once the verifier
pins the key. CorrLog does not supply, and cannot supply, the key distribution
step. That is inherent to the design, not a defect, but it must be stated
wherever "independently verifiable" is claimed.

**A precondition that is now fixed.** The published `corrlog-core 0.2.1`
produced records that a conforming third-party verifier rejects whenever the
record contains non-ASCII text. That is demonstrated in
`harness/migration_impact.py` and `mig_oracle.py`: identical records, verified
"True" by 0.2.1 itself, rejected by the oracle. So before today, "independently
verifiable" was **false in practice for any non-ASCII content**, and the claim
survived because the in-tree verifier shared the SDK's wrong assumption.

---

## 3. Scope, method, and what the numbers are

| Suite | What it is | Tests |
|-------|------------|-------|
| Core matrix | Claims 1 to 9, deterministic, in isolated venvs | 91 |
| Inspect E2E | Claim 10, driven through the real `inspect eval` CLI | 10 |
| JCS conformance | Official RFC 8785 test vectors plus a third-party oracle | 6 vectors + 5,756 fuzz cases |
| Migration impact | Records signed by published 0.2.1, verified by the fixed build and by the oracle | 6 cases, both directions |

Environments (each a separate venv, so no test can pass by accident because
another test's dependency happened to be importable):

- `cleanroom/env-clean`: published `corrlog-core 0.2.1` from PyPI, nothing else.
- `env-fixed`: a wheel built from the fixed source tree.
- `env-oracle`: `rfc8785` plus `cryptography` only, no CorrLog code.
- `env-inspect`: `inspect-ai` 0.3.263 plus `corrlog-inspect` and its core extra.
- `env-nocore`: `inspect-ai` plus `corrlog-inspect` WITHOUT the core extra.

Totals: **101 tests, 81 PASS, 20 FAIL** in the final state. Before the fixes,
the same 91 core tests were 57 PASS and 34 FAIL.

---

## 4. Defects found, root-caused, fixed, and re-verified

Each entry follows the required process: failing test, root cause, smallest fix,
implementation, full re-run.

### F1 (critical): canonicalization was not RFC 8785

- **Failing tests:** C8-01 to C8-08, C2-04, C2-05, C7-01 to C7-08. Officially
  1 of 6 JCS conformance vectors passed and 5 of 13 oracle comparisons matched.
- **Root cause:** `canonical_json` used `json.dumps(..., ensure_ascii=True,
  sort_keys=True)`. That escapes every non-ASCII character as `\uXXXX` instead
  of emitting raw UTF-8, uses Python's float repr instead of ES6
  `Number::toString` (`56.0` instead of `56`, `1e+16` instead of
  `10000000000000000`, `1e-07` instead of `1e-7`), escapes U+007F, and sorts
  keys by code point instead of UTF-16 code unit. `predecessor.digest` and every
  signature were therefore computed over bytes no conforming implementation
  reproduces. The shipped `verifier/standalone.py` made the same
  `ensure_ascii=True` choice, so it could not detect the divergence.
- **Smallest fix:** implement RFC 8785 directly (string escaping per 3.2.2.2,
  ES6 number serialization per 3.2.2.3, recursive key sort by UTF-16 code unit
  per 3.2.3, hard error on lone surrogates per 3.2.2.2) in `corrlog_core` and in
  `verifier/standalone.py`.
- **Verification:** 6 of 6 official vectors pass; 5,756 of 5,756 fuzz cases are
  byte-identical to the third-party oracle; the full project suite passes.
- **Migration impact, precisely bounded:** ASCII-only records are fully
  backward compatible. Records containing non-ASCII text that were signed by
  0.2.1 stop verifying under a conforming implementation, but they never
  verified under one: the oracle rejects them too. There is no way to make a
  record both JCS-conformant and identical to the old bytes, because the old
  bytes were not JCS. The fix creates third-party verifiability for these
  records rather than removing it.

### F2 (high): truncated and orphaned chains verified

- **Failing tests:** C4-04 to C4-06.
- **Root cause:** `verify_chain` skipped the first record with `if i == 0:
  continue`, so a chain suffix, an orphaned correction, and even an empty list
  all returned True.
- **Smallest fix:** reject an empty list, and reject a first record that carries
  a `supersedes` pointer (a chain presented for verification must start at a
  root). Same fix applied to `verifier/standalone.py`.
- **Verification:** all three cases now fail as they should.

### F3 (high): `verify()` raised instead of returning False on malformed input

- **Failing tests:** C7-01 to C7-05.
- **Root cause:** no type guarding before `record.get("signature").get("alg")`.
  A non-dict record or a non-dict `signature` raised `AttributeError`.
- **Smallest fix:** guard for a dict record, a dict signature, and the expected
  algorithm, returning False. The standalone verifier already had equivalent
  guards.
- **Verification:** malformed inputs now return False with no exceptions.

### F4 (medium): `load_private_key` could not parse one of its documented prefixes

- **Failing test:** C9-08.
- **Root cause:** the prefix handling only stripped `ed25519:` and a generic
  3-character prefix; the documented `sk_` form fell through to the generic
  branch and produced invalid key bytes.
- **Smallest fix:** handle `sk_` explicitly.
- **Verification:** all documented key formats load and round-trip.

### F5 (high): documented behaviour that was not true, now corrected

Two claims were contradicted by the tests. Both were resolved by making the
documentation state the truth; neither could be made true by a small code edit,
and the underlying capability gaps remain open (see section 5, theme A).

- **Failing test:** C10-06, plus the pre-existing claim text in
  `corrlog_inspect/hooks.py`, `corrlog_inspect/README.md`, and
  `corrlog_inspect/_corrlog.py`.
- **Claim:** receipts are "hash-chained by file order".
- **Reality:** they are not. Each receipt carries a `supersedes` pointer to the
  action record it corrects, but `CorrlogSigner.sign` discards that action
  record, so the pointer resolves to nothing on disk. `verify_chain` over the
  receipts file returns False, and the file has no order binding at all, so
  deleting or reordering receipt lines is undetectable from the file.
- **Action taken:** the false claims were withdrawn and replaced with an
  explicit, accurate statement of the limitation in all three files.

### F6 (medium): Inspect integration silently inert without the optional dependency

- **Failing test:** C10-07, C10-08 (both new).
- **Root cause:** `enabled()` returned True whenever a key and a path were set,
  regardless of whether `corrlog_core` could be imported. With `corrlog-inspect`
  installed without its `core` extra, the hook reported itself enabled, produced
  zero receipts, and logged a confusing traceback per sample.
- **Smallest fix:** add `_core_available()`, have `enabled()` require it, emit
  one actionable error naming the install command, and guard signer and sink
  construction.
- **Verification:** `enabled()` now returns False, the eval completes with zero
  tracebacks, and exactly one actionable message is logged.

### F7 (medium): the receipt dropped the field identifying what was corrected

- **Failing test:** C10-03.
- **Root cause:** `_corrlog.build_correction` computes `subject_ref` (the sample
  pointer) and `CorrlogSigner.sign` uses it as `action_target` on the internal
  action record, which is then superseded and discarded. The signed receipt
  returned to the caller therefore contained no `subject_ref` field, contrary to
  the module docstring's promise that the receipt keeps "who" and "what"
  distinct.
- **Smallest fix:** carry `subject_ref` into the metadata of the receipt.
- **Verification:** the receipt now contains a `subject_ref` that exactly equals
  `inspect:<eval_id>/<sample_id>` as recorded in its own metadata.

---

## 5. Open findings (20)

None of these can be closed by a small edit. They are grouped by theme, with
the tests that evidence each.

### Theme A: the ledger is not tamper evident (6 tests)

- C5-02 (delete a line), C5-03 (reorder lines), C5-04 (truncate the tail),
  C5-05 (corrupt a line), C5-06 (structural append-only), C10-06 (Inspect
  receipts file).
- Deleting, reordering, or truncating JSONL lines leaves a file whose remaining
  records all verify individually. `damaged_lines` is the only signal for a
  corrupt line and is easy to miss. The file is a plain regular file, mode 0664,
  freely rewritable, with no fsync and no chaining. `JsonlSink` is
  "append-only by convention", not by mechanism.
- This is the gap between what CorrLog is documented to provide and what it
  provides. It is the single most important thing to close before any claim of
  tamper evidence.

### Theme B: duplicates and replay are undetected (3 tests)

- C6-01, C6-02, C6-04. The same record can be appended any number of times,
  and two different records can share one `correctionId`; `get(id)` then returns
  one of them silently. Nothing in the format carries a sequence number, and no
  sink consults the existing contents before appending.

### Theme C: the schema is not enforced (3 tests)

- C7-13, C7-14, C7-15. `SPEC.md` 6.1 requires schema validation before the
  signature check, but `verify()` never validates against the bundled schema.
  Records with an empty `reason` or empty `agent_id` verify successfully.
  `record()` output is missing the required `supersedes` property, and
  `unknown()` output is missing `supersedes`, `action`, and `reason`, so two of
  the three public constructors emit records that the project's own schema
  rejects. `verify()` and the schema therefore disagree about what a valid ACR
  record is.

### Theme D: the trust boundary is the default trap (2 tests)

- C2-02 (attacker key substitution accepted when unpinned), C9-06
  (`agent.publicKey` and `signature.publicKey` are independently settable; a
  record whose `agent.publicKey` is not the signing key is accepted unpinned).
- This is documented in `SECURITY.md`, but the README quick start demonstrates
  the unpinned form. A reader following the docs gets a check that any attacker
  can satisfy. Separately, `agent.publicKey` is pure decoration: it is never
  used or cross-checked.

### Theme E: provenance cross-checks are absent (5 tests)

- C4-08: `supersedes.receiptId` is never compared to the predecessor's
  `correctionId`. A correction can point at a totally unrelated id and
  `verify_chain` still returns True. Only the digest is checked.
- C4-09: a correction timestamped before the action it supersedes verifies.
- C4-10: two contradictory corrections superseding the same record are each
  individually valid; the format has no way to express or detect a conflict.
- C9-03: `timestamp` is not validated as RFC 3339 at all. The literal string
  `not-a-timestamp` is accepted at creation and the record verifies.
- C9-05: `signature.kid` is written and never resolved or checked against
  anything, so it cannot be used for key identification.

### Theme F: silent corruption reporting (1 test)

- C7-12: `JsonlSink.all()` over a wholly malformed file returns an empty list
  plus a `damaged_lines` counter. A caller who reads only the return value
  cannot distinguish "no records" from "every record is destroyed".

---

## 6. Claim by claim

| # | Claim | Verdict |
|---|-------|---------|
| 1 | Record creation works | **Proven** (7 of 7) |
| 2 | Independent verification from a clean environment | **Proven with a precondition** (see section 2). 6 of 7; the 1 failure is key substitution, which pinning closes and which the docs must lead with. |
| 3 | Alteration detection works | **Proven** (27 of 27). Every single-field mutation tested is caught. |
| 4 | Correction history is preserved and traceable | **Partially proven.** The digest chain is enforced and truncation is now rejected, but `receiptId` is not cross-checked, time ordering is unvalidated, and contradictions cannot be represented. |
| 5 | No silent overwrite or modification without detection | **Not proven.** This is the weakest area. Line deletion, reordering, and tail truncation are all undetected at the ledger level. |
| 6 | Duplicate and replay handled safely | **Not proven.** Nothing detects either. |
| 7 | Missing, malformed, or corrupt records fail clearly | **Partially proven.** Malformed input now returns False cleanly instead of raising, but corruption in a ledger is under-reported and the bundled schema is not enforced. |
| 8 | Deterministic signature and hash verification | **Proven** (7 of 7), and now anchored to the official RFC 8785 vectors and a third-party oracle. |
| 9 | Timestamps, identifiers, provenance, ownership behave as intended | **Partially proven.** Identifiers and ownership are carried correctly; timestamps are unvalidated, `kid` is decorative, and `agent.publicKey` is never cross-checked. |
| 10 | Inspect integration works end to end | **Proven for emission and verification** (9 of 10). Receipts are produced by real eval runs, verify under a pinned key in a third-party verifier, and survive being moved environments. The file is not a hash chain, and the superseded action record is discarded, so the chain claim was withdrawn. |

---

## 7. What must change before the public claims are safe

1. **Ledger integrity.** Either chain the ledger (each record commits to its
   predecessor's bytes) or stop describing the JSONL sink as tamper evident.
   Without this, "tamper-evident" is a claim about individual records that
   readers will reasonably apply to the whole file.
2. **Make pinning the documented default.** Every quick-start example that calls
   `verify(record)` unpinned should pin, and the unpinned form should carry an
   explicit warning at the call site, not only in `SECURITY.md`.
3. **Enforce the schema, or stop publishing one.** Either `verify()` validates
   against `schema/acr-v1.json` as `SPEC.md` 6.1 states, or both the spec and
   the schema need to change to match the constructors.
4. **Cross-check `receiptId` against the predecessor's `correctionId`** and
   validate timestamp format. Both are small and close five findings.
5. **Persist the superseded action record** in the Inspect integration, or drop
   `supersedes` from the receipts. A pointer that can never resolve is worse
   than no pointer, because it is easily read as evidence of a chain.

---

## 8. Limits of this validation

- Verification was tested against one third-party canonicalization oracle
  (`rfc8785`). That is a genuine independent implementation, but it is one
  implementation. Conformance to the official vectors reduces, but does not
  eliminate, the risk of a shared blind spot.
- The ledger tests use a local filesystem on Linux ext4 style semantics. Crash
  durability was not tested by killing a process mid-write; the partial trailing
  line case was tested by constructing the damaged file directly.
- Multi-process concurrent appends were not re-tested here; the project's CI
  claims and a prior stress test cover that, and this report does not.
- Windows and macOS were not exercised in this validation. The project's CI
  does exercise them.
- No attempt was made to attack the Ed25519 implementation or the `cryptography`
  library. The primitive is assumed sound.
- The Inspect integration was validated against `inspect-ai` 0.3.263 only.

---

## 9. Appendix: clean-room reproduction of this entire report

After the fixes were complete, the whole validation was re-run from scratch on
a bare workspace: a fresh `git clone` of the public repository, a fresh checkout
of `b85910d`, a fresh application of `report/corrlog-validation-fixes.patch`,
and five newly created virtual environments built from empty directories. No
state from any earlier run was reused.

Command:

```bash
CORRLOG_REPO=https://github.com/SaInT8888888888/corrlog.git \
VALIDATION_DIR=/home/shane/corrlog-validation \
WORK=/tmp/corrlog-cleanroom \
bash /home/shane/corrlog-validation/harness/run_all.sh
```

Result, exit code 0, every number identical to the ones reported above:

| Suite | Fresh clean-room result |
|---|---|
| Project tests, core | 35 passed |
| Project tests, Inspect adapter | 15 passed |
| Official JCS conformance vectors | 6 of 6 |
| Fuzz against the third-party oracle | 5,756 of 5,756 byte-identical |
| Core matrix, claims 1 to 9 | 72 PASS, 19 FAIL |
| Inspect end-to-end matrix, claim 10 | 9 PASS, 1 FAIL |
| Migration impact | ASCII compatible; non-ASCII from 0.2.1 not verifiable |
| Regressions introduced by the fixes | 0 |

The reproduction script also regenerated the evidence JSON files and
deliverable B from that fresh run, so the matrix you are reading was produced
by the clean-room run rather than by the exploratory one.
