# CORRLOG VALIDATION SUPPLEMENT — INDEPENDENT SCORING (Chilli)

**Scorer:** Chilli (independent scorer). **Date:** 2026-10-07. **Method:** read-only assessment of the
preserved artefacts; no CorrLog test, verifier or product code was run by me; I did not use the other
independent scorer's conclusions.

Artefact scored: `CORRLOG-VALIDATION-SUPPLEMENT.zip`
SHA-256 `de716e86598f902fa2ee6ab073e3286553ce07227977c1ed3c75dc58c8fa49eb` — **matches** the value given.

---

## 1. Package verification (done before scoring)

| Check | Result |
|---|---|
| Archive SHA-256 vs the value supplied | **MATCH** (`de716e86…`) |
| Sidecar `CORRLOG-VALIDATION-SUPPLEMENT.zip.sha256` | matches the archive and, inside itself, the executive report, the file inventory and the SHA-256 manifest |
| `SUPPLEMENT-SHA256-MANIFEST.txt` | lists **401 of 402** members (all but itself); **401/401 hash-match** |
| `FINAL-FILE-INVENTORY-SHA256.txt` | lists the **400** remaining members; **400/400 hash- and size-match**; covers the archive exactly (0 unlisted apart from the inventory and the manifest) |
| `SUPPLEMENT-SHA256SUMS.txt` | **STALE / MISMADE**: 212 entries, of which 168 match files under `evidence-attempt-1/` and 44 match files common to both trees; **0 entries describe the delivered revised tree as a whole**. `SUPPLEMENT-PACK-MANIFEST.md` describes this file as "hashes of every file packed here", which is not true |
| FINAL inventory header metadata | internally consistent for the 400 covered files, but "Archive size: 281505 bytes" does not describe the delivered archive (**305,100 bytes** on disk; 573,048 uncompressed across 402 members). The 400-file subtotal (447,693 bytes) is correct for the covered set; the header describes a pre-manifest archive |
| SUT correspondence | `sut/corrlog_core-0.2.2-py3-none-any.whl` = `232d6f66…` — **identical to the original pin**; `cleanroom/standalone.py` = `ace4c11e…` (release-tag verifier); `cleanroom/acr-v1.json` = `48bd9ad9…`; per-test `trusted-signer.json` = `4bf83c53…`. All re-verified by me against the delivered bytes |
| Frozen registers | v1 `52012d4d8c0ebe0c38913ab0862caf86fd454f5bddab649f3bb27d13a3cd3d93` and v2 `d9250caa2b9cf82ea294ef4aff541b146e215750f1a939fc996e74664bc5c8ee` — both **match the delivered files** and the values cited in the ledgers |
| Execution ordering | v1 frozen **22:09:45Z**; first attempt executed **22:10:24–22:11:28Z**; v2 frozen before the revised run; revised run **22:13:35–22:14:22Z**; archive built **22:16:17Z**. Registers precede their runs. v2 supersedes v1 for evidence discipline, S005's objective and S006's fixture, and **says so** |
| Evidence preservation | First attempt preserved at `evidence-attempt-1/` (with `NOTE.md`), its ledger `SUPPLEMENT-RUN-LEDGER.md` intact; harness problems itemised in `harness-errors/DESCRIPTION.md`; the revised run is a separate tree `evidence/S00x/` |
| Invocation discipline | **No preserved exit code in the revised evidence is 2**; no `argparse_error: true` and no `"exit": 2` in any `RESULTS.json`; every preserved command carries exactly one of `--key` / `--signature-only` |

**Integrity verdict: the package is scoreable.** Its substantive integrity chain (archive → manifest →
inventory → sidecar) is complete and self-consistent. Three documentation-level defects are noted in §6
(a stale `SUPPLEMENT-SHA256SUMS.txt`, stale intermediate completion hashes in the revised ledger, and one
ledger artefact-path that does not exist in the delivered tree).

## 2. S001–S006 scored

### S001 — attacker-resigned record vs the genuine anchor (C6) — **SUPPORTED**
Evidence: `evidence/S001/` — the fixture embeds the attacker key `kN52Yhf0…`; the preserved genuine-anchor
run `--key …/S001/trusted-signer.json …/verifier-input-attacker-resigned.json` returned
**`FAIL untrusted signer`, exit 1**; the attacker-anchor run returned `PASS valid under pinned key`, exit 0;
core under the genuine anchor `verify(None)=true, verify(pub)=false, verify_trusted=false`.
My own check: the record's Ed25519 signature **verifies under the attacker key and fails under the trusted
key**, computed with my own canonicalisation and signature verification — the fixture really is the attack
it claims to be.

### S002 — altered content validly re-signed by an untrusted key (C2, C6) — **SUPPORTED**
Evidence: `evidence/S002/` — the fixture's `reason` differs from the baseline correction's; genuine anchor
**`FAIL untrusted signer`, exit 1**; `--signature-only` → **`PASS signature consistency only; signer
untrusted`, exit 0**; core trusted `False`; the consistency-vs-attribution distinction is written into
`CONSISTENCY-VS-ATTRIBUTION.md`. My own check: signature valid under the attacker key, invalid under the
trusted key; the altered reason is exactly one field.

### S003 — malformed same-length signature (C7) — **SUPPORTED**
Evidence: `evidence/S003/` — `signature.sig` replaced at **identical length 86** (construction.txt records
86 → 86); preserved run **`FAIL invalid record, schema, key or signature`, exit 1**; core
`verify(None)=false, verify(pub)=false, verify_trusted=false`. My own check: the signature is 86 characters
long, differs from the baseline, and does not verify.

### S004 — truncated signature (C7) — **SUPPORTED**
Evidence: `evidence/S004/` — signature truncated **86 → 78** characters; preserved run
**`FAIL invalid record, schema, key or signature`, exit 1**; core `verify` all false. My own check: 78
characters, differs from the baseline, does not verify.

### S005 — constructibility of a cryptographic self-reference (C3, C8) — **SUPPORTED, with the split classification set out in §3**
Evidence: `evidence/S005/` — `STEP1-ANALYSIS.json` quotes the digest definition from the pinned code;
`STEP2-SELF-REFERENCE-ITERATIONS.json` (5 iterations, none a fixed point) and
`STEP2B-CYCLE-ITERATIONS.json` (4 iterations, cycle never closes); `STEP3-DETERMINATION.md`;
the hand-completed self-digest record → verifier exit 1; the identifier-collision subcase
(`subcase-identifier-collision-predecessor/successor.json`) → successor alone exit 0, chain `[P, X]` →
`PASS`, `PASS`, **`FAIL duplicate ID`** (exit 1), chain `[X, X]` → **`FAIL missing genesis`** (exit 1).
My own checks: the pinned wheel really does compute `prior_digest = _hash_object(canonical_json(prior_record))`
and sign `{**record, "signature": {… "sig": ""}}`; the subcase predecessor and successor are **both validly
signed** under the trusted key; the successor's `supersedes.receiptId` equals its own `correctionId`; and the
successor's `supersedes.digest` equals **my own independently computed digest of the predecessor**; the
record carrying its own digest is **not** a fixed point and fails verification (I reproduced iteration 1's
recorded digest exactly).

### S006 — the documented same-binary64 spelling pair (C2, C5) — **SUPPORTED; the claim is independently confirmed**
Evidence: `evidence/S006/` — `verifier-input-base-9007199254740992.json` and
`verifier-input-variant-9007199254740993.json`; both verifier runs exit 0 (`PASS valid under pinned key`);
core for both `verify(None)=true, verify(pub)=true, verify_trusted=true`; `STEP1-SPELLINGS-AND-BYTES.json`
and `RESULTS.json` record spellings, runtime values, canonical payload length 685 and SHA-256
`454a6592df1990fa43ef8c4c820b97dc…` for both.
**My own verification, from the delivered bytes:**
- raw spellings differ (`9007199254740992` vs `9007199254740993`), files differ, signature blocks are identical;
- the two values are the **same binary64** (bit-equal) but different Python ints;
- with the product's documented int→binary64 normalisation, **my own** canonicalisation of each record's
  signing payload yields **685 bytes and SHA-256 `454a6592df1990fa43ef8c4c820b97dc…` for both**;
- the trusted Ed25519 signature **verifies for both records**;
- without that normalisation the payloads differ (`657fcad0…`) and the signature **fails** for the variant.
So the supplement's headline is established, and the mechanism is exactly the number-domain normalisation.

## 3. Question 1 — do S001–S004 close the original T015/T017/T019/T020 gaps?

**Yes.** All four now have real cleanroom verdicts on the identical pinned artefact, with the verifier
inputs living inside each test's own folder, exit codes 1 / 1 / 1 / 1 (and one exit 0 for the
`--signature-only` control), and no exit 2 anywhere. My crypto-level checks agree with the recorded
fixtures and verdicts.

Qualifications that can now be **removed** from my original scoring:
1. From **C7**: "malformed and truncated signature rejection was never judged by the independent verifier
   (T019/T020 were argparse exit 2)" — removed by S003/S004.
2. From **C6**: "the trusted-anchor arms for T015/T017 produced no verifier verdict" — removed by S001/S002.
3. From the test-level record: T015, T017, T019, T020 move from INSUFFICIENT EVIDENCE to
   **EVIDENCE SUPPORTS the pre-registered outcome**.

Qualifications that **remain** and cannot be removed by this supplement: the verifier is CorrLog-authored
(C4/C5 are "outside the runtime", not third-party-implemented); the standalone verifier is not shipped in
the wheel; history completeness is provable only against an externally trusted checkpoint; `verify()`
without an anchor is consistency-only; diagnostic messages stay generic; cross-OS behaviour is untested;
and (new) the C2 numeric-domain qualification in §5.

## 4. Question 2 — S005 and the original T030

**Does the evidence support "the literal cryptographic self-reference registered in T030 is not
constructible under the CorrLog 0.2.2 record format because it requires a digest fixed point and cannot be
expressed by the API"? — Yes for the digest-level reading, and the evidence is sound:**
the predecessor digest is `SHA-256` over the predecessor's canonical bytes *including that record's own
`supersedes` block* (verified by me in the pinned wheel and in the verifier), so a record whose digest field
referred to itself would have to satisfy `d(R) = SHA-256(canonical(R[supersedes.digest := d(R)]))` — a
SHA-256 fixed point; and `retract()` derives the digest only from a distinct prior record, so no API path
expresses it. The measured attempts (5 single-record iterations, 4 two-record cycle iterations) never settle,
and the hand-completed carrier fails verification.

**Classification (my own, not the executor's):**
- **Literal cryptographic (digest-level) self-reference: NOT CONSTRUCTIBLE AS REGISTERED.** This is the
  right label. It is not "NOT APPLICABLE" (the scenario was meaningful and was addressed), and it is **not
  a CorrLog defect** — refusing to contain a digest of oneself is inherent to any hash-linked structure and
  is what keeps the chain acyclic. I also would not call it a *limitation* in the operational sense: no
  legitimate operator needs a self-referential record.
- **Identifier-collision subcase (X.supersedes.receiptId == X.correctionId, distinct predecessor record):
  CONSTRUCTIBLE and CONSTRUCTED**, validly signed (I verified both signatures), and refused as history
  (`FAIL duplicate ID` in a two-record chain, `FAIL missing genesis` when duplicated). It is correct that
  the supplement keeps this separated from literal self-reference — they are different objects, and the one
  that is constructible is the one the product refuses by duplicate-identifier rule.
- **The original T030 gap:** the closed pack's execution remains what it was (a fixture that was not
  self-referencing). The supplement supplies the substantive answer for the digest-level reading and a
  measured answer for the ID-level reading, so **the test gap is closed in substance**; what remains
  unmeasured is a *verifier verdict on a literal self-reference*, which cannot exist because no such record
  can be built.

## 5. Question 3 — S006 and its impact on C2

**Independently established: yes** (see §2 S006 for my own computation). Records differing only in the raw
decimal spelling `9007199254740992` / `9007199254740993` produce **identical canonical signed payloads**
(685 bytes, SHA-256 `454a6592…`) and the original signature verifies for both.

**Three levels, kept distinct:**

| Level | What changes | Detectable? |
|---|---|---|
| raw JSON bytes / decimal spelling | the file's literal text | **No** — the collision case is exactly this: bytes differ, signature still verifies |
| canonical signed representation | the RFC 8785/ES6 canonical form that is hashed and signed | **Yes** — any change here breaks the signature (T006–T013, T044: 28/28 arms rejected) |
| semantic binary64 value | the double the value maps to | **Yes** — a different binary64 produces different canonical bytes and is rejected (S006 variants `distinct→2` and `collide→9007199254740994`, both exit 1) |

**C2 verdict: C2 is SUPPORTED WITH QUALIFICATION.** C2 as originally worded — "modification of signed
material after signing is detectable" — is true only if "signed material" is read as *the canonical signed
representation*. Read at face value as "any modification of the record's bytes", the S006 collision is a
counter-example: two different source spellings are one signed value. The qualification is narrow (it needs
values that are distinct as JSON literals but identical as binary64) but it is precise and now measured.

**What S006 is, classified:**
- **not an implementation defect** — the pinned code implements the documented RFC 8785/ES6 number domain;
- **a documented protocol limitation** inherited from RFC 8785/JCS (JavaScript/IEEE-754 number semantics);
- **a specification/design weakness** in the sense that a signing format used for assurance evidence
  should not silently equate distinct decimal literals — but it is the *specification's* property, not
  CorrLog's deviation from it;
- **an interoperability concern, and the sharpest one in the pack**: the reference `rfc8785` library called
  directly raises `IntegerDomainError: 9007199254740992 exceeds safe integer domain for JSON floats`, and
  the product's verifier only succeeds because it normalises numbers into the binary64 domain first
  (`_to_double_domain`). Any third-party verifier built on the library without that identical normalisation
  will reject records the product accepts — a *verification-configuration* failure that looks like a
  signature failure.

**Significance for assurance evidence:**
- **Money:** safe while amounts stay exactly representable (integer-valued or within ~2^53 with a dyadic
  fraction); unsafe as a general assumption — a decimal such as `0.1` is already not exact, and two
  spellings that round to the same double are indistinguishable in the signed evidence.
- **Identifiers and counters:** a counter or an ID above 2^53 (9,007,199,254,740,992) can be silently
  normalised to a neighbouring value; an ID encoded as a JSON number is therefore not a reliable identity
  in signed evidence.
- **Large integer quantities:** distinct large integers can share one signed representation — exactly the
  S006 pair.
- **Recommendation that follows from the evidence:** carry exact quantities (money, identifiers, counters,
  large integers) as **strings** in signed records, or restrict numbers to values that are exactly
  representable as binary64 and pin that rule in the customer's own evidence contract. This is a
  documentation/consumer-control matter for the product's users, and it is not currently stated as a
  limitation in the material I scored.

## 6. Supplement harness / evidence / packaging defects (no product defect)

1. **`SUPPLEMENT-SHA256SUMS.txt` is stale and mislabelled** — 168 of 212 entries describe the first-attempt
   tree; 44 describe files common to both; none describe the delivered revised tree. `SUPPLEMENT-PACK-MANIFEST.md`
   asserts it holds "hashes of every file packed here". Use `SUPPLEMENT-SHA256-MANIFEST.txt` /
   `FINAL-FILE-INVENTORY-SHA256.txt` instead (both verify 100%).
2. **Stale "authoritative" hashes in the revised ledger** — its completion tables quote an inventory hash
   (`d3ea2ac8…`, `b3e0600a…`) and report hashes (`3e1f65ab…`, `566be51d…`) that do not match the delivered
   files (inventory `50c4a20b…`, report `8b84bc4d…`). The ledger's own append-only note says earlier tables
   are historical and the sidecar holds the authoritative values; the sidecar does match the delivered files.
3. **One ledger artefact path is wrong** — the S006 rows cite `CORRECTION-NOTE.md=218c7064…` and
   `rfc8785-direct-vs-normalised.txt=cfcbfc21…` as residing in `evidence/S006`; neither exists there (both
   are under `evidence-attempt-1/S006/`). The S006 *substance* is present in the delivered
   `evidence/S006/RESULTS.json` and `STEP1-SPELLINGS-AND-BYTES.json`, which I used.
4. **FINAL inventory header metadata** does not describe the delivered archive (281,505 bytes vs 305,100;
   400 files vs 402 members). The per-file coverage is complete; the header is confusing, not wrong about
   the files it lists.
5. **Two reports in one pack, only one of which is current** — `CORRLOG-VALIDATION-SUPPLEMENT-EXECUTION-REPORT.md`
   is the **first attempt's** report (v1 register, S005 presented as a successfully constructed ID-level
   self-reference, "six of six met the pre-registered outcome"), and
   `CORRLOG-VALIDATION-SUPPLEMENT-EXECUTOR-REPORT.md` is the revised report (S005 = NOT CONSTRUCTIBLE AS
   REGISTERED). Neither file states in its own text that the other exists or which is superseded; the
   reconciliation sits in the ledger, `evidence-attempt-1/NOTE.md` and `harness-errors/DESCRIPTION.md`.
   A scorer reading only the EXECUTION-REPORT gets the superseded story.
6. **Two fixture sets in the pack whose bytes differ** — `cleanroom/export/S00x/*` (first attempt) versus
   `evidence/S00x/verifier-input-*.json` (revised). Only the `evidence/` set is named by the revised
   commands. Not an integrity failure, but a scoring trap; I used only the files named by the preserved commands.
7. **Register supersession is disclosed, but v2 relaxes S006's pass rule** (from "the variant still verifies"
   to "measure it; not scored against a pre-chosen answer") after the first pass's canonical sub-check was
   found vacuous. No expectation laundering occurred on the substance: the collision was predicted in v1 and
   found, twice, and I confirmed it myself.
8. **First-attempt limitations recorded honestly**: the shared-export discipline (contrary to v2's rule), the
   `TypeError` that stopped the v1 S005 script, and the vacuous canonical sub-check are all preserved and
   labelled rather than deleted.

## 7. Revised overall verdict

### 7.1 Revised C1–C8

| Claim | Original verdict | Revised | What changed |
|---|---|---|---|
| C1 valid signed record verifies | SUPPORTED | **SUPPORTED** | unchanged; S001/S002/S006 add more verified records |
| C2 post-signing modification detectable | SUPPORTED | **SUPPORTED WITH QUALIFICATION** | S006: spelling-only changes of a number are not detectable; C2 holds for the canonical signed representation |
| C3 correction references an earlier record | SUPPORTED | **SUPPORTED** | S005 corroborates: ID-level self-reference is refused as history; no chain arrangement accepts it |
| C4 verification independent of the producing AI system | SUPPORTED | **SUPPORTED** | unchanged; scope caveat (verifier is CorrLog-authored) remains |
| C5 verify from exported evidence + trusted key + verifier | SUPPORTED | **SUPPORTED** | unchanged; new numeric-domain scope added by S006 |
| C6 untrusted/substituted key not accepted as the trusted signer | SUPPORTED | **SUPPORTED** | the T015/T017 verifier-evidence gap is now closed by S001/S002 |
| C7 malformed/invalid records fail deterministically | PARTIALLY SUPPORTED | **SUPPORTED** | S003/S004 close the malformed/truncated signature arms with real verdicts; the generic failure message remains a limitation, not a gap |
| C8 original distinguishable from later corrections | SUPPORTED | **SUPPORTED** | unchanged |

### 7.2 Remaining unclosed test gaps
- **None of the six supplement-covered gaps remains open** (T015, T017, T019, T020, T030-as-registered, T035b).
- **Still outside this evidence, from the original validation:** cross-OS behaviour (T054 was a second
  interpreter on one OS); agreement with a third-party-implemented verifier; history completeness without an
  externally trusted checkpoint; key rotation/revocation (documented as out of scope).
- **Residual inside S005:** there is no verifier verdict for a literal self-reference, because none can be
  constructed — a determination, not a measurement. Iterations 3–5 of the non-convergence have digest
  recomputation but no verifier run (fine for the fixed-point argument).

### 7.3 CorrLog product defects evidenced
**None** — in the supplement or, on this evidence, in the original validation. The S006 collision is
documented protocol behaviour, not a deviation from CorrLog's own specification. The previously classified
harness defects (four argparse invocations, the T030 fixture, the T035 fixture) remain harness/fixture
defects and are now corrected by S001–S006.

### 7.4 Material protocol/product limitations (buyer / auditor / engineer relevant)
1. **Numeric-domain collision (C2 qualification)** — distinct JSON numeric spellings can share one signed
   representation; exact values (money, IDs, counters, large integers) must be carried as strings or kept
   inside exactly-representable binary64.
2. **Interop hazard on the same point** — a third-party verifier using `rfc8785` directly throws on such
   literals; it must replicate CorrLog's `_to_double_domain` normalisation or it will report false failures.
3. **Verifier provenance** — the verifier is not in the wheel and is CorrLog-authored: "independent" means
   outside the runtime, not independent of the author.
4. **Completeness only against an externally trusted checkpoint** — a removed record is not detectable from
   the surviving records alone; a dangling predecessor verifies as an individual record.
5. **Trust discipline is the caller's** — `verify()` without an anchor is consistency-only (the supplement
   states this explicitly and measures it in S002).
6. **Store semantics are thin** — no uniqueness, no fsync, torn tails tolerated and reported;
   `ReplayGuard` is local and caller-protected.
7. **Diagnostics are coarse** — one generic failure message for schema, key and signature faults.
8. **No rotation/revocation facility** — per-anchor verification only.

### 7.5 Does the VALIDATED WITH QUALIFICATIONS verdict change?
**It improves, and it stays qualified.** The revised conclusion is:

**VALIDATED WITH QUALIFICATIONS (reduced qualification set).** Seven of the eight claims are now fully
supported and C7's gap is closed; the only claim-level qualification left is the newly *measured* C2
wording (canonical representation, not raw bytes), plus the standing scope qualifications (verifier
provenance, checkpoint-dependent completeness, no cross-OS or third-party-verifier evidence). I would not
move to "VALIDATED AGAINST THE FROZEN CLAIM SET" while C2 must be re-worded and while the numeric-domain
interop hazard is undocumented in the material I scored.

### 7.6 Strongest defensible technical claim after the supplement
> On the pinned published `corrlog-core` 0.2.2 artefact, an independently executed adversarial validation
> and its supplement show: valid signed records verify; modification of the canonical signed content is
> detected across single-field edits, 20 single-byte mutations and untrusted-key re-signing; corrections
> carry verified predecessor links; verification reproduces from exported evidence plus a trusted public key
> in an environment containing no CorrLog code and no private key; records signed by a substituted key are
> refused under the genuine anchor; malformed and truncated signatures are refused deterministically by the
> independent verifier as well as by the library; originals remain distinguishable from later corrections and
> no chain arrangement accepts a self-referential or duplicate-identifier record as valid history; and the
> package's own integrity chain (archive → manifest → inventory → sidecar) verifies in full. One measured
> caveat: two JSON numeric spellings that map to the same binary64 value are one signed value, so the
> signed evidence cannot distinguish them, and a third-party verifier must normalise numbers the same way.

### 7.7 Wording that must now be prohibited or qualified
- **Prohibited:** "any modification of a record can be detected"; "the signed evidence preserves the exact
  numeric value as written"; "the signature binds every byte of the record"; "zero defects / fully audited";
  "independently validated by a third party"; "complete history"; "APRA/regulatory compliant"; "detects AI
  errors"; "proves the correction is correct"; "safe, fair or accurate AI"; "cross-platform verified";
  "the verifier ships with the package"; "trust is established by the signature alone"; "production ready".
- **Must be qualified:** "tamper-evident" → say *tamper-evident with respect to the canonical signed
  representation*; "independent verification" → say *verification outside the CorrLog runtime, using the
  release-tag verifier*; "version 0.2.2 is validated" → say *validated on the pinned published wheel with
  the claim set and qualifications recorded, C2 as re-worded*.

### 7.8 Can the internal technical validation phase be considered closed?
**Yes, on the pinned artefact — conditionally.** The six registered gaps that the supplement existed to
close are closed with real verdicts on the identical pinned wheel, the evidence is integrity-verified, and
no product defect was found. I would close the phase once the following are recorded as outputs rather than
open issues: (1) C2 re-worded to the canonical signed representation with the binary64 qualification;
(2) the numeric-domain rule documented for users (carry exact values as strings; third-party verifiers must
replicate the number normalisation); (3) the pack's stale artefacts (`SUPPLEMENT-SHA256SUMS.txt`, the
superseded EXECUTION-REPORT, the two fixture sets) either corrected in a later delivery or clearly labelled
in the pack manifest; and (4) the residual scope limits (verifier provenance, checkpoint-dependent
completeness, no cross-OS, no third-party verifier) carried forward as stated limitations. Nothing in this
supplement justifies reopening the product's cryptography; the remaining work is wording, documentation and
delivery hygiene.
