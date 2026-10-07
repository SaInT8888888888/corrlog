# Validation evidence

`report/` contains the supplied historical validation reports and patch, not the
current release verdict. `harness/` derives from that handover. The core matrix has
minimal adaptations for constructors/sinks now rejecting invalid input and the
standalone verifier's location. Historical hard-coded FAIL assertions remain FAIL
and must be interpreted using the current release report, not counted as new passes.

The source tests include direct new regression gates for the corrected behavior.
`tests/test_release_security.py` tests actual core canonicalization against vendored
vectors and a seeded independent oracle, rather than testing a detached candidate.
No real production key is included: inspect-e2e/operator.seed is public test material.

See RELEASE_READINESS.md at the repository root for the current evidence and scope.

## Final closeout (October 2026)

The internal technical validation of the pinned 0.2.2 artefact is **CLOSED** with status
**VALIDATED WITH QUALIFICATIONS**. See [`../VALIDATION_STATUS-0.2.2.md`](../VALIDATION_STATUS-0.2.2.md)
for the final status, the per-claim outcomes (C1–C8), the authoritative C2 wording and the
binary64 numeric boundary.

Preserved evidence for the closeout lives in [`closeout/2026-10/`](closeout/2026-10/README.md):
the four independent scoring reports, the supplement hash sidecar, and the hashes of the three
immutable evidence packages (original executor submission, delivery addendum, validation supplement).

Stated plainly, so no reader over-reads the closure:

- the validation status is **VALIDATED WITH QUALIFICATIONS**;
- internal technical validation for the **pinned 0.2.2 artefact** is **CLOSED**;
- this **does not imply** production readiness, regulatory compliance or certification,
  complete correction history, or independently implemented third-party verification.

The supplement sidecar in the closeout directory is the authoritative supplement hash record. The
historical supplement ledger retains intermediate hash bookkeeping from its rebuild and those
intermediate values are not authoritative; the ledger has deliberately not been edited to hide them.
