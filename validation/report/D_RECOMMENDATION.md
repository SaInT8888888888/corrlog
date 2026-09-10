# Deliverable D: Recommendation

Date: 2026-09-10
Basis: 101 tests, 81 pass, 20 open. Full detail in deliverable A and the test
matrix in deliverable B.

---

## Verdict per public claim

| Claim you want to make | Ready today? | Notes |
|---|---|---|
| **Open source** | **Yes, with one condition** | The repository and license are in place. But the published `corrlog-core 0.2.1` on PyPI carries the canonicalization defect, so anyone who installs today and uses non-ASCII text gets records no conforming third party can verify. Ship the fix as 0.2.2 before pointing anyone at PyPI. |
| **Correction records** | **Yes, narrowly** | "Creates signed correction records" is proven (C1, 7 of 7). Do not claim "ACR schema compliant" until the schema is enforced: `record()` and `unknown()` output currently fails the project's own schema (C7-14, C7-15), and empty required fields verify (C7-13). |
| **Tamper detection** | **Only in the narrow form** | Per-record: proven, 27 of 27 alteration tests pass, including tamper tests on real Inspect receipts. Ledger-level: **not true**. Deleting, reordering, or truncating lines in the JSONL file leaves a file whose remaining records all verify (C5-02 to C5-06, C10-06). Say "modification of an individual record is detectable", never "tamper-evident log" or "tamper-evident ledger". |
| **Independently verifiable records** | **Yes, after 0.2.2 ships, with the precondition stated** | This was **false in practice** for non-ASCII content under 0.2.1 (proven: the third-party oracle rejects records that 0.2.1 accepts). With the fix, a verifier sharing no code with CorrLog, built on Trail of Bits' `rfc8785`, verifies real records offline under a pinned key. The precondition that must always be stated: verification is only a security property when the verifier pins a known public key. The unpinned form accepts any attacker-signed record. |
| **Inspect integration** | **Yes, narrowly** | A real `inspect eval` emits one signed receipt per failing sample; every receipt verifies under a pinned key; tamper detection works; receipts survive being moved to another machine; an unusable key or a missing core extra does not break the eval (C10-01 to C10-10). Do not claim "hash-chained receipts": the receipts file is not a chain and the superseded action record is discarded (C10-06). That claim has already been withdrawn from the source tree during this validation. |
| **Production use** | **No** | See below. |

---

## Why "production use" is a no

Five independent reasons, any one of which would be sufficient on its own:

1. **The ledger is not tamper evident.** The headline capability is absent at
   the file level. A client who deletes an inconvenient line from
   `corrections.jsonl` leaves a file that still verifies. This is the gap
   between the promise and the implementation.
2. **Replay and duplication are undetected.** The same receipt can be appended
   any number of times, and two different records may share one
   `correctionId`; lookups then return one of them silently.
3. **`verify()` and the published schema disagree.** `SPEC.md` 6.1 says the
   schema is checked first; it is never checked. Two of three public
   constructors emit records the bundled schema rejects.
4. **The secure path is not the documented path.** `SECURITY.md` documents the
   key-substitution hazard, but the README quick start demonstrates the
   unpinned `verify(record)` form that is vulnerable to it.
5. **The fixes are not released.** Everything in `corrlog-validation-fixes.patch`
   lives in an uncommitted working tree. Nothing in this report is true of the
   artifact a client can install from PyPI today.

---

## Priority order for closing the gap

Do these in order. Items 1 to 3 are small and close eight findings between them.

1. **Cross-check `supersedes.receiptId` against the predecessor's
   `correctionId`, and validate the timestamp format.** Closes C4-08, C9-03.
   Small, contained, no format change.
2. **Make pinning the documented default.** Change every quick-start example to
   pass the public key, and put the warning at the call site. Closes the
   documentation half of C2-02 and C9-06.
3. **Reconcile `verify()` with the schema.** Either validate against
   `schema/acr-v1.json` as `SPEC.md` says, or fix the schema and the
   constructors so all three agree. Closes C7-13, C7-14, C7-15.
4. **Decide the ledger question.** Either chain the ledger (each record commits
   to the previous record's bytes, so deletion and reordering are detectable),
   or stop calling the JSONL sink tamper evident and state plainly that the
   file is an untrusted transport. This closes C5-02 to C5-06 and C10-06, and
   it is the single change that most moves CorrLog toward its own pitch.
   Recommendation: chain it. The digest machinery already exists.
5. **Detect duplicates and replay.** A monotonic sequence number in the record,
   or a sink that refuses a `correctionId` it has already seen. Closes C6-01,
   C6-02, C6-04.
6. **Persist the superseded action record in the Inspect integration**, or drop
   `supersedes` from those receipts. A pointer that can never resolve reads as
   evidence of a chain that is not there.
7. **Release 0.2.2, then re-run this validation against the published artifact.**
   Everything here was measured against a working tree and a locally built
   wheel. The last mile is confirming the same numbers from PyPI.

---

## Suggested claim wording, once items 1 to 4 are done

Replace:

> A cryptographically signed, tamper-evident record of corrections to agent actions.

With:

> Cryptographically signed correction records. Each record is independently
> verifiable offline against a pinned public key by any RFC 8785 conforming
> verifier, with no CorrLog service in the loop. Modifying a record is
> detectable. Duplicate and replay protection requires
> [whatever item 5 produces]; until then, treat the JSONL file as an untrusted
> transport and verify every record individually.

That wording is defensible today, and it is honest about what the file does and
does not prove.

---

## What is genuinely strong

This should not get lost in the findings list. The core primitive is in good
shape, and it is stronger now than when the validation started:

- Sign and verify are deterministic and now anchored to the official RFC 8785
  conformance vectors and to a third-party oracle (6 of 6 vectors, 5,756 of
  5,756 fuzz cases byte-identical).
- Every single-field alteration tested is caught, across 27 alteration tests.
- A genuinely independent verifier, sharing no code with CorrLog, verifies real
  records offline. That claim is now demonstrated rather than asserted.
- The Inspect hook is genuinely well behaved under failure: bad keys, missing
  optional dependencies, and unreadable sinks never break an eval run.
- The durability contract for the JSONL sink (atomic single writes, partial
  trailing line tolerance, damaged line counter) is sound for what it claims
  to be, which is a file writer, not a ledger.

The problem is not the cryptography. The problem is that three of the four
capabilities the project markets sit on top of a file format that does not
provide the guarantees the marketing implies.
