# VALIDATION_STATUS-0.2.2.md

## Status

**CorrLog Core 0.2.2 — VALIDATED WITH QUALIFICATIONS**

Internal technical validation phase — **CLOSED**.

| Item | Value |
|---|---|
| Pinned wheel | `corrlog-core` 0.2.2 |
| Wheel SHA-256 | `232d6f6668f42fae70f869347cf6fc82003ceb0031299c4f1e29ccb9e479b6ec` |
| Pinned source / tag | `393d8d90d3977ce4b4b1ccf001a0b51c142c53db` (tag `v0.2.2`) |

The validated CorrLog 0.2.2 source is commit 393d8d90d3977ce4b4b1ccf001a0b51c142c53db, tagged v0.2.2. Current master is one documentation/evidence-only closeout commit ahead. The validated product files are unchanged between the tag and current master.

## Final claims

| Claim | Final status |
|---|---|
| C1 — a valid signed CorrLog record can be cryptographically verified | **SUPPORTED** |
| C2 — modification of signed material after signing is detectable | **SUPPORTED WITH QUALIFICATION** |
| C3 — a correction can cryptographically reference an earlier record through its predecessor/supersedes relationship | **SUPPORTED** |
| C4 — a verifier can validate the evidence independently of the AI system that produced the output | **SUPPORTED, scope-limited** |
| C5 — verification can be performed from exported evidence using the appropriate trusted public key and verifier | **SUPPORTED, with interoperability qualification** |
| C6 — records attributable to an untrusted or substituted signing key are not accepted as belonging to the trusted signer | **SUPPORTED** |
| C7 — malformed or cryptographically invalid records fail verification deterministically rather than being silently accepted | **SUPPORTED** |
| C8 — the original record remains distinguishable from subsequent corrections rather than being silently overwritten | **SUPPORTED** |

**No CorrLog product defect was evidenced by the closed validation or by the supplement.**

Both independent scorers returned **VALIDATED WITH QUALIFICATIONS** and converged on the qualification set.
Their reports are preserved under [`validation/closeout/2026-10/`](validation/closeout/2026-10/README.md).

## Authoritative C2 wording

> Modification that changes CorrLog's canonical signed representation or a signed semantic value is
> detectable. Distinct source representations that canonicalise to the same signed value are not
> cryptographically distinguishable.

## The binary64 boundary

CorrLog authenticates **canonical binary64 numeric values**. It does not authenticate every possible decimal
spelling of a number.

- Two decimal literals that map to the same binary64 value produce the same canonical signed bytes, so the
  same signature covers both. For example `9007199254740992` and `9007199254740993` map to one signed value.
- Consequences: a signature over one spelling verifies for the other, and a change between them is **not** a
  cryptographic modification under this format.
- Therefore encode **exact quantities — money, identifiers, counters, timestamps, large integers and similar
  values where every digit matters — as strings**, not as JSON numbers.

This boundary is described in `SPEC.md` and `SECURITY.md`. It is a documented property of the numeric
contract, not a defect.

## Qualification detail

| Area | Qualification |
|---|---|
| C2 | True of the canonical signed representation and of signed semantic values. Not true of raw JSON byte spelling, and not true of decimal digits that fall inside one binary64 equivalence class. |
| C4 | Demonstrated for verification **outside the originating CorrLog runtime**. The standalone verifier is CorrLog-authored code from the release source, so this does not demonstrate agreement with a separately implemented third-party verifier. |
| C5 | The standalone verifier is **not shipped in the published wheel**; an independent verifier must obtain it from the release source. Interoperability note: the `rfc8785` library called directly raises `IntegerDomainError` for literals such as `9007199254740992`, while CorrLog's verifier normalises numbers into the binary64 domain first. An implementation that skips that normalisation would fail to verify such records. |
| C1, C3, C6, C7, C8 | Supported as worded, with the scope limits stated below. |
| Key rotation / revocation | Not provided in 0.2.2; rotation and revocation are explicitly operator responsibilities per `SPEC.md` and `SECURITY.md`. |
| Cross-OS verification | Claimed by the release's own CI matrix; **not** independently verified in this validation. Only one operating system was available to the validator. |

## Hash authority

**The supplement sidecar is the authoritative supplement hash record:**
`validation/closeout/2026-10/CORRLOG-VALIDATION-SUPPLEMENT.zip.sha256`.

The historical validation supplement ledger contains intermediate hash bookkeeping written while the archive
was still being rebuilt. Those intermediate values are **not** authoritative, are retained as history, and the
historical ledger has deliberately not been edited to hide them.

| Immutable evidence package | SHA-256 |
|---|---|
| Original executor submission (`corrlog-validation-2026-10.zip`) | `8575ff3f9c71ff95da7900ae3974c438e904441ac53132bef553836e48a07c2e` |
| Delivery addendum (`CORRLOG-VALIDATION-DELIVERY-ADDENDUM.zip`) | `90172bd43d43b26cf978b1be37872ecc244f14ac072b014deea3bad9f2832eb1` |
| Validation supplement (`CORRLOG-VALIDATION-SUPPLEMENT.zip`) | `de716e86598f902fa2ee6ab073e3286553ce07227977c1ed3c75dc58c8fa49eb` |

The historical archives are not rewritten. Their bytes are preserved outside source control, and GitHub
records their hashes and the scoring reports rather than the archives themselves.

## What this status does NOT mean

Validation closure is a statement about evidence for the listed claims on the pinned artefact. It does not
mean, and must not be read as, any of the following:

- that CorrLog is production ready solely because validation is closed;
- that CorrLog is APRA compliant or certified by any regulator;
- that CorrLog detects AI errors itself;
- that a signed correction is factually true;
- that CorrLog proves model safety, fairness or accuracy;
- that the correction history is complete;
- that the JSONL store is an immutable or tamper-proof ledger;
- that every raw-byte modification to JSON is detected;
- that arbitrary decimal digit spellings are authenticated;
- that an independently implemented third-party verifier exists;
- that key rotation or revocation is supported in 0.2.2.

Scope limits and honesty boundaries elsewhere in this repository (`README.md`, `SPEC.md`, `SECURITY.md`,
`RELEASE_NOTES-0.2.2.md`) remain in force and are not relaxed by this document.
