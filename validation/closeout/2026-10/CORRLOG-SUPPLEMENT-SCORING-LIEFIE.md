# CORRLOG VALIDATION SUPPLEMENT — INDEPENDENT SCORING

**Scorer:** LiefieTango (independent; did not design, execute, modify or prepare any part of either phase)
**Date:** 2026-10-07
**Method:** read-only inspection of the delivered archive plus independent recomputation and source reading. No CorrLog API was executed, no test re-run, no artefact modified. Both archives re-hashed after scoring and byte-identical to as delivered.

---

## 1. INDEPENDENT VERIFICATION OF THE SUPPLEMENT

### 1.1 Archive SHA-256 — MATCH
`CORRLOG-VALIDATION-SUPPLEMENT.zip` = `de716e86598f902fa2ee6ab073e3286553ce07227977c1ed3c75dc58c8fa49eb` (recomputed; identical to the value supplied). 402 regular files, 573,048 bytes uncompressed.

### 1.2 SUT correspondence — CONFIRMED, re-measured by me inside the archive
| Material | Expected | Measured in the archive |
|---|---|---|
| `corrlog-core` 0.2.2 wheel | `232d6f66…b479b6ec` | MATCH |
| release-tag standalone verifier | `ace4c11e…414a0f7c` | MATCH |
| schema `acr-v1.json` (from inside the wheel) | `48bd9ad9…47e1137` | MATCH |
| trust anchor `trusted-signer.json` | `4bf83c53…19f5435` | MATCH |

Same wheel as the closed original validation, source tag `v0.2.2` = `393d8d90…`, development tree not used. Per-test `environment.json` files record the CorrLog-free verifier interpreter. **The supplement evaluates the same pinned published artefact as the original.**

### 1.3 Frozen registers — two, and both legitimate
- **v1** `52012d4d8c0ebe0c38913ab0862caf86fd454f5bddab649f3bb27d13a3cd3d93` — six tests S001–S006 with pre-registered expectations, and the invocation rule **"any exit 2 = NOT EXECUTED, never a rejection"**, which is exactly the discipline the original run lacked. Not altered by v2.
- **v2** `d9250caa2b9cf82ea294ef4aff541b146e215750f1a939fc996e74664bc5c8ee` — re-registers the same six tests under a revised evidence discipline, and supersedes v1 *for the evidence discipline, for S005's objective and for S006's fixture*, with the supersessions stated rather than applied silently.

**Assessment:** the v1→v2 change is a legitimate re-registration, not a post-hoc goalpost move, on three grounds. (i) S005's objective moved from "construct two self-reference fixtures" to "determine honestly whether the registered scenario is constructible at all, and do not manufacture a fixture for it" — a *harder* and more honest requirement. (ii) S006's fixture was corrected because v1's construction could not produce the registered pair; v2's expectation was weakened to "recorded as measured, not scored against a pre-chosen answer", which removes a scoring prediction rather than adding a claim. (iii) Most materially, **v1's S006 expectation was the stronger prediction and the measurement came out in its favour** (the same-binary64 variant still verifies), so no result was rescued by the rewording. Residual methodological note: v2's S006 pass rule is a *reporting* rule, so S006 is scored by me on the measurement itself, not on the executor's PASS.

### 1.4 Execution ordering — CONFIRMED by zip-internal timestamps (my own check)
| Time (UTC) | Event |
|---|---|
| 22:09:16 | workspace material, pinned wheel, cleanroom verifier/schema/anchor, baselines |
| 22:09:34 | **register v1 written** |
| 22:10:24–22:11:28 | first attempt executed (S001–S006), preserved separately |
| 22:11:50 | first-attempt execution report |
| 22:12:02 | first-attempt pack manifest + first-attempt ledger |
| **22:13:04** | **register v2 written** |
| 22:13:35–22:13:40 | **revised S001–S004 executed** |
| 22:14:19 / 22:14:22 | **revised S005 / S006 executed** |
| 22:15:50 | executor report |
| 22:16:10 | revised ledger |
| 22:16:16 | final inventory + manifest |

**Both registers precede every execution they govern.** The revised executions strictly follow v2's freeze. Ordering is sound.

### 1.5 Inventory / manifest integrity — MATCH, with one stale-authority trap
- `FINAL-FILE-INVENTORY-SHA256.txt`: I recomputed every listed member against the archive — **400/400 match, 0 mismatches, 0 not-found** (it excludes itself and the manifest).
- `SUPPLEMENT-SHA256-MANIFEST.txt`: **401/401 match** (it excludes only itself, and therefore pins the inventory too).
- `SUPPLEMENT-SHA256SUMS.txt` is **stale** — it is a working-directory checksum list from before the first attempt's evidence was moved to `evidence-attempt-1/`, so 26 of its entries no longer match the archive's files. It is superseded by the two files above and should not be used.
- **Stale-authority defect:** the revised ledger's "Clarification" block calls inventory `b3e0600a…` and manifest `130a6975…` "the authoritative values". Both are **wrong** (measured: inventory `50c4a20b…`, manifest `b3b35a2a…`). The executor report §7 additionally quotes a third stale value (`d3ea2ac8…`) inside a garbled sentence that says it is not being quoted. **Only the sidecar `CORRLOG-VALIDATION-SUPPLEMENT.zip.sha256` is correct**, and it matches my measurements exactly (archive `de716e86…`, report `8b84bc4d…`, inventory `50c4a20b…`, manifest `b3b35a2a…`). The executor's own final note does say earlier tables are historical, so this is churn rather than concealment — but the archived record contains at least three generations of self-referential hashes and a scorer must treat the sidecar as the sole authority.

### 1.6 Evidence preservation — STRONG
- Per-test folders verify: `SHA256SUMS` recomputed for S001–S006 → **148/148 match, 0 mismatches, 0 not-found**. Every command in each folder names a verifier input that is *inside that folder* and still present — the shared last-writer-wins export path that weakened the original pack (**my HD-3**) is eliminated.
- Every invocation carries exactly one of `--key` / `--signature-only`; **no invocation returned exit 2**; each `RESULTS.json` records `argparse_error: false` and `verdict_present: true`. **HD-1's cause is designed out rather than corrected after the fact.**
- The first attempt is preserved unaltered in `evidence-attempt-1/` with its own ledger and `NOTE.md`; the revised runs are new ledger rows. Nothing was deleted or overwritten.
- Harness failures are itemised in `harness-errors/DESCRIPTION.md`, including the one that matters most: the first attempt's S006 canonical sub-check called `rfc8785` directly, which raises `IntegerDomainError` for the literal, **so both comparison sides were empty and every variant compared "equal"** — a vacuous check, disclosed and superseded. Catching and disclosing that is a marker of integrity.
- **Original pack untouched:** `corrlog-validation-2026-10.zip` `8575ff3f…` and the delivery addendum `90172bd4…` both re-hash unchanged.
- One workspace divergence I found and resolved: `CORRLOG-VALIDATION-RUN-LEDGER.md` in the original *workspace* differs from the copy inside the original *pack*. Its mtime is `2026-10-07 21:19:29` — the same second the pack was built, ~50 minutes before the supplement began — and the extra block is the original pack's own append-only correction (excluding `env-*` directories) quoting `8575ff3f…`. It never mentions the supplement. **Not attributable to the supplement; a pre-existing original-phase wrinkle already disclosed in the delivery addendum.**

**Conclusion of section 1: the supplement's integrity claims all verify. Its one genuine weakness is hash bookkeeping inside its own ledger, where the sidecar — not the ledger — is the correct authority.**

---

## 2. SCORING S001–S006

### S001 — corrected T015: attacker-resigned record against the genuine anchor → **SUPPORTED**
Genuine anchor: verifier `exit 1`, `FAIL untrusted signer` (a real verdict, not a usage error). Attacker anchor: `exit 0`, `PASS valid under pinned key`, recorded as a configuration fact. Core under the genuine anchor: `verify(None)=true, verify(pub)=false, verify_trusted=false`; under the attacker anchor all true. I confirmed the fixture is genuinely attacker-signed (its `agent.publicKey` is the attacker key `kN52Yhf0…`, not the trusted `kYfDvEcu…`; the attacker-anchor run accepting it proves the re-signing is real) and that its content matches the baseline original apart from the signer identity and `correctionId` (see §5 note). No invocation returned exit 2.

### S002 — corrected T017: altered content validly re-signed by an untrusted key → **SUPPORTED**
I verified the `reason` field differs from the baseline correction ("… ceiling **ALTERED AND RE**…") and that the record carries the attacker public key. Genuine anchor: `exit 1`, `FAIL untrusted signer`. `--signature-only`: `exit 0`, `PASS signature consistency only; signer untrusted` — consistency explicitly not read as attribution. Core trusted: `False`. A written statement of the distinction (`CONSISTENCY-VS-ATTRIBUTION.md`) is preserved as the register required.

### S003 — corrected T019: malformed same-length signature → **SUPPORTED**
`signature.sig` replaced with a random base64url value; lengths measured 86 before and 86 after (same encoded length, so length checks cannot be what rejects it). Verifier `exit 1`, `FAIL invalid record, schema, key or signature`; core all false. Nothing silently accepted.

### S004 — corrected T020: truncated signature → **SUPPORTED**
Signature truncated 86 → 78 characters. Verifier `exit 1`, same verdict; core all false.

### S005 — corrected T030: constructibility of a cryptographic self-reference → **SUPPORTED** (determination delivered and independently verified)
I verified S005's work rather than accepting it, and it holds:
- **The code citations are exact.** I read the pinned wheel myself: line 411 `prior_digest = _hash_object(canonical_json(prior_record))`, line 290 `def _hash_object(data)`, line 536 `payload = {**record, "signature": {**sig_meta, "sig": ""}}`, line 510 `sig_bytes = private_key.sign(canonical_json(body))` — every one found at the stated line. The verifier's own `_digest(record) = sha256(canonical_bytes(record))` agrees with the core's definition.
- **The structural argument is sound.** A record's digest is a function of its canonical bytes *including its own `supersedes` block*, so a record naming itself would have to satisfy `d(R) = SHA-256(canonical(R[supersedes.digest := d(R)]))` — a SHA-256 fixed point with the output embedded in its own input. The API additionally derives the digest only from a *distinct* prior record, so no call expresses it. **Infeasible, not merely unattempted.**
- **The measured attempt corroborates it:** five insert-and-remeasure iterations never converge (each iteration's computed digest differs from the value the record contains), and the two-record cycle attempt never closes across four iterations (both records continue to fail verification).
- **No lookalike was manufactured:** the hand-completed self-digest record is labelled as hand-completed and is evidence only that such a record fails (`exit 1`, core all false).
- **The separate subcase is correctly separated and I verified it directly:** `subcase-identifier-collision-successor.json` has `correctionId == supersedes.receiptId == "SAME-ID-0001"` (my own field read), it is validly signed and verifies alone (`exit 0`), and as history the chain [predecessor, successor] is refused — verifier `exit 1` with `PASS valid under pinned key / PASS valid under pinned key / FAIL duplicate ID`, core `{"verify_chain": false, "per_record_verify": [true, true]}`. That is an **identifier collision**, not a cryptographic self-reference, and it is refused as valid history by the duplicate-ID rule.

### S006 — corrected T035b: the same-binary64 spelling pair → **SUPPORTED**
I verified the fixture pair myself and confirm the collision is real:
- The two fixture files are both 942 bytes and differ in **exactly one byte**: offset 346, `2` → `3` — `"collide": 9007199254740992` versus `"collide": 9007199254740993`. Nothing else changed; **the `signature.sig` value is byte-identical between them**.
- Recorded fixture hashes match measured (`f5b70850…`, `bd362ef0…`).
- My own arithmetic, in plain Python and with no CorrLog code: `float(9007199254740992) == float(9007199254740993)` → `True`; IEEE-754 bit patterns identical (`4340000000000000`); `9007199254740992 == 2**53`; and `int(float(9007199254740993)) != 9007199254740993`.
- Preserved capture: both canonical signed payloads are 685 bytes with the identical SHA-256 `454a6592df1990fa…`; the verifier returns `exit 0` `PASS valid under pinned key` and the core returns all-true **for the variant with the original signature**.
- My static read of the pinned wheel explains why: `_jcs_number`/`_jcs_integer` convert a parsed integer to binary64 (`_jcs_double(float(n))`) before canonicalisation, so both literals canonicalise to one payload.
**The evidence establishes the documented collision.** The rejection half (genuinely different binary64 rejected) is also evidenced — attempt-1's two different-value variants both `exit 1` on both paths, corroborated by the original run's T035 cases (c) and (d). Note: v2's revised S006 dropped those variants, so that half rests on the preserved first attempt (labelled not-a-product-verdict by the executor) plus the original pack — reasonable, but not re-registered in v2.

---

## 3. RECONCILIATION AGAINST MY ORIGINAL C1–C8 SCORING

| Claim | My original score | Revised score | Why |
|---|---|---|---|
| C1 valid record verifies | SUPPORTED | **SUPPORTED** | unchanged; S001/S002 attacker-anchor and base runs add more valid-record verifications |
| C2 modification of signed material detectable | SUPPORTED | **SUPPORTED WITH QUALIFICATION** | S006 shows raw-byte/decimal-spelling changes within one binary64 are *not* detectable by design; the claim holds only at the canonical signed representation / semantic value level |
| C3 predecessor/supersedes linkage | SUPPORTED | **SUPPORTED** | the T030 scenario is now resolved (not constructible), and the ID-collision analogue is refused as history; the chain-mode-only limit (PL-1) stands |
| C4 verification independent of the AI runtime | SUPPORTED (scope-limited) | **SUPPORTED** (scope-limited) | unchanged; authorship/packaging qualification stands |
| C5 verify from exported evidence with trusted key | SUPPORTED | **SUPPORTED** (add caveat) | plus a new interoperability caveat on out-of-domain numeric literals (§4.3) |
| C6 untrusted/substituted key not accepted as trusted | SUPPORTED (two tests one-path-only) | **SUPPORTED, qualification REMOVED** | S001 and S002 now produce real verdicts on the independent verifier path |
| C7 malformed/invalid records fail deterministically | SUPPORTED (two tests one-path-only) | **SUPPORTED, qualification REMOVED** | S003 and S004 now produce real verdicts on the independent verifier path |
| C8 original distinguishable from corrections | SUPPORTED | **SUPPORTED** | unchanged; S005's subcase adds that a duplicate identifier is caught in chain view |

**Net effect: nothing in the supplement contradicts my original scoring, and the two claims that carried coverage qualifications (C6, C7) no longer do. One claim's wording must tighten (C2), and one new limitation is added (numeric-literal class / interoperability).**

### 3.1 Corrections to my own earlier scoring (self-caught, recorded)
1. **Original T030.** I previously scored T030 `SUPPORTS` on the strength of the executor's note, writing that "the signed self-referential record verifies as an individual record". I have now measured the fixture: `self-reference-by-id-signed.json` has `correctionId='SELF-REF-0001'` and `supersedes.receiptId='f2f363c0-9599-480c-b4e9-78ea6d0a940d'` — **it was never self-referential**. Only the hand-mutated fixture was, and it was rejected trivially on an invalid signature. T030's registered scenario was therefore **never constructed**; my correct score was INSUFFICIENT EVIDENCE, not SUPPORTS. S005 now resolves the scenario properly. Recorded with CorrectAgent.
2. **C2's wording.** My original C2 was stated as a bare SUPPORTED. Given the original pack's own T031/T032 evidence (reordered fields, whitespace and indent variants *all verify* by design) and SPEC's explicit warning that binary64 semantics are "not a guarantee of decimal-digit integrity", the qualification in §4.2 was already latent and should have been stated. Corrected here and recorded.

---

## 4. THE THREE SPECIFIC QUESTIONS

### 4.1 Do S001–S004 close the standalone-verifier gaps for T015, T017, T019, T020? **Yes — fully.**
Each of the four registrations required a verdict from the independent verifier that the original run never obtained (its invocations exited 2 on an argparse usage error). S001–S004 produce exactly those verdicts, on both paths, with fixtures preserved inside each test folder, explicit key arguments, and no exit 2 anywhere.

**Original qualifications that can now be removed:**
- From the T015/T017 findings: the statement that the trusted-anchor path never produced a verdict → **removed** (S001, S002).
- From the T019/T020 findings: the statement that malformed and truncated signatures were rejected on the core path only → **removed** (S003, S004).
- From the material-qualifications list: "four trust-anchor/malformed-signature tests ran on one path only" → **removed** as a live coverage gap.
- From the test tally: T015, T017, T019, T020 move from INSUFFICIENT EVIDENCE to EVIDENCE SUPPORTS EXPECTED OUTCOME.
- From C6 and C7: their "both paths" qualifications → **removed**.
**What cannot be removed:** HD-1 remains a true statement about the *original* pack. It is a defect of that closed artefact, remedied in coverage but not erased from its record — as the supplement itself states.

### 4.2 S005 / original T030 — my classification
The evidence supports the proposition: **the literal cryptographic self-reference registered in T030 is not constructible under the CorrLog 0.2.2 record format, because it requires a SHA-256 digest fixed point and cannot be expressed through the API.** I verified the digest definition and signature coverage line-by-line in the pinned source, and the measured non-convergence attempts corroborate it.

Applying the available labels to the **registered scenario**:
- **NOT CONSTRUCTIBLE AS REGISTERED — correct, and my classification.**
- *NOT APPLICABLE* — **rejected.** The scenario was applicable and well motivated; it was ill-posed as a fixture, not off-topic.
- *Unresolved test gap* — **rejected on the merits.** It is resolved by a structural impossibility argument plus a measured attempt; nothing further could be executed to close it.
- *CorrLog limitation* — **rejected for the literal scenario.** That the product cannot produce a hash fixed point is a property of SHA-256, not of CorrLog. (Separately, a real CorrLog limitation of a *different* kind is confirmed below.)
- *CorrLog defect* — **rejected.** No frozen expectation was contradicted and no safety property failed.

**The identifier-collision subcase must be kept strictly separate, and I keep it so.** It is constructible, validly signed, and it is *not* a cryptographic self-reference: the predecessor digest resolves normally to a distinct record and the collision is purely on the `receiptId` string. Its behaviour is that the successor verifies alone while `chain [P, X]` is refused with `FAIL duplicate ID`. Two consequences I record: (i) the duplicate-ID rule is what stops the collision being read as history, which is the mechanism the original register predicted; (ii) the *record alone* still verifies, which is the same shape as the known PL-1 boundary (linkage integrity is a chain-mode property) and is therefore a **product limitation**, not a defect.

### 4.3 S006 / binary64 collision, and what it does to C2

**Does the evidence establish it? Yes.** Independently confirmed by me at three levels: the fixtures differ in exactly one byte with the signature untouched; plain-Python arithmetic shows both literals are one IEEE-754 double; the preserved canonical payloads are byte-identical and the verifier accepts the variant; and the pinned source's number handling explains the mechanism.

**Revised score for C2: SUPPORTED WITH QUALIFICATION.**

The three levels must be distinguished precisely:
1. **Modification of raw JSON bytes / decimal spelling** — **not detected, and never claimed to be.** Reordering keys, changing whitespace/indentation/CRLF and re-spelling a number that maps to the same binary64 all leave verification passing (original T031/T032 as intended; S006 as the numeric instance). The signed object is not the file's bytes.
2. **Modification of the canonical signed representation** — **detected.** Any change that alters the canonical bytes invalidates the signature; the B-series, the canonicalisation series and S006's different-value variants all show this.
3. **Modification of the semantic binary64 value** — **detected.** Change the value and verification fails.
The new fact S006 establishes is where the boundary sits: the equivalence class is *not* "the same decimal number" but "the same binary64 value", and for literals at or beyond 2^53 that class spans **different decimal integers**. So a signature over a record containing such a literal commits to a double, not to the digits a reader sees. C2 is true as a statement about canonical/semantic content and false as a statement about the stored bytes or the written digits.

**Classification of S006: a combination, in this order of weight.**
- **Documented protocol limitation (primary).** SPEC.md states the collision explicitly, says a verifier may accept both spellings, and warns "This is not a guarantee of decimal-digit integrity. Use strings for exact decimal money, identifiers and large integer quantities." The product's signing side even refuses to create such a record (`_check_application_numbers`: "inexact application integer must be represented as a string", read from the pinned source). So the observed behaviour is the documented contract, not a deviation from it.
- **Specification / design weakness (real, and worth stating plainly).** The asymmetry is the weak point: the *signing* side refuses inexact integer literals, but the *verification* side accepts a mutated record containing one when the signature was made over the colliding spelling. A reader who assumes "signed" means "the digits are bound" is wrong for this class, and nothing in a verified record warns them. For an assurance artefact whose purpose is to bind content, the numeric domain deserves a much louder boundary than a paragraph in §2.
- **Interoperability concern (real, and new).** The `rfc8785` library called directly raises `IntegerDomainError` for `9007199254740992`; the product normalises into the binary64 domain first and then accepts. A third-party verifier that did not replicate that normalisation would refuse records the product accepts — a cross-implementation divergence in exactly the place where independent verification matters most.
- **Not an implementation defect.** The measured behaviour matches the documented contract, and the wheel's own docstrings describe the numeric domain deliberately rather than accidentally.

**Significance for assurance evidence — measured, not asserted.** In plain Python I confirmed these pairs share one binary64: `9007199254740992`/`9007199254740993`; `99999999999999999999`/`99999999999999999998`; `0.1`/`0.1000000000000000055511151231257827`; `4820.10`/`4820.1000000000000001`. Therefore:
- **Integers up to 9,007,199,254,740,992** are exactly representable, so ordinary integer money values are inside the exact range and their digits are effectively bound.
- **Integers above 2^53** collide with their neighbours — 64-bit identifiers, Snowflake IDs, nanosecond timestamps, large counters and ledger-style quantities of that magnitude are exposed if carried as JSON numbers.
- **Non-integer decimals** can be re-spelled within the same double — money with cents is only as safe as its decimal spelling if written as a number, and `0.1` versus a long spelling is a real example.
- **Mitigation is the documented one:** carry exact quantities (money, identifiers, counters, large integers) as **strings**. The original validation's use case in fact carries its identifiers and digests as strings, and its amounts live in externally-asserted evidence, so the exposure is a producer-discipline property rather than a defect in that particular package.

---

## 5. REVISED OVERALL VERDICT

### 1. Revised C1–C8
- **C1 SUPPORTED** — unchanged.
- **C2 SUPPORTED WITH QUALIFICATION** — true of canonical signed content and of semantic values; not true of raw bytes or of decimal digits within one binary64 equivalence class.
- **C3 SUPPORTED** — plus: the literal self-reference scenario is determined **not constructible**, and the identifier-collision analogue is refused as valid history.
- **C4 SUPPORTED** — verification outside the CorrLog runtime and without private keys; verifier is CorrLog-authored release-source code.
- **C5 SUPPORTED** — plus: an independent implementation using a strict JCS library may refuse records containing out-of-domain numeric literals without the product's normalisation.
- **C6 SUPPORTED — qualification removed** (S001, S002 give real verdicts on both paths).
- **C7 SUPPORTED — qualification removed** (S003, S004 give real verdicts on both paths).
- **C8 SUPPORTED** — unchanged.

### 2. Remaining unclosed gaps
1. **Cross-OS behaviour** — still untested; the supplement is single-host (the original run's Python 3.11 interpreter check stands as the only environment diversity).
2. **Independently implemented third-party verifier** — still not demonstrated; the verifier is CorrLog-authored. S006 sharpens this: the one reference library consulted *disagrees* on out-of-domain numeric literals.
3. **Verifier distribution** — the standalone verifier is still not shipped in the published wheel.
4. **Key rotation / revocation** — absent from 0.2.2 (NOT APPLICABLE, not a gap to close).
5. **S006's rejection half** — the two genuinely-different-binary64 variants were exercised in attempt-1 (preserved, explicitly not counted as product verdicts) and in the original run's T035 (c)/(d), but were dropped from the revised v2 fixture set; a future re-registration would close this cleanly.
6. **Torn tail** — still rests on manual truncation, not a naturally reproduced crash.
7. **Completeness** — still only provable against an independently trusted checkpoint.
8. **Supplement hash bookkeeping** — the ledger's "authoritative" hashes are wrong and only the sidecar is right; a scorer must know that, and the closed record should carry one unambiguous authority.

### 3. CorrLog product defects evidenced — **none**, in either phase.
Every registered expectation that was actually exercised by a correctly constructed fixture was met. The three items that looked like contradictions in the original phase — the four exit-2 invocations, T030, and T035b — are all harness or fixture defects, and S001–S006 now demonstrate the underlying behaviours properly. No product contradiction occurred in the supplement.

### 4. Material protocol / product limitations (current list)
Record-level linkage is not resolved (dangling or circular references pass as individual records; chain/checkpoint mode is required) · completeness is checkpoint-relative · trust derives entirely from the supplied anchor · the verifier is CorrLog-authored and not shipped in the wheel · no cross-OS evidence · no rotation/revocation in 0.2.2 · the JSONL sink has no uniqueness guarantee and replay protection is opt-in with protected state · verification diagnostics collapse into one generic verdict string · no naturally produced torn tail · **and new: decimal-digit and out-of-domain numeric integrity is not protected by the signature — exact quantities must be carried as strings, and a strict third-party verifier may refuse such literals.**

### 5. Does VALIDATED WITH QUALIFICATIONS change?
**No — the verdict stands, and it stands stronger.** All four coverage gaps that qualified the original scoring are closed, the T030 scenario is resolved by a verified structural determination, the T035b fixture is replaced by the correct registered pair, no product defect was found in either phase, and the supplement's execution discipline (pre-registered expectations, per-test self-contained evidence, no exit-2-as-rejection, preserved failed attempts, disclosed vacuous check) is materially better than the original phase's. What changes is the *shape* of the qualification set: one dimension shrinks (coverage), and two refine (C2's wording, and the numeric-literal/interoperability boundary).

### 6. Strongest defensible technical claim after the supplement
> CorrLog 0.2.2 — the pinned published wheel, verified byte-identical to its release tag — provides signed, canonically-serialised records that verify cryptographically against a supplied trusted public key, and correction records that link to earlier records through a predecessor digest covering the predecessor's entire canonical bytes. Any change to the canonical signed representation, or to a signed semantic value, is detected: eight signed-field mutations, in-place byte mutations, malformed and truncated signatures, corrupted structure and substituted signing keys are all refused deterministically on both the core path and the release-source standalone verifier, with negative controls accepted in the same runs. Attribution is bound to the supplied anchor, and a record signed by a substituted key is refused by the genuine anchor while a consistency-only check explicitly declines to claim attribution. Records and their corrections remain separately identifiable; a duplicate identifier is refused as history; and a literal cryptographic self-reference is structurally impossible in this format, requiring a SHA-256 fixed point inexpressible through the API. Evidence exported from a producing environment verifies in a CorrLog-free environment with no private key present. Documented and material limits: the signed object is the canonical form, not the file's bytes — so benign re-spellings verify, and for numeric literals at or beyond 2^53, or non-integer decimals, the signature binds a binary64 value rather than the written digits, which is why exact money, identifiers, counters and large quantities must be carried as strings; linkage and completeness are chain/checkpoint properties, not per-record ones; trust derives solely from the supplied anchor; and the verifier is CorrLog-authored release-source code, not an independently implemented third party.

### 7. Wording that must now be prohibited or qualified
**Prohibited (carried over):** APRA/regulatory compliance · "detects AI errors" · a valid signature proves content true, accurate, fair or safe · history complete without an independently trusted checkpoint · tamper-proof / immutable / tamper-evident ledger · independently implemented third-party verification or cross-OS verification · rotation/revocation support · "zero defects, fully validated".
**Prohibited (new from this phase):**
- "**Every** modification to a signed record is detectable", or any claim that the signature covers the stored bytes. Correct wording: it covers the canonical signed representation and the signed semantic values.
- Any claim that **decimal digits are protected** where a value is carried as a JSON number: for integers at or above 2^53 and for non-integer decimals, two different spellings can verify under one signature.
- Any claim that a **third-party verifier will reproduce CorrLog's verdicts without reimplementing its number normalisation** — the `rfc8785` library refuses a literal the product accepts.
- Any claim that **the supplement's ledger carries the authoritative artefact hashes**: the ledger's values are wrong; the sidecar is authoritative.
**Must now be qualified rather than repeated:** "all 55 tests passed" (four of them are now understood as not-executed and are superseded by S001–S004), and the original C-series and E-series summary counts, which overstate their own evidence (HD-8 — unchanged in the closed pack).

### 8. Can the internal technical validation phase now be considered closed?
**Yes, for the internal technical validation phase as scoped — with three conditions, and with one thing it does not mean.**
- The three coverage defects carried by the original pack are resolved: the four exit-2 invocations are superseded by correctly-invoked re-executions on both paths (S001–S004); the mis-constructed collision fixture is replaced by the exact registered pair (S006); and the unconstructed T030 scenario is resolved as structurally impossible with a byte-level verified argument and a separately-labelled constructible analogue (S005).
- No CorrLog product defect is evidenced across either phase, every registered expectation that was exercised was met, and the remaining items are *scope* limits (cross-OS, independent third-party implementation, verifier packaging, rotation) rather than unexecuted tests.
- **Condition one:** C2 must be restated in the canonical/semantic form before this validation is cited externally, and the numeric-literal boundary must be published with it.
- **Condition two:** the S006 interoperability divergence should be recorded in the product's own documentation or release notes as a known boundary, because it determines whether an independent implementer can verify CorrLog records.
- **Condition three:** the supplement's hash bookkeeping should be corrected so that the closed record names one authority (the sidecar) rather than three generations of conflicting values.
- **It does not mean** that R1 or any owner-level closure has been granted, that the validation covers the development tree or any artefact other than the pinned wheel, or that CorrLog is production ready, secure or compliant. Closure of an internal technical validation phase is not a product release decision, and only the owner closes R1.

---

*Prepared by LiefieTango as independent scorer. Read-only throughout: no CorrLog API executed, no test re-run, no artefact in either archive modified — both archives re-hashed after scoring and byte-identical to as delivered. All digests, fixture diffs and code citations reported here were recomputed or re-read by me.*
