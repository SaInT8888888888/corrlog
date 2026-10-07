# CORRLOG VALIDATION — INDEPENDENT SCORING

**Scorer:** LiefieTango (independent; did not design the protocol, run the tests, prepare fixtures, or modify anything)
**Date of scoring:** 2026-10-07
**Method:** read-only inspection of the two supplied archives plus independent recomputation. Nothing in either archive was modified, repaired or re-run. No CorrLog API was executed.

---

## 1. EVIDENCE PACKAGE VERIFICATION

### 1.1 Archive digests — both confirmed by my own computation

| Artefact | Supplied SHA-256 | Recomputed | Result |
|---|---|---|---|
| Executor submission (`corrlog-validation-2026-10.zip`) | `8575ff3f9c71ff95da7900ae3974c438e904441ac53132bef553836e48a07c2e` | identical | MATCH |
| Delivery addendum (`CORRLOG-VALIDATION-DELIVERY-ADDENDUM.zip`) | `90172bd43d43b26cf978b1be37872ecc244f14ac072b014deea3bad9f2832eb1` | identical | MATCH |

### 1.2 Frozen deliverable hashes — recomputed from the immutable archive

- `CORRLOG-VALIDATION-SUT-PIN.md` = `b6aefa37f2fbd0a94afa956f49585996cb0546a470e1c17eb35c15b5a6174cfc` — MATCH (as recorded in the pack manifest).
- `CORRLOG-VALIDATION-TEST-REGISTER-v1.md` = `90f1a26b5814a51c0135be485a03bce303b023f0f93cdecc9642b7ed61a936c0` — MATCH.
- Addendum's own `ADDENDUM-SHA256SUMS.txt` verified 6/6.
- `CORRLOG-VALIDATION-EXECUTION-REPORT.md` = `20cba8a2…` — MATCH (addendum's supersession claim for the stale manifest).
- The addendum's `FINAL-FILE-INVENTORY-SHA256.txt` is **exact** against the archive: 1343 entries, **0 hash mismatches, 0 size mismatches, no missing and no extra paths**; its header names the same archive digest.

### 1.3 Delivery addendum — inspected in full

Contents: `ADDENDUM-README.md`, `ADDENDUM-SHA256SUMS.txt`, `FINAL-FILE-INVENTORY-SHA256.txt`, `PACKAGING-ERRATA.md`, `T011-EVIDENCE-PRESERVATION-ERRATA.md`, `T011-RECONSTRUCTED-mutation.txt`, `T011-RECONSTRUCTED-agent-id.json`. It is a genuine supersession document: it leaves the stale artefacts unedited and states which digest supersedes which.

Two stale packaging artefacts are disclosed and superseded: `PACK-MANIFEST.md` (describes the 21:07 snapshot, before the B–G series and the use case ran) and the top-level `SHA256SUMS.txt` (written before the ledger was updated). The disclosure is accurate — I verified the stale top-level manifest does claim an earlier state.

### 1.4 T011 evidence-preservation erratum — reviewed and independently confirmed

The erratum states that the mutation helper reused two filenames for a second variant (`agent.publicKey`), overwriting the registered `agent.id` fixture on disk. I confirmed this independently:

- I reconstructed the registered `agent.id` mutation myself from the preserved pristine fixture (`agent.id := "agent://attacker"`, serialised as the pristine file is) and reproduced **`6df3c149…` exactly** — the hash the run ledger records for the registered run.
- I swept the whole pack: **no file carries the registered-run bytes** (`6df3c149…`, `ac911fab…` are absent everywhere). So the erratum's claim that the registered fixture bytes are not recoverable is correct, and the reconstruction in the addendum is the only representation of them.
- The addendum's two reconstructed files hash to exactly the ledger's recorded values (`6df3c149…`, `ac911fab…`), so the reconstruction is faithful.

### 1.5 Fixture-hash integrity across the whole register — measured, not sampled

Every fixture hash recorded in the run ledger was recomputed against the file it names:

- **132 fixture references checked → 130 resolve and match exactly. The only 2 that do not are T011's `mutated.json` and `mutation.txt`** — precisely the pair the erratum discloses.
- 1 apparent mismatch (`T054 run.txt`) was my resolver selecting `T055/cold/run.txt`; the named file `T054/clean-alt/run.txt` = `1ee24c37…` **matches** the ledger.
- The ledger holds 76 rows for 55 tests, i.e. re-runs and the superseded attempt-1 A-series rows are preserved rather than overwritten. The A series therefore appears **twice** in the ledger (attempt-1 `verifier exit=1` under a JWK anchor, then the corrected `exit=0`), with the explanation living in the report and OBS-03 rather than in the row itself.

### 1.6 Original vs reconstructed material — distinction is sound

Every artefact is original captured evidence except the two explicitly labelled `T011-RECONSTRUCTED-*` files in the addendum. No other reconstructed-after-execution material exists. Corrected re-runs (T044, T047, T050, T036, A-series attempt-1) are preserved as separate original artefacts and labelled, not substituted.

### 1.7 Integrity issues found (none of which prevent scoring)

1. **Shared cleanroom export path (material, and not disclosed).** 43 tests' captioned verifier commands read a copy under `cleanroom/export/`. That directory is a last-writer-wins scratch area: T011's captioned command names `cleanroom/export/mutated.json`, which **today contains the T013 mutation** (`metadata.model` → `"triage-v4-not-signed"`), not T011's. So for every test whose command names that path, the captioned command no longer identifies the bytes that were verified. The per-test fixtures under `evidence/<TEST>/` are unaffected and intact. This is a chain-of-custody weakness, not evidence of a wrong verdict.
2. **T011's registered-variant provenance is ambiguous** for that reason *plus* the documented overwrite — the preserved verifier output for T011 cannot be tied with certainty to the `agent.id` variant. The sibling `agent.publicKey` variant **is** separately preserved with its own verdict (`FAIL agent key mismatch`).
3. **Stale `mechanical outcome` fields** left in several READMEs after corrected re-runs (T047, T050 record `FAIL` while their corrected evidence and re-run notes sit underneath).
4. **Hash-description slip:** the report §1 gives "public key file SHA-256 `4bf83c53…`" while the pin §5 gives `1a1ef939…` for `harness/keys/TEST-signer.pub.json`. Both hashes are real files — `4bf83c53…` is `TEST-signer.trust.json`. One loose phrase describing two different files.

**Conclusion of section 1: the package is internally consistent and its digests, inventory and reconstruction claims all verify. Scoring can proceed.** The only chain-of-custody weakness is confined to T011 and to the shared `cleanroom/export/` copies.

---

## 2. SYSTEM UNDER TEST — CORRESPONDENCE CONFIRMED

The pinned SUT is the **published `corrlog-core` 0.2.2 wheel**, `sha256 232d6f66…`, and every ledger row records that hash. I verified the pin's correspondence claim myself rather than trusting the executor's tool:

- I unzipped the wheel and byte-compared all 8 Python members against `reference/v0.2.2/` source: **8 of 8 byte-identical** (`corrlog_core/__init__.py`, `corrlog_core/replay.py`, and the five adapter packages' modules).
- The verification schema `corrlog_core/schema/acr-v1.json` **is** inside the wheel.
- The standalone verifier is **not** in the wheel (confirmed independently; consistent with OBS-01).
- T053 (fresh reinstall of the pinned wheel → 0 file mismatches, historical chain verifies) corroborates the correspondence operationally.

**The development working tree was not evaluated** (consistently excluded by the pin, §9). **The evidence supports that the installed SUT corresponds to the pinned published artefact.**

---

## 3. CLAIMS C1–C8

### C1 — A valid signed CorrLog record can be cryptographically verified. **SUPPORTED**
T001 (verifier `exit 0`, `PASS valid under pinned key`; core `verify/verify_trusted/tamper_evident` all true), T002, T003 (`verify_chain` true, per-record true×3), T005, T031–T034, T038 (6/6 byte-identical against `rfc8785`), T045 (1,000,000-char payload verifies), T052, T053, T054, T055, and use case `07-cleanroom-verification` (`exit 0`, three records + chain consistent).

### C2 — Modification of signed material after signing is detectable. **SUPPORTED**
T006–T013: eight distinct signed-field mutations (content digest, corrected-content hash, reason, timestamp, provenance, signer identity, predecessor digest, model/version), each rejected by **both** paths (verifier `exit 1`, core false) with a control accepted in the same run. Corroborated by T033 (one-character Unicode mutation), T034 (NFD spelling of an NFC signature fails), T037 (unsigned extra field rejected), T039–T043, T044 (**20 of 20** seeded byte mutations rejected, 0 accepted), T026 (fabricated record carrying a copied signature rejected).
*Boundary:* the same-binary64 large-integer collision the spec describes (a decimal literal and its colliding spelling sharing one signature) was **not exercised** — see T035.

### C3 — A correction can cryptographically reference an earlier record through predecessor/supersedes. **SUPPORTED**
T002 (independent reproduction of the predecessor digest; `linkage=resolved`), T003 (O→C→D chain verifies), T022 (wrong predecessor digest → chain `exit 1`), T023 (predecessor tampered after signing → rejected), T042 (same-length wrong digest rejected), T028 (fork visible), T029 (dangling reference refused in chain view), T030 (circular reference refused in chain view). Use case correction carries `supersedes.receiptId` + `supersedes.digest` and verified in the cleanroom.
*Material boundary (PL-1):* linkage is only resolved in chain/checkpoint mode. Verified on its own, a correction naming a **nonexistent** predecessor returns `exit 0` (T029, `alone exit=0 chain exit=1`). This is documented (SPEC §1, report L-01) but it means C3's guarantee is a chain-mode guarantee, not a per-record one.

### C4 — A verifier can validate the evidence independently of the AI system that produced the output. **SUPPORTED**
T055 (cold directory: 3 records + schema + verifier + trusted key; `private_material=[]`, `corrlog=NO`, `exit 0`), T054 (same chain verified under a second interpreter, Python 3.11.15, no CorrLog), T004 (cleanroom export verified with `corrlog_in_cleanroom=NO`), use case `07`.
*Scope (PL-6, PL-7):* this demonstrates verification **outside the CorrLog runtime and without private key material**. It does not demonstrate agreement from an independently implemented third-party verifier — the verifier is CorrLog-authored release-source code and is **not** shipped in the published wheel.

### C5 — Verification can be performed from exported evidence using the appropriate trusted public key and verifier. **SUPPORTED**
T052 (export → re-import: `bytes_identical=true`, 3 records, all verify), T053 (fresh reinstall then historical chain verifies, `install_rc=0`, `mismatches=0`), T055 (cold export verified against a supplied trusted key), use case export + cleanroom (`06-export`, `07`).
*Boundary:* the verifier must be obtained from release **source** (not the wheel), and the trust anchor must be supplied out-of-band — verification against a caller-supplied anchor proves consistency with that key, not that the key is the right one (PL-3; T016).

### C6 — Records attributable to an untrusted or substituted signing key must not be accepted as belonging to the trusted signer. **SUPPORTED**
T016 (record signed by the attacker key: genuine anchor → `exit 1 FAIL untrusted signer`; attacker anchor → `exit 0`, i.e. trusted only when the caller trusts that key), T014 (trusted record under the attacker key as anchor → `exit 1`, `verify_trusted=false`), T011 (`agent.id` mutation rejected; sibling `agent.publicKey` variant → verifier `FAIL agent key mismatch`, core false), T015 signature-only control (`PASS signature consistency only; signer untrusted` — trust is explicitly not claimed), T017 (`verify(pub)=false`, signature-only control `exit 0`).
*Material boundary (PL-3):* refusal is conditional on the trusted anchor being the genuine one. Anchoring on an attacker-supplied key verifies the attacker's record (correct by design, and warned about in SPEC §1 / SECURITY.md). C6 holds as worded but its strength is entirely the anchor's.

### C7 — Malformed or cryptographically invalid records fail verification deterministically rather than silently being accepted. **SUPPORTED**
T018 (three malformed trusted-key files → `exit 1`; repeat deterministic), T039 (60% truncation → `exit 1`), T040 (trailing comma → `exit 1`), T041–T043 (field removed / digest corrupted / empty provenance → `exit 1` both paths), T044 (20/20 rejected), T046 (empty required field refused; schema-legal empties accepted), T036, T037, T006–T013, and operational: T049 (SIGKILL mid-write leaves nothing damaged and nothing accepted), T050 corrected (torn tail reported damaged, never accepted).
*Coverage gap, not a contradiction:* for T019 (random same-length signature) and T020 (truncated signature) the **independent verifier never produced a verdict** — see HD-1 — so the "both paths" half of those two registered rules is unestablished. The core rejected both.
*Boundary (PL-9):* rejection is deterministic but diagnosis is coarse — all signature, schema and key failures collapse to one generic verdict (`invalid record, schema, key or signature`), and a malformed trust anchor yields only `FAIL: 'publicKey'` (OBS-03).

### C8 — The original record remains distinguishable from subsequent corrections rather than being silently overwritten. **SUPPORTED**
T005 (append a correction; the original's bytes are unchanged; store holds 3 records), T003 (three distinct records in one chain), T052 (export/import byte-identical, 3 records), T047 (duplicate writes leave both lines individually valid; `JsonlSink` is documented as not deduplicating; `ReplayGuard` returns `True` then `False` on a fresh protected database), use case (original action, correction and subsequent human-review event preserved as three separate signed records).
*Boundary (PL-8):* the JSONL sink provides no uniqueness guarantee and replay protection is opt-in and needs protected persistent state — so "distinguishable" is a property of the records, not an enforced store constraint.

**No claim in C1–C8 is contradicted by the evidence. C1, C2, C3, C6, C7, C8 are supported on their own terms; C4 and C5 are supported for "outside the originating runtime" and qualified on verifier authorship/packaging (PL-6, PL-7).**

---

## 4. NEGATIVE BOUNDARIES N1–N6

All six are preserved — in the product's own documentation, in the use-case artefact, and in the report's non-conclusions. No product behaviour, documentation or executor claim was found that contradicts them.

- **N1** (not every AI error is detected) — preserved: `08-proof-boundary.json` lists under *cannot be concluded*: "that every error of the AI system was detected (only this one was)".
- **N2** (a valid signature does not prove the correction is factually correct) — preserved: SPEC.md line 7, "A signature does not prove the statement is true, that a referenced source is correct, that an agent performed an action, or that all events were recorded"; and the boundary file defers the truth of the recorded input, the correctness of the rule set, the validator's integrity, and the identity of the human reviewer to external evidence.
- **N3** (correction history is not necessarily complete) — preserved: SPEC.md 96–105 ("A checkpoint received alongside an untrusted chain establishes nothing"), the verifier's own wording `PASS consistent chain; completeness only relative to supplied trusted checkpoint`, T024 (reduced history vs trusted checkpoint → `exit 1`), and the boundary file.
- **N4** (CorrLog does not detect AI errors) — preserved and *demonstrated*: the detector in the use case is an external deterministic rule validator with `detector_is_ai_self_report: false`, and the boundary file states "that the AI system detected its own mistake" cannot be concluded.
- **N5** (CorrLog alone does not establish regulatory/APRA compliance) — preserved: boundary file: "that the insurer is compliant with APRA or any other regime: this package is a record of one decision and its correction, not a compliance artefact"; report §8 repeats it.
- **N6** (cryptographic validity does not prove the AI system is safe, fair or accurate) — preserved: boundary file: "that the underlying AI system is safe, fair or accurate" under *cannot be concluded*.

Two things are *close to* the boundary but I judge them to stay inside it, and both belong to the executor layer rather than the product: the T035 note ("two distinct literals that map to one binary64 **share a signature**") asserts a behaviour the run did not measure and the fixture did not construct; and the report's series-level "PASS (n of n)" counts overstate their own evidence in four places (HD-8). Neither claim overstates what CorrLog proves about the world; they overstate what the *execution* measured. Both must be corrected in any external use of this package.

---

## 5. TEST-BY-TEST ASSESSMENT (T001–T055)

Against the frozen pre-registered expectations, unmodified. Totals: **50 EVIDENCE SUPPORTS EXPECTED OUTCOME · 4 INSUFFICIENT EVIDENCE · 1 NOT APPLICABLE · 0 EVIDENCE CONTRADICTS EXPECTED OUTCOME** (one test contains an unexercised sub-case).

- **T001–T005 (A series) — SUPPORTS ×5.** Both paths agree: T001/T002 `exit 0` + core true; T003 chain `exit 0` with per-record true×3; T004 cold export verified with CorrLog absent (core not run by design); T005 original unchanged after appending a correction. (Ledger also preserves the superseded attempt-1 rows where the JWK anchor was refused — preserved, not hidden.)
- **T006–T013 (B series, tampering) — SUPPORTS ×8.** Every signed-field mutation rejected on both paths with an accepted control in the same run. T011 carries the erratum caveat in §1.4; the sibling `agent.publicKey` variant has its own preserved verdict.
- **T014–T020 (C series, trust anchor / key substitution):**
  - **T014 SUPPORTS** — `exit 1 FAIL untrusted signer`; `verify_trusted=false`.
  - **T015 INSUFFICIENT EVIDENCE** — the trusted-anchor run exited **2** with `standalone.py: error: one of the arguments --key --signature-only is required` and produced no verdict; the `--signature-only` control ran (`exit 0`, `PASS signature consistency only; signer untrusted`) and the core returned `verify(pub)=false`, but the pre-registered pass rule ("PASS if the trusted-anchor path refuses") was never exercised.
  - **T016 SUPPORTS** — genuine anchor refuses (`exit 1`), attacker anchor accepts; exactly the recorded configuration behaviour.
  - **T017 INSUFFICIENT EVIDENCE** — same usage-error pattern as T015; signature-only control `exit 0`, core `verify(pub)=false`.
  - **T018 SUPPORTS** — three malformed key files, all `exit 1`, deterministic.
  - **T019, T020 INSUFFICIENT EVIDENCE** — verifier `exit 2` usage error (no verdict); core rejected both (`false`). The registered "both paths reject" is half-established.
- **T021 (key rotation) — NOT APPLICABLE**, correctly: the pinned wheel exposes no rotation function, `kid` is informational, and the release documentation places rotation/revocation outside CorrLog (SECURITY.md). Justification is recorded with the documentation quotes, and historical verification under a single anchor is covered by T052/T053.
- **T022–T030 (D series, chain manipulation) — SUPPORTS ×9.** T022 wrong predecessor digest → `exit 1`; T023 predecessor tampered post-signing → `exit 1`; T024 broken link reported (`FAIL broken link`) and reduced history against a trusted checkpoint → `exit 1` while full history → `exit 0`; T025 reversed order → `FAIL missing genesis`; T026 fabricated record → that record fails, chain `exit 1`; T027 replay → `FAIL duplicate ID`; T028 fork → each branch verifies alone (`0`,`0`) but combined `exit 1`; T029 dangling predecessor → alone `exit 0` / chain `exit 1` (documented limitation, expectation met as written); T030 self-reference → hand-mutated variant rejected, doubled construction `FAIL missing genesis` (the signed single record verifies as a *record* — the circularity is caught only in the chain view; same class as PL-1).
- **T031–T038 (E series, canonicalisation):**
  - **T031–T034, T036–T038 SUPPORTS** — reordered fields, whitespace/CRLF/indent variants, Unicode signed (and one-character mutation rejected), NFC verifies / NFD rejected, three null/empty/missing cases as registered (schema-legal empty reason `exit 0`; `fix.note=null` `exit 1`; action removed `exit 1`), extra field un-re-signed `exit 1` / re-signed `exit 0`, and `rfc8785` byte-identity on 6 of 6 records.
  - **T035 — SUPPORTS for cases (a), (c), (d); case (b) INSUFFICIENT EVIDENCE.** Case (a) `1 → 1.0` verifies (`exit 0`), case (c) different value rejected, case (d) string→number rejected — all as pre-registered. **Case (b) does not test what it claims:** its label says `9007199254740992 -> 9007199254740993 (same binary64)`, but the fixture's actual change is `metadata.big: 2 → 9007199254740993` (base value **2**, verified by me field-by-field). Those are different binary64 values, so rejection is the *correct* behaviour and the registered same-binary64 expectation is simply not exercised. Classified as a harness/register defect (§6, HD-9), **not** a product defect. Consequence for scope: the spec's documented same-binary64 spelling collision remains **untested** by this validation.
- **T039–T046 (F series, malformed/corrupt) — SUPPORTS ×8.** Truncation, trailing comma, removed field, corrupted digest, empty provenance, 20/20 byte mutations rejected, 1M-character payload accepted, and the three empty-payload cases exactly as registered.
- **T047–T055 (G series, operational) — SUPPORTS ×9.**
  - T047 duplicate writes: store lines all individually valid, `damaged=0`; `ReplayGuard` `True` then `False` on a **fresh** protected database (corrected run, `logs/g-T047-rerun.txt`). The raw-outcome `FAIL` and its cause (reused guard DB) are disclosed in the README.
  - T048 four concurrent writers, 100 records: 100 parsed, 0 damaged, all verified.
  - T049 SIGKILL mid-record: 0 damaged after kill, append succeeds, final 2 records verify. (Limitation PL-4: a torn tail was not naturally produced.)
  - T050 torn tail: first pass `damaged=0` (harness write-then-read bug, disclosed); corrected run `parsed=1`, **`damaged_lines=1`**, partial tail never accepted (`logs/g-T050-fixed.txt`). Expectation met.
  - T051 read-only file and read-only directory both raise `PermissionError`; existing record still verifies.
  - T052 export/re-import `bytes_identical=true`, 3 records verify.
  - T053 fresh reinstall of the pinned wheel: `install_rc=0`, `file_mismatches=0`, chain `exit 0`.
  - T054 second interpreter (Python 3.11.15, no CorrLog): `exit 0`, chain consistent. OS diversity explicitly **not** obtained and labelled as such.
  - T055 cold export with trusted material only: `private_material=[]`, `corrlog=NO`, `exit 0`, 3 records + chain.

---

## 6. THREE TYPES OF FINDINGS

### A. PRODUCT DEFECTS (observed CorrLog behaviour contradicting a frozen claim or expected result)
**None evidenced.** Every registered expectation that was actually exercised by a correctly constructed fixture was met by the pinned artefact. The three apparent candidates did not survive inspection:
- T035 case (b) looks like a contradiction but the fixture does not construct the scenario (base value is `2`) — the rejection is correct behaviour → harness defect.
- T019/T020's non-verdicts are a malformed harness invocation, not a product refusal → harness defect.
- T030's record-level acceptance of a self-referential record is consistent with the documented per-record model (SPEC §1: per-record checking does not detect insertion/deletion/reordering/truncation/substitution/replay; linkage requires chain or checkpoint mode) → product limitation, disclosed as similarly shaped L-01.

### B. VALIDATION / HARNESS DEFECTS
1. **HD-1 — malformed verifier invocations (T015, T017, T019, T020).** Commands omitted both `--key` and `--signature-only`; the verifier exited 2 on an argparse usage error and never evaluated the record. Four registered pass rules were therefore not exercised, while their READMEs read `mechanical outcome: PASS`.
2. **HD-2 — T011 fixture overwrite (disclosed).** Two variants shared filenames; the registered `agent.id` bytes are gone and the ledger's recorded hashes no longer match the files at those paths — the only two such mismatches in the entire pack.
3. **HD-3 — shared `cleanroom/export/` copies (not disclosed).** 43 tests' captioned verifier commands name a last-writer-wins scratch path; T011's command path today holds T013's mutation. Captioned commands no longer identify the verified bytes.
4. **HD-4 — corrected runs with stale outcome fields.** T044 first pass (classifier), T047 (reused guard DB), T050 (write-then-read bug), T036 first pass, A-series attempt-1 (JWK anchor). All disclosed; corrected evidence preserved; but the `mechanical outcome: FAIL` fields were left in READMEs.
5. **HD-5 — stale packaging artefacts.** `PACK-MANIFEST.md` and the top-level `SHA256SUMS.txt` describe an earlier snapshot; disclosed and superseded in the addendum.
6. **HD-6 — trust-anchor description slip.** The report's "public key file `4bf83c53…`" is `TEST-signer.trust.json`; the pin's `1a1ef939…` is `TEST-signer.pub.json`. Both real; one phrase for two files.
7. **HD-7 — duplicate A-series ledger rows** (attempt-1 and corrected) with no in-row supersession marker, so a reader scanning outcomes sees two conflicting values for T001–T005.
8. **HD-8 — executor report overstatement in four series summaries.** T014–T020 "PASS 7 of 7" (four of those record verifier usage errors); T031–T038 "PASS 8 of 8" (T035 carries an unexercised case and a `FAIL` raw outcome); T022–T030 "9 of 9 PASS" (T030 is recorded `EXECUTED`); T047–T055 "9 of 9 PASS" (T047 and T050 READMEs carry `FAIL` as the raw outcome). Also "Defects discovered: None" is stated without the qualifiers these items require, and the T011 observable quoted ("agent key mismatch") belongs to the sibling `agent.publicKey` variant, not to the stdout preserved under T011.
9. **HD-9 — T035 case (b) fixture mis-construction.** `metadata.big` mutated from `2` to `9007199254740993` while labelled `9007199254740992 -> 9007199254740993 (same binary64)`. The registered expectation is unexercised, and the executor's note ("two distinct literals ... share a signature") is unsupported by the fixture.

### C. PRODUCT LIMITATIONS
PL-1 record-level verification does not resolve `supersedes` links (dangling or circular references pass as individual records; T029, T030) · PL-2 completeness requires an independently trusted checkpoint, and a checkpoint from the same transport proves nothing · PL-3 anchoring on a supplied key proves consistency, not identity/trust (T016) · PL-4 no naturally produced torn tail (T049), so that path rests on manual truncation (T050) · PL-5 no cross-OS evidence (T054 is interpreter diversity only) · PL-6 the standalone verifier is not shipped in either published wheel · PL-7 the standalone verifier is CorrLog-authored · PL-8 the JSONL sink has no uniqueness guarantee and replay protection is opt-in with protected state · PL-9 verification diagnostics are coarse (one generic verdict string) · PL-10 no key rotation/revocation in v0.2.2 (`kid` informational) · PL-11 the documented same-binary64 spelling collision is untested by this validation.

---

## 7. ASSESSMENT OF THE EXECUTOR'S STATED LIMITATIONS

| # | Stated limitation | My assessment | Materially changes C1–C8? |
|---|---|---|---|
| 1 | Dangling predecessor references may verify as individual records | **Confirmed** — T029 `alone exit=0`, chain `exit 1`; consistent with SPEC §1. | Qualifies **C3**: linkage is a chain-mode guarantee. |
| 2 | Completeness depends on an independently trusted checkpoint | **Confirmed** — T024 reduced-history `exit 1`; SPEC 96–105; verifier's own wording. | No change; it is the correct reading of C3/C8 scope. |
| 3 | Embedded-key verification without an external anchor proves consistency, not identity/trust | **Confirmed** — T016 attacker-anchor `exit 0`; SECURITY.md line 12. | Qualifies **C6**: refusal depends on the genuine anchor being supplied. |
| 4 | SIGKILL testing did not naturally reproduce a torn tail | **Confirmed** — T049 `damaged_after_kill=0`; the torn-tail case rests on T050's manual truncation. | No change; narrows the operational evidence for C7. |
| 5 | Cross-OS behaviour was not independently tested | **Confirmed** — T054 is Python 3.11.15 on this host; `os_diversity: NOT OBTAINED`. | No change to C1–C8; a scope limit on C4/C5. |
| 6 | Standalone verifier not shipped in the published wheel | **Confirmed by me** — no verifier member in `corrlog_core-0.2.2-py3-none-any.whl`; the schema *is* shipped. | Qualifies **C5** (how the verifier is obtained). |
| 7 | Standalone verifier is CorrLog-authored, not third-party | **Confirmed** — OBS-02, and the file is CorrLog release source. | Qualifies **C4/C5**: "outside the runtime" is shown; "independent implementation" is not. |

Limitations 1–7 are accurately stated and honestly scoped. Three of them (1, 3, 6/7) materially qualify how C3, C6 and C4/C5 should be read by a buyer. I found **no** limitation the executor overstated as stronger than the evidence, and one behaviour they did **not** test (PL-11).

---

## 8. CLAIMS-TRIAGE USE CASE

**Statement assessed:** *CorrLog can preserve and export a cryptographically verifiable record of an original AI action, an externally detected correction, the correction reason/provenance, signer attribution and correction linkage for later verification outside the originating AI runtime.*

**Verdict: SUPPORTED** (as worded, with the scope notes below).

Evidence: `USECASE-CLAIMS-TRIAGE` holds the original AI routing record, the external determination (`rule_validator.py`, `LR-CEILING-2026-09 VIOLATION`, `deterministic: true`, `detector_is_ai_self_report: false`), the correction and a subsequent human-review event. I read the correction's signed fields directly: `reason` (deterministic business-rule validator found a rule violation), `fix.note`, `fix.source.type`/`fix.source.reference` (`rule_validator.py LR-CEILING-2026-09 VIOLATION`), `trigger=check_failed`, signer attribution (`agent.id`, `signature.kid`/`publicKey`/`sig`, `principal.id=insurer-demo`, `principal.type=organization`), and correction linkage (`supersedes.receiptId`, `supersedes.digest`). The cold cleanroom run returned `exit 0` with three records verified and `PASS consistent chain; completeness only relative to supplied trusted checkpoint`, with `private_material: []` and `corrlog_in_cleanroom: "NO"`. `08-proof-boundary.json` separates proved / externally asserted / not concludable.

Scope notes (already inside the statement, and preserved by the evidence): "cryptographically verifiable" means canonical-form + signature + linkage verification against a supplied trusted public key; completeness holds only relative to a trusted checkpoint; and the package proves nothing about APRA compliance, the completeness of AI events, the factual truth of the correction, or the safety of the model — all four are explicitly excluded in the artefact.

---

## 9. OVERALL VERDICT

### A. Technical assurance conclusion
**VALIDATED WITH QUALIFICATIONS.**

Six of the eight claims (C1, C2, C3, C6, C7, C8) are supported as worded; C4 and C5 are supported for verification outside the originating runtime, and qualified on verifier authorship (CorrLog-authored) and packaging (not in the wheel). No claim is contradicted, and **no CorrLog product defect is evidenced**. The assessment rests on four registered tests being incomplete (T015, T017, T019, T020), one registered case being unexercised (T035b), one fixture-loss erratum, and one undisclosed chain-of-custody weakness — all of which reduce coverage rather than overturn results.

### B. Scope
**Covers:** the pinned published `corrlog-core` 0.2.2 wheel (`232d6f66…`, 8/8 modules byte-identical to the tagged reference source), its schema, and the CorrLog-authored standalone verifier from release source; 55 registered tests plus one simulated claims-triage use case; single-record verification, tamper detection, canonicalisation, malformed-input handling, trust-anchor/substitution behaviour, chain manipulation, and operational store/export behaviour; verification in a CorrLog-free environment with no private key.
**Does not cover:** the development working tree; any published artefact other than the pinned wheel; independently implemented third-party verifier agreement; cross-OS behaviour; key rotation/revocation (absent from v0.2.2); the documented same-binary64 integer-spelling collision; completeness beyond a trusted checkpoint; and any property of the underlying AI system or of regulatory compliance.

### C. Material qualifications (for a buyer, auditor, engineer or assurance practitioner)
1. **Anchoring is the whole of trust.** A record signed by a substituted key verifies if the verifier is handed that key as the anchor (T016). C6's protection is worth exactly the provenance of the anchor.
2. **Linkage is chain-mode only.** A correction naming a nonexistent predecessor verifies as an individual record (T029); dangling and circular references are invisible outside chain/checkpoint verification (PL-1).
3. **Completeness is checkpoint-relative** and a checkpoint delivered alongside the chain establishes nothing (SPEC 96–105, T024).
4. **The verifier is CorrLog-authored and not shipped in the wheel.** Verification outside the runtime is demonstrated; independent third-party implementation is not. Obtain the verifier from release source.
5. **Coverage gaps in this validation:** four trust-anchor/malformed-signature tests ran on one path only (T015, T017, T019, T020); the same-binary64 spelling collision was not constructed (T035b); a torn tail came from manual truncation, not a crash (T049/T050).
6. **Diagnostics are coarse** — all signature/schema/key failures collapse into one generic verdict, so an operator cannot tell a schema problem from a key problem (PL-9).
7. **T011's registered fixture bytes no longer exist**, and the `cleanroom/export/` copies are last-writer-wins, so some captioned commands cannot be tied back to the bytes verified.

### D. Defects (CorrLog product)
**None evidenced.** No exercise of the pinned artefact with a correctly constructed fixture produced behaviour contradicting a frozen claim or expected result.

### E. Harness / evidence defects
HD-1 malformed verifier invocations (T015/T017/T019/T020) · HD-2 T011 fixture overwrite (disclosed) · HD-3 shared `cleanroom/export/` path (undisclosed) · HD-4 corrected runs leaving stale outcome fields · HD-5 stale packaging artefacts (disclosed) · HD-6 trust-anchor description slip · HD-7 duplicate A-series ledger rows without in-row supersession · HD-8 report series summaries overstating their own evidence (four series) · HD-9 T035 case (b) fixture mis-construction and its unsupported executor note.

### F. Supported external wording
> CorrLog 0.2.2 was validated as a signed-record and correction-linkage component. On the pinned published wheel, a valid signed record verifies cryptographically against a supplied trusted public key; any post-signing modification of signed material is detected; corrections reference earlier records through a verified predecessor digest, and chain manipulation, key substitution against the trusted anchor, and malformed or corrupted records are refused deterministically. Exported evidence can be verified in an environment that has no CorrLog runtime and no private key, using the trusted public key and the release-source standalone verifier. Original records and their corrections remain separately identifiable, and the package explicitly distinguishes what is cryptographically proved from what is merely asserted. Limitations are material and stated: trust derives from the supplied anchor, completeness holds only relative to an independently trusted checkpoint, the verifier is CorrLog-authored and not shipped in the wheel, no cross-OS or independent third-party verification was obtained, and no key rotation exists in this version.

### G. Prohibited wording (would overstate this validation)
- Any claim of **APRA or regulatory compliance**, or that CorrLog satisfies an audit, prudential or record-keeping obligation.
- Any claim that CorrLog **detects AI errors**, or that a correction's presence proves the AI system erred.
- Any claim that a valid signature proves the **content is true, accurate, fair or safe**, or that the disclosed model/prompt metadata describes what actually ran.
- Any claim that the correction history is **complete**, or that completeness is established without an independently trusted checkpoint.
- Any claim of **tamper-proof / tamper-evident ledger**, immutable record, or that omission of an event is detectable — implementation, omission and hidden history are not prevented.
- Any claim that verification was performed by an **independently implemented third-party verifier**, or that cross-platform/OS behaviour was verified.
- Any claim of **"all 55 tests passed"**, "zero defects, fully validated", "no limitations on trust", or that **R1-style closure** has been granted — four registered tests are incomplete on one path, one registered case was not constructed, and the executor's own series summaries overstate their evidence.
- Any claim that key **rotation or revocation** is supported in 0.2.2.

---

*Prepared by LiefieTango as independent scorer. Read-only: no artefact in either archive was modified, no CorrLog API was executed, and no test was re-run. All digests reported here were recomputed by me.*
