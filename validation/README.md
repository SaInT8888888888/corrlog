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
