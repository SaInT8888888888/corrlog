<!-- Historical evidence, preserved as reviewed. This report describes revision
     22b1f88 (repair branch remediation/lifecycle-fix, base a683162), which was
     reviewed independently and then reconciled into the current revision 4e00708.
     It is the record of that repair, not a description of the current revision.
     The current revision is described in RELEASE_READINESS.md at the repo root. -->

# CorrLog lifecycle repair — 10 September 2026

## Decision

The remaining numeric round-trip defect has been repaired locally. This is a
review candidate, not release approval. The repaired branch still requires an
independent review and its own complete cross-platform CI run before publication.
No merge, push, tag or publication was performed for this repair.

Base: `a683162e1d97610c2f939832de288fccfaccb266` (PR #6 candidate).
Repair branch: `remediation/lifecycle-fix`. The accompanying manifest identifies
its exact commit and package hashes. All evidence below belongs to this repair
unless explicitly marked historical.

## Defect and repair

The preceding candidate accepted and signed finite floats whose shortest canonical
integer spellings it subsequently rejected. Three finite RFC 8785 Appendix B cases
failed the signed-record round trip. A seeded 100,000-draw exercise found 687
codec-closure failures among 99,958 finite numbers on that candidate.

For example, binary64 `float(2**68)` serializes as `295147905179352830000`.
That shortest decimal spelling parses to the original binary64 even though it is
not the float's exact mathematical integer. Requiring exact integer conversion
when verifying received JSON therefore rejected legitimate canonical data.

The core codec and independent verifier now interpret received JSON numbers as
finite binary64 values. Constructor admission separately rejects Python integers
that would lose precision, including nested metadata and dictionary inputs hashed
into records. The independent verifier also normalizes nested Python tuples as
JSON arrays, consistently with the core.

This is an explicit numeric contract, not arbitrary-precision integrity: two
literals that map to the same binary64 may verify under the same signature.
For example, 9007199254740992 and 9007199254740993 map to the same binary64.
A regression test demonstrates this boundary, different-binary64 tamper rejection,
and exact string tamper rejection. Use strings for exact quantities or identifiers.
The constructor guard cannot recover precision already lost upstream.

## Validation

Results are recorded in the accompanying evidence bundle, including commands,
interpreter dependency inventories, individual logs and synthetic signed fixtures.
Local execution is macOS with Python 3.12. Platform CI for the preceding candidate
is historical; it does not certify this changed code.

| Gate | Repair evidence |
|---|---|
| Full source suite | 160 passed |
| Fresh installed-wheel suite, with no package source in the test tree | 160 passed |
| Published JCS fixture files | 6 byte-exact matches |
| RFC Appendix B number expectations | 26 samples, including non-finite rejection |
| Finite RFC numbers through record/retract/unknown, serialization, verification, checkpoint and replay admission | 24/24 |
| Seeded numeric codec closure | 99,958 finite cases passed; 42 non-finite draws excluded from closure |
| Independent native JavaScript canonicalization comparison | 99,962 matches; zero mismatches |
| Random nested signed-record journeys | 1,000; ordinary and canonical JSON; both verifiers |
| Standalone CLI numeric fixtures | 10/10 normal/canonical files accepted under pinned key |
| Offline oracle | CorrLog absent; socket creation disabled; valid chain accepted, tamper, wrong signer, malformed records and checkpoint truncation rejected |
| Fresh installations | Core and Inspect wheels; independent oracle; Inspect without core; legacy 0.2.1; dependency checks clean |
| Real Inspect CLI | Three forced-failure samples emitted three signed receipts; subject references preserved |
| Adversarial suite | Malformed and schema-invalid records; pinned-key mismatch; duplicate IDs; replay admission including concurrent attempts; checkpoint insertion/deletion/reordering/truncation/substitution |

The JavaScript comparator is separate verification code using native JSON numeric
serialization and Node Ed25519 verification. Its fixture/signature exercise is
calibrated against six JCS files and all 26 Appendix B samples. It is not a second
human review, and randomized coverage is not exhaustive proof.

The historical core matrix remains 78/91 PASS, with 13 FAIL results preserved,
not relabeled as passes. They concern embedded-key self-verification, untrusted
or inconsistent timestamps, contradictory independently signed corrections,
JSONL deletion/reordering/truncation/malformed-line omission, freely rewritable
storage, duplicates stored in JSONL, and lack of automatic kid/agent identity
resolution. The Inspect matrix remains 9/10 PASS: its failed test expects a
hash-chained receipt file, which is expressly outside the current implementation.

These are real limitations. The scoped contract tests pass because they require
pinned keys, protected replay state and trusted checkpoints where appropriate;
they do not turn plain JSONL into a ledger. If the business requires any excluded
guarantee, that is additional implementation work, not a documentation waiver.

The Inspect test redirects only test data/cache paths into the workspace to
accommodate local filesystem restrictions. It runs the real CLI with a mock model;
it does not validate a live production model service or delivery under failures.

## Trust and deployment boundaries

- `verify()` without a pinned key establishes self-consistency only. Use
  `verify_trusted()` or the standalone verifier with an independently provisioned
  public key. A key carried in a record does not establish authority.
- Checkpoint-based completeness is relative to a separately trusted genesis,
  length and head. A checkpoint obtained from an attacker is not protection.
  Freshness, authorization and revocation are deployment responsibilities.
- `ReplayGuard` requires protected persistent state shared by the participating
  admission processes. Plain JSONL permits duplicate storage. State rollback,
  distributed exactly-once processing and semantic duplicates are not solved.
- Signatures bind canonical signed content, not truth, trusted time, delivery or
  proof that all events were disclosed. Inspect receipts are individual records,
  not a self-contained hash-chained history.
- 0.2.1 compatibility breaks remain. Preserve originals and trusted public keys.
  Re-signing is a new assertion, not repair of a historical signature. The release
  notes disclose Unicode, number serialization and schema-enforcement changes.

## Release gates still open

1. Review this precise code change independently, especially the binary64 numeric
   contract and its exact-value limitations.
2. Run all 12 CI combinations on this repair: Linux, macOS and Windows with Python
   3.10–3.13. Any change after review/testing needs checks appropriate to that change.
3. Approve the compatibility disclosure and release explicitly. Publish core 0.2.2
   before Inspect 0.1.3; then validate index installation. This report authorizes none
   of those external actions.
4. Before production reliance, test the actual integration's trust provisioning,
   checkpoint freshness, replay-state durability, delivery and recovery requirements.

There are no known failing tests of the locally tested, scoped per-record contract
in this repair. That is a bounded finding, not a general production-readiness claim.
0.2.2 is not yet cleared for publication. General production use is not certified.

## Exact safe website wording

> CorrLog creates signed records of disclosed AI actions and corrections. Verifiers
> can check signed canonical content against an independently trusted public key.
> Optional correction-chain checks use trusted checkpoints, and replay admission
> requires protected persistent state. JSONL storage does not guarantee a complete
> or immutable audit history. Signatures do not establish that a statement is true.

While this repair is unpublished, add:

> The corrected release candidate is under review. Published 0.2.1 has known
> canonicalization limitations; assess compatibility before relying on it.

## Exact claims to avoid

“Tamper-proof ledger”; “immutable audit trail”; “all deletions are detected”;
“automatic replay prevention”; “exactly-once delivery”; “complete AI history”;
“proves the AI was correct”; “trusted timestamps”; “independent verification needs
no trusted key”; “Inspect receipts are hash-chained”; “all existing signatures remain
valid”; “all decimal digits are protected as numbers”; “production-ready assurance”.

## Reproduction

Apply the included patch to the base commit, or inspect the supplied git bundle.
In a new environment, install build/test prerequisites and run:

```sh
python validation/run_current.py --work /absolute/new/validation-directory
```

On a restricted macOS host, add `--redirect-inspect-data`. The runner needs network
access for dependency installation. Its oracle verification phase forbids network
socket creation. The supplemental scripts and invocation record are in the evidence
bundle. Preserve the raw historical matrix failures when assessing results.
