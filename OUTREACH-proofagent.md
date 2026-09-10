# ProofAgent integration: factual scope

The adapter converts governance verdicts into operator-signed correction records.
A consumer needs an independently trusted operator public key to verify attribution.
A signed verdict is an assertion, not proof of its truth. The adapter does not make
a JSONL file hash-chained or complete. Refer to RELEASE_READINESS.md before using
integration claims externally; this remediation does not retest live third-party
services beyond the specified Inspect CLI integration.
