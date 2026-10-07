# Validation closeout — 2026-10

Final independent scoring material for the internal technical validation of the pinned **CorrLog Core 0.2.2**
artefact. This directory is documentation and preserved evidence only: it contains no product code, and the
validated 0.2.2 artefact and tag `v0.2.2` are untouched by this closeout.

Status: **VALIDATED WITH QUALIFICATIONS** — see [`../../../VALIDATION_STATUS-0.2.2.md`](../../../VALIDATION_STATUS-0.2.2.md).

## Scoring reports

| File | Scorer | SHA-256 |
|---|---|---|
| `CORRLOG-INDEPENDENT-SCORING-LIEFIE.md` | LiefieTango (independent scorer, original phase) | `8295a8fac1112675031e0287c617573005ee3ef60ff263eb0fbb1de0fd79ae7b` |
| `CORRLOG-INDEPENDENT-SCORING-CHILLI.md` | Chilli (independent scorer, original phase) | `fe9baded304cb59ce9bddf4709c8f0935fdd91a07d787aeda4ba3952dae21eb2` |
| `CORRLOG-SUPPLEMENT-SCORING-LIEFIE.md` | LiefieTango (independent scorer, supplement phase) | `83ca5679fa87b338adbd9009a35423390b36a93942acb2b481b7f53bd313ef8a` |
| `CORRLOG-SUPPLEMENT-SCORING-CHILLI.md` | Chilli (independent scorer, supplement phase) | `83426bec55ad7c2d0504476789d23a00ca43b642aa833766f7a371778c22b52c` |

Both scorers returned **VALIDATED WITH QUALIFICATIONS** in both phases, converged on the qualification set,
and found **no evidenced CorrLog product defect**.

### Source of the placed reports (renames recorded, content unchanged)

Two reports were placed under the closeout naming requested for this directory. Their content is
**byte-identical** to the scorers' originals; only the filename differs, and the mapping is recorded here:

| Placed as | Copied from |
|---|---|
| `CORRLOG-INDEPENDENT-SCORING-LIEFIE.md` | `.hermes-liefietango/data/corrlog-scoring/CORRLOG-INDEPENDENT-SCORING.md` |
| `CORRLOG-SUPPLEMENT-SCORING-LIEFIE.md` | `.hermes-liefietango/data/corrlog-scoring/CORRLOG-SUPPLEMENT-INDEPENDENT-SCORING.md` |
| `CORRLOG-INDEPENDENT-SCORING-CHILLI.md` | `corrlog-scoring-chilli/CORRLOG-INDEPENDENT-SCORING-CHILLI.md` (name unchanged) |
| `CORRLOG-SUPPLEMENT-SCORING-CHILLI.md` | `corrlog-scoring-chilli/CORRLOG-SUPPLEMENT-SCORING-CHILLI.md` (name unchanged) |

Each copy was verified `cmp`-identical to its source at placement time.

## Immutable evidence packages

These archives are the frozen evidence of the validation. Their bytes are preserved outside source control.
This repository records their hashes and the scoring reports rather than adding the archives to source
control; the historical archives have **not** been rewritten.

| Evidence package | SHA-256 |
|---|---|
| Original executor submission — `corrlog-validation-2026-10.zip` | `8575ff3f9c71ff95da7900ae3974c438e904441ac53132bef553836e48a07c2e` |
| Delivery addendum — `CORRLOG-VALIDATION-DELIVERY-ADDENDUM.zip` | `90172bd43d43b26cf978b1be37872ecc244f14ac072b014deea3bad9f2832eb1` |
| Validation supplement — `CORRLOG-VALIDATION-SUPPLEMENT.zip` | `de716e86598f902fa2ee6ab073e3286553ce07227977c1ed3c75dc58c8fa49eb` |

The supplement's authoritative hash record is the sidecar file in this directory,
`CORRLOG-VALIDATION-SUPPLEMENT.zip.sha256` (SHA-256
`e0a7fff581ed5bdf9f03bde8ccd7f5917a7c579bcb21dea6b25577584cad3e0f`), which pins the archive and the
supplement's internal report, inventory and manifest.

## Hash authority

**The supplement sidecar is the authoritative supplement hash record.**

The historical supplement ledger contains intermediate hash bookkeeping written while the archive was still
being rebuilt. Those intermediate values are **not** authoritative and must not be treated as such. They are
retained as history and the historical ledger was deliberately **not** edited to hide them.

## What this closeout does not claim

Closure of internal technical validation does not mean, and must not be read as: production readiness,
regulatory compliance or certification, that CorrLog detects AI errors itself, that a signed correction is
factually true, that model safety/fairness/accuracy is proven, that the history is complete, that the JSONL
store is an immutable or tamper-proof ledger, that every raw-byte JSON modification is detected, that
arbitrary decimal digit spellings are authenticated, that an independently implemented third-party verifier
exists, or that key rotation/revocation is supported in 0.2.2.
