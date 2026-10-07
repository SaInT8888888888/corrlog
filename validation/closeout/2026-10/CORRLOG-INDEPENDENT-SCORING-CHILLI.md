# CORRLOG VALIDATION — INDEPENDENT SCORING VERDICT

**Scorer:** Chilli (independent scorer). **Date:** 2026-10-07 (UTC).
**Artefacts scored:** executor submission `corrlog-validation-2026-10.zip` and delivery addendum
`CORRLOG-VALIDATION-DELIVERY-ADDENDUM.zip`. I did not design the protocol, execute any test, modify the
SUT, or write the executor's conclusions. I did not read or use any other party's scoring of this run.
I did not rerun CorrLog; my checks are read-only over the preserved artefacts.

---

## 1. Evidence package integrity (verified first)

| Check | Result |
|---|---|
| Submission ZIP SHA-256 | `8575ff3f9c71ff95da7900ae3974c438e904441ac53132bef553836e48a07c2e` — **matches** the brief |
| Addendum ZIP SHA-256 | `90172bd43d43b26cf978b1be37872ecc244f14ac072b014deea3bad9f2832eb1` — **matches** the brief |
| Frozen SUT pin document | `b6aefa37f2fbd0a94afa956f49585996cb0546a470e1c17eb35c15b5a6174cfc` — **matches** |
| Frozen test register v1 | `90f1a26b5814a51c0135be485a03bce303b023f0f93cdecc9642b7ed61a936c0` — **matches** |
| Pinned SUT wheel | `232d6f6668f42fae70f869347cf6fc82003ceb0031299c4f1e29ccb9e479b6ec` — **matches** the pin |
| Pinned sdist / inspect wheel / release-tag tarball | `baf81148…`, `b144598a…`, `5258da99…` — all **match** |
| Release-tag verifier in every cleanroom copy | `ace4c11e4d80c3b75d7d062414824b3c261aeed46780e073c61f11fb414a0f7c` — identical in all 6 locations |
| Trust anchor files in the cleanroom/cold dirs | `4bf83c53…` identical in all 4 locations; no private/seed material present |
| Schema in wheel and cleanroom | `48bd9ad9…` — matches the pin |
| Addendum's own SHA256SUMS | 6 of 6 files match |
| Addendum FINAL-FILE-INVENTORY vs the submission ZIP | **1343 of 1343 files match** (hash and size); inventory covers the ZIP exactly (0 unlisted, 0 extra); 4,287,092 uncompressed bytes and 1,343 files agree with the addendum header |
| Submission's own top-level `SHA256SUMS.txt` | **STALE**: 312 lines, 310 match, **1 mismatch** (`CORRLOG-VALIDATION-RUN-LEDGER.md` grew after it was generated), **1 missing** (`harness/__pycache__/runner.cpython-313.pyc`, not shipped), and it omits 1,032 files |
| Ledger's completion hashes | **DO NOT MATCH the delivered artefacts**: ledger records executor report `5e2098d3…` (delivered `20cba8a2…`) and delivered pack `6a6412cf…` (delivered `8575ff3f…`) |

**The package is intact and scoreable**, but the submission's self-integrity manifest is stale and the
ledger's own completion hashes refer to a pre-delivery state of the report and the ZIP. Both are
documented as packaging errata (the addendum covers `PACK-MANIFEST.md` and `SHA256SUMS.txt`) except the
report-hash and pack-hash mismatches, which the addendum does **not** mention.

**Original vs reconstructed material.** Everything in the submission ZIP is original captured evidence
(all 1,343 files verified against the addendum inventory). The only reconstructed artefacts are the two
addendum files `T011-RECONSTRUCTED-agent-id.json` and `T011-RECONSTRUCTED-mutation.txt`, correctly
labelled "RECONSTRUCTED AFTER EXECUTION". I verified that their hashes reproduce the ledger's recorded
T011 hashes exactly, and that the on-disk `evidence/T011/` fixtures instead hold the later
`agent.publicKey` variant — the erratum's two hash rows are accurate to the byte.

## 2. System under test

The pin identifies the **published `corrlog-core` 0.2.2 wheel** (hash above), installed unmodified, with
the release-tag standalone verifier and the wheel's own schema used for cleanroom verification. The
development tree with 6 uncommitted modifications is explicitly excluded by the pin. I confirmed:
the wheel's 8 shipped Python modules are the artefact the run used; the wheel ships the schema and
**no verifier member**; the verifier used in every cleanroom run is byte-identical to the release-tag
verifier. **Evidence supports that the installed SUT corresponds to the pinned published artefact** —
via the pin's measured hash, the wheel present in the pack, and the per-file correspondence claim
(§8 of the pin), which I could not re-measure directly because the harness environments sit outside the
delivered pack, but whose inputs (the wheel) are present and hash-verified.

## 3. Claims C1–C8

| Claim | Score | Basis (test IDs / artefacts) |
|---|---|---|
| **C1** valid signed record verifies | **SUPPORTED** | T001 (verifier exit 0 "PASS valid under pinned key" + core `verify` True), T004 (cold export, CorrLog-free env), T053 (fresh reinstall, chain exit 0), T055 (cold export exit 0) |
| **C2** post-signing modification is detectable | **SUPPORTED** | T006–T013 (8/8 one-field mutations rejected on both paths; I independently confirmed each fixture differs from pristine in exactly one signed field with `signature.sig` unchanged), T044 (20/20 single-byte mutations rejected; I independently confirmed all 20 files differ from pristine by exactly one byte at the stated positions), T012/T042/T043, T023, T026 |
| **C3** correction references an earlier record | **SUPPORTED** | T002 (`C.supersedes.receiptId == O.correctionId`, digest resolves), T003 (D→C link, chain exit 0), T022/T024/T025/T027/T028/T029 (broken links, reordering, duplicates, forks all reported, never silently accepted) |
| **C4** verification independent of the producing AI system | **SUPPORTED** | T004, T054, T055, USECASE: verification run with no CorrLog present (`corrlog_in_cleanroom: NO`), no private key, records + trusted public key + verifier + schema only; producing agent (`agent://claims-triage`) is not involved |
| **C5** verification from exported evidence + trusted key + verifier | **SUPPORTED** | T004 (cold export chain exit 0), T052 (export/import byte-identical, 3 records verified), T055, USECASE cleanroom transcript |
| **C6** records from an untrusted/substituted key not accepted as the trusted signer | **SUPPORTED** | T014 (wrong anchor → "FAIL untrusted signer", exit 1; core `verify_trusted` False), T016 (attacker-signed record under the genuine anchor → FAIL; under the attacker anchor → accepted, recorded as a configuration fact), T011 publicKey variant. Caveat: `verify(record)` with no anchor returns True on embedded-key consistency only (L-03) and must not be read as trust |
| **C7** malformed/invalid records fail deterministically, never silently accepted | **PARTIALLY SUPPORTED** | Supported: T018 (three malformed trusted keys → exit 1, repeat exit 1), T039–T043 (parse/schema failures → verifier "FAIL …" exit 1 + core False), T044 (20/20), T006–T013. **Not supported for the signature arm**: T019 and T020's preserved cleanroom invocations are argparse usage errors (`exit 2`, stderr "one of the arguments --key --signature-only is required") — the verifier never evaluated those records, so the independent path did not test malformed/truncated signatures; only the SUT's own core API returned False |
| **C8** original distinguishable from later corrections, not silently overwritten | **SUPPORTED** | T005 (original byte-identical after a correction is added, still verifies, `store_records=3`), T027 (replay → "FAIL duplicate ID", not accepted as a second successor), T028 (fork: both branches verify individually, combined chain → FAIL broken link), T025 (order enforced), T052 (records byte-identical across export/import) |

## 4. Negative boundaries N1–N6

| Boundary | Preserved? | Where |
|---|---|---|
| N1 CorrLog does not prove every AI error was detected | **Yes** | Execution report §8; `USECASE…/08-proof-boundary.json` ("asserted_by_external_evidence_not_proved_by_corrlog") |
| N2 a valid signature does not prove the correction is factually correct | **Yes** | §8; 08-proof-boundary.json ("that the routing decision was wrong in any legal or bus…" listed as not proved) |
| N3 the available correction history is not necessarily complete | **Yes** | §8; T024 (reduced chain refused only when a trusted checkpoint is supplied); verifier's own success text states the boundary |
| N4 CorrLog does not itself detect AI errors | **Yes** | §8; use case detector is an external deterministic rule validator (`03-external-determination.json`, `detector_is_ai_self_report: false`) |
| N5 CorrLog alone does not establish regulatory/APRA compliance | **Yes** | §8 |
| N6 cryptographic validity does not prove the AI system is safe/fair/accurate | **Yes** | §8 |

**No product behaviour, documentation or executor claim was found that contradicts these boundaries.**
The closest pressure points are honest and self-limiting: `08-proof-boundary.json` names the human
reviewer's identity and the rule set's correctness as *asserted externally*, and OBS-02 limits what
"independent verification" means in this run.

## 5. Registered tests T001–T055

48 **EVIDENCE SUPPORTS EXPECTED OUTCOME** · 6 **INSUFFICIENT EVIDENCE** · 1 **NOT APPLICABLE** ·
0 **EVIDENCE CONTRADICTS EXPECTED OUTCOME** (no pre-registered expectation is contradicted by evidence
that is attributable to the product).

**Tests where evidence supports the pre-registered outcome:** T001, T002, T003, T004, T005,
T006, T007, T008, T009, T010, T011 (with the erratum), T012, T013, T014, T016, T018, T022, T023, T024,
T025, T026, T027, T028, T029, T031, T032, T033, T034, T036, T037, T038, T039, T040, T041, T042, T043,
T044 (corrected matrix), T045, T046, T047 (fresh-guard rerun), T048, T049, T050 (fixed rerun), T051,
T052, T053, T054, T055. Plus the end-to-end claims-triage use case.

**NOT APPLICABLE (1):** **T021** — the register's own alternative branch (documented NOT APPLICABLE with
justification) is met: `SPEC.md` and `SECURITY.md` are quoted placing rotation/revocation outside
CorrLog, no rotation API exists in the pinned wheel, and the supporting per-anchor check was executed
and recorded (`O` verifies under anchor A and fails under B; the B-signed record fails under A). Scope
note: key rotation itself is therefore **not tested** by this validation.

**INSUFFICIENT EVIDENCE (6):**

- **T015** — the preserved trusted-anchor arm is an argparse usage error (exit 2), so the verifier never
  judged the attacker-resigned record; the `--signature-only` control (exit 0) is reported in the README
  only, with no preserved command/output. The core API result (False/False) is preserved.
- **T017** — same invocation defect; same evidence shape.
- **T019** — same invocation defect; the malformed-signature rejection is evidenced only by the SUT's own
  core API (`verify(pub)=False`), not by the independent verifier.
- **T020** — same; truncated signature is likewise unevidenced on the independent path.
- **T030** — the registered construction (a validly signed record whose `supersedes` points at itself)
  was **not built**: `self-reference-by-id-signed.json` has `correctionId=SELF-REF-0001` and
  `supersedes.receiptId=f2f363c0…` (i.e. it points at the *original* record, not itself), and it verifies
  exit 0. The only true self-reference is a hand-mutated file whose signature is invalid, so it fails for
  signature reasons rather than by detecting circularity. The duplicate-chain and hand-mutated outcomes
  are recorded ("missing genesis", "FAIL invalid …") and are consistent with the register, but the
  registered case itself remains unmeasured.
- **T035** — case (b) was mis-built: `numeric-base.json` carries `metadata.big = 2` and
  `big-literal-collision.json` carries `metadata.big = 9007199254740993`, so the mutation is
  `2 → 9007199254740993`, a **different** binary64 value, correctly rejected. The registered
  same-binary64 collision pair (9007199254740992 vs 9007199254740993) was therefore never exercised.
  The other three variants behave exactly as pre-registered (`1 → 1.0` verifies; `1 → 3` rejected;
  `"1" → 1` rejected), and `1 → 1.0` passing is itself evidence that integer/float spelling is
  normalised to a shared binary64 form. The T035 evidence README records mechanical outcome **FAIL**,
  which contradicts the executor report's "T031–T038 PASS (8 of 8)".

## 6. Three kinds of findings, separated

### PRODUCT DEFECT
**None evidenced.** No test produced an outcome that contradicts a frozen claim or expected result
attributable to CorrLog. The T035 "FAIL" resolves to a fixture error; the T044/T047/T050 "FAIL" rows are
harness artefacts with corrected reruns; the behaviours that do constrain use (dangling predecessor,
completeness only against a checkpoint, embedded-key consistency, generic diagnostics, no rotation) are
documented limits or limitations, not claim violations.
**Open risk (not a defect):** the same-binary64 canonicalisation case (T035b) and self-referential
signed linkage (T030) remain unmeasured, so a defect in those corners cannot be ruled out from this pack.

### VALIDATION / HARNESS DEFECT
1. **T015/T017/T019/T020** verifier invocations omitted `--key`/`--signature-only`; both the harness and the
   exit-code convention treated argparse's `exit 2` as a verification verdict. (The verifier returns 0/1
   only, so `exit 2` is unambiguously a usage error.)
2. **T011** mutation helper wrote two different fixtures to one filename pair inside a single test case,
   overwriting the registered `agent.id` fixture. Reconstructed afterwards; the run's stdout/exit for the
   registered arm survive.
3. **T030** registered self-reference never constructed in a validly signed form.
4. **T035** fixture base value wrong (`2` instead of `9007199254740992`), so the registered case was not tested.
5. **T044** first-pass classifier omitted the signature axis (19/20); corrected in a later ledger row.
6. **T047** rerun reused a persistent `ReplayGuard` database (first-pass FAIL for the wrong reason);
   re-run with a fresh database.
7. **T050** first pass opened the file for writing before reading, so no partial record existed; fixed and
   re-run (parsed=1, damaged=1).
8. **A-series attempt 1** trust anchor supplied as a JWK; preserved under `_harness-attempt-1/`.
9. **D-series** used a cleanroom helper because `rfc8785` is absent from the pinned environment.
10. **Stale per-test evidence folders**: T035, T044, T047, T050 READMEs still say `FAIL` while the
    authoritative ledger rows and the executor report say the outcome was met.
11. **Ledger vs delivery**: the ledger's completion hashes for the executor report (`5e2098d3…`) and the
    delivered pack (`6a6412cf…`) do not match the delivered artefacts (`20cba8a2…`, `8575ff3f…`).
12. **Register §"evidence" requirement not met by every folder**: T035, T038, T044, T047–T052, T054, T055
    and USECASE have empty `command-verifier.txt` / `exit-verifier.txt` / `stdout-verifier.txt` at the test
    folder level (for T054, T055 and USECASE the real transcripts exist in sub-folders `clean-alt/`,
    `cold/`, `07-cleanroom-verification/`).
13. **Executor report precision**: "76 mechanical rows" (I measure 69 test rows + 1 use-case row);
    "'FAIL agent key mismatch' for the identity variant" attributes to the registered `agent.id` arm a
    message that the preserved stdout shows came from the `agent.publicKey` variant; and the
    "T031–T038 PASS (8 of 8)" claim contradicts T035's own evidence folder.
14. **Stale manifest in the pack** (`PACK-MANIFEST.md`, top-level `SHA256SUMS.txt`) — already disclosed by
    the addendum.

### PRODUCT LIMITATION
1. **Dangling predecessor invisible at record level** (T029): a correction naming a nonexistent
   predecessor verifies as a single record; only a chain view reports the broken link.
2. **Completeness requires an independently trusted checkpoint** (T024): a removed intermediate record is
   not detectable from the surviving records alone; the verifier's own message says so.
3. **Embedded-key verification is consistency, not trust** (T014/T015/T017): `verify(record)` without an
   anchor returns True for a record with a consistent embedded key.
4. **Verifier is not shipped in the wheel** (OBS-01; I confirmed the wheel has no verifier member — the
   schema is shipped): a verifier must be obtained from the source, outside the installed distribution.
5. **The verifier is CorrLog-authored** (OBS-02): "independent" here means outside the CorrLog runtime,
   not a separately implemented third-party verifier.
6. **No key rotation/revocation facility** (T021), by documentation.
7. **Store guarantees are split** (OBS/L-06): `JsonlSink` offers no uniqueness, no fsync, tolerates torn
   tails and reports damage; `ReplayGuard` is at-most-once in a caller-protected local SQLite database,
   explicitly not a distributed service.
8. **Torn tail not naturally reproduced under SIGKILL** (T049: 0 damaged tails in 3 large-append
   attempts); the torn-tail behaviour is evidenced instead by the deterministic T050 construction.
9. **Diagnostic precision**: all verification failures collapse to one message
   ("invalid record, schema, key or signature"), so an operator cannot distinguish schema, key and
   signature failures (OBS-03).
10. **Cross-OS behaviour not obtained** (T054 used a second interpreter on the same OS; recorded honestly).

## 7. Assessment of the executor's stated limitations

| Stated limitation | My assessment | Does it change C1–C8? |
|---|---|---|
| Dangling predecessor verifies as an individual record | **Confirmed** (T029 alone exit 0) | Yes, in scope terms: C3 holds only in the chain view |
| Completeness depends on an independently trusted checkpoint | **Confirmed** (T024; verifier's own wording; T055/T054/USECASE success text repeats it) | Yes: materially narrows any completeness claim (N3) |
| Embedded-key verification proves consistency, not identity/trust | **Confirmed** (T014, T015, T017 core tuples: `verify(None)=True` for attacker-signed content) | Yes: narrows how `verify()` alone may be read; C6 holds on the trusted path |
| SIGKILL did not naturally reproduce a torn tail | **Confirmed** (0 of 3; T049) | No: the register's expectation is met and torn-tail handling is evidenced via T050 |
| Cross-OS behaviour not independently tested | **Confirmed** (T054 is a second interpreter, same OS) | No for C1–C8; blocks any cross-platform claim |
| Standalone verifier not shipped in the wheel | **Confirmed independently** (wheel RECORD has no verifier member; schema is shipped) | Yes, for deployment of C5: verification material must come from the source |
| Verifier is CorrLog-authored, not third-party | **Confirmed** (OBS-02; import block contains no corrlog imports) | Yes, in scope terms for C4/C5: same-author implementation |

## 8. Claims-triage use case

**Statement scored:** "CorrLog can preserve and export a cryptographically verifiable record of an
original AI action, an externally detected correction, the correction reason/provenance, signer
attribution and correction linkage for later verification outside the originating AI runtime."

**Verdict: SUPPORTED.**

Evidence: `02-original-record.json` (action `claim_route`, target `claim:1047`, model/prompt/input/output
metadata), `03-external-determination.json` (deterministic rule validator, rule `LR-CEILING-2026-09`,
violation), `04-correction.json` (`trigger=check_failed`, reason naming the validator finding,
`fix.source.reference="rule_validator.py LR-CEILING-2026-09 VIOLATION"`, `supersedes` binding the
original's `correctionId` and digest), `05-subsequent-event.json` (human-flagged follow-up linked to the
correction), `06-export/EXPORT-MANIFEST.json` (three ids and both supersedes links),
`07-cleanroom-verification/run.txt` (exit 0: three "PASS valid under pinned key" + "PASS consistent
chain", CorrLog-free environment, no private material), `08-proof-boundary.json`, `09-usecase-summary.json`.

Scope limits I verified in the artefacts themselves: "signer attribution" means the signing key/kid and
the agent id (all three records are signed by the same test key; the named human reviewer is a string in
`fix.source.reference`, and the proof-boundary file explicitly lists the reviewer's identity and the rule
set's correctness as *asserted externally*). No APRA compliance, no event-completeness and no factual
truth of the correction is supported by this evidence, and none is claimed by it.

## 9. Overall verdict

### A. Technical assurance conclusion

**VALIDATED WITH QUALIFICATIONS.**

On the pinned published artefact (`corrlog-core` 0.2.2 wheel, hash-verified, in a CorrLog-free
verification environment), the evidence supports C1, C2, C3, C4, C5, C6 and C8, with C7 partially
supported, and the negative boundaries N1–N6 correctly preserved. The qualification is not a hedge:
one claim (C7) is only partly established, six registered tests are not fully evidenced, and the
package's own self-integrity manifest is stale, so an unqualified "validated against the frozen claim
set" is not supportable from this evidence.

### B. Scope

Covers: the frozen claim set C1–C8 as tested by the frozen register's 55 tests and the claims-triage use
case, on the pinned `corrlog-core` 0.2.2 wheel and the release-tag standalone verifier, on one host
(Debian 13, Python 3.13.5; plus a Python 3.11 interpreter), with exported evidence and a trusted public
key. Does not cover: the CorrLog development tree or any later commit; `corrlog-inspect` 0.1.3 beyond
its presence as the secondary integration surface; key rotation/revocation (out of scope by
documentation); cross-OS behaviour; agreement with any third-party verifier; completeness of stored
history without an external checkpoint; regulatory compliance; factual correctness of corrections;
AI-system safety, fairness or accuracy; and any production-deployment or operational-security property.

### C. Material qualifications

1. **C7 is only partially supported**: malformed and truncated *signature* rejection was never judged by
   the independent verifier (T019/T020 invoked it without `--key`), so that arm rests on the SUT's own API.
2. **Verification material must come from the source**: the wheel ships no verifier; the verifier used is
   CorrLog-authored, so "independent" means outside the runtime, not independent of the author.
3. **No completeness guarantee**: history completeness is provable only against an externally trusted
   checkpoint; a dangling predecessor verifies as an individual record.
4. **Trust discipline is on the caller**: `verify(record)` without a supplied anchor returns True on
   embedded-key consistency; only `verify_trusted`/`--key` paths carry trust.
5. **Storage semantics are thin**: no uniqueness, no fsync, torn tails tolerated and reported, at-most-once
   admission in a local SQLite guard the caller must protect; SIGKILL did not naturally produce a torn tail.
6. **No rotation/revocation**: key lifecycle is entirely the operator's, with per-anchor verification only.
7. **Diagnostics are coarse**: schema, key and signature failures are indistinguishable to an operator.
8. **Evidence gaps to close before any unqualified claim**: T015, T017, T019, T020 (verifier arms), T030
   (signed self-reference), T035(b) (same-binary64 canonicalisation).
9. **Delivery integrity**: the ledger's completion hashes do not match the delivered report and pack; the
   pack's top-level manifest is stale (disclosed); several test folders lack the register's required
   per-test command/stdout/exit artefacts.

### D. Defects

**No CorrLog product defect is evidenced by this pack.** The two unmeasured corners (T035b, T030) are
open risks, not findings.

### E. Harness / evidence defects

Listed in full in §6 above; the load-bearing ones are the four mis-invoked verifier arms
(T015/T017/T019/T020), the T011 fixture overwrite, the T030 construction, the T035 fixture base value,
four stale per-test READMEs that contradict the executor report, and the ledger-to-delivery hash
mismatches.

### F. Supported external wording

The strongest statement this evidence objectively supports:

> On the pinned published `corrlog-core` 0.2.2 artefact, an independently executed adversarial
> validation measured that valid signed CorrLog records verify, that modifications to signed material
> after signing (single-field edits and single-byte mutations) are detected by both the library and a
> standalone verifier, that corrections carry verifiable predecessor links, that verification reproduces
> from exported evidence plus a trusted public key in an environment containing no CorrLog code and no
> private key, that records signed by a substituted key are refused under the genuine trust anchor, that
> malformed input fails deterministically rather than being silently accepted, and that originals remain
> distinguishable from later corrections. All verification material was hashed and re-verified before
> scoring; no product defect was found. Seven of the eight claim areas are supported and one
> (deterministic rejection of malformed signatures on the independent path) is only partly evidenced.

### G. Prohibited wording

Not supported by this evidence, and must not be used: "independently validated by a third party";
"tamper-proof", "immutable", "cannot be altered"; "proves the complete history of AI actions"; "detects AI
errors"; "guarantees corrections are correct"; "APRA/regulatory compliant"; "safe, fair or accurate AI";
"zero defects / fully audited"; "cross-platform verified"; "the verifier ships with the package"; "trust
is established by the signature alone"; "production ready"; and any statement that a valid signature
proves factual truth, completeness, compliance or model safety.
