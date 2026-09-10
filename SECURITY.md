# Security and trusted verification

Use `verify_trusted(record, trusted_key)` for a trust decision. Provision the expected
operator public key over an authenticated channel before receiving records. Bind the
key to an operator and permitted agent/principal identifiers in application policy.
Verify its fingerprint with the operator through an independent authenticated channel.
Store the key in configuration an attacker supplying records cannot modify. Never
copy a received record's embedded key into the trusted-key configuration.

`verify(record)` is a compatibility API for schema and signature consistency only.
Anyone can create a key pair and produce a record that passes that check. Signatures
attribute assertions to a key, not automatically to a human, model, or organization.
A pinned operator can still assert false agent IDs, reasons, sources and timestamps.

The standalone CLI requires `--key trusted-key.json`, or an explicit
`--signature-only` opt-out from trust verification. It imports no corrlog code and
uses the third-party rfc8785 library. The bundled schema is shared format data;
independence of verification code is not independence of the specification or trust policy.

Protect private keys and define rotation/revocation outside CorrLog. Retain old public
keys with an authenticated policy describing which historical records they authorize.
There is no built-in revocation service, secure clock, key discovery or time-of-signing
proof. A stolen trusted signing key can produce accepted false records.

## Completeness and replay

JSONL storage has no ledger-integrity guarantee. Per-record signatures do not detect
missing lines, reordered lines or replacement with other valid signed records.
Correction-chain verification checks a rooted linked sequence. A trusted checkpoint
and pinned key are necessary to detect suffix truncation relative to an expected head.
Checkpoint freshness and anti-rollback state are the consumer's responsibility.

ReplayGuard provides persistent unique-ID admission through a protected shared SQLite
database. It is optional and not used automatically by JSONL or Inspect. Do not delete,
restore or independently duplicate this state and expect replay protection to persist.
There is no exactly-once side-effect guarantee or semantic deduplication of fresh IDs.

## Input and operational limits

Verification rejects malformed dictionary inputs without raising. The standalone JSON
reader rejects duplicate members and nonfinite constants. Applications parsing JSON
before invoking dictionary APIs must reject duplicate members themselves. Enforce
request size/depth and resource limits outside this library; unbounded hostile inputs
can exhaust CPU or memory. Schema extensions are allowed and signed.

Inspect hook failures are logged and do not fail the evaluation. enabled() indicates
configuration and import availability, not guaranteed receipt delivery. Monitor errors
and reconcile expected samples externally. Inspect retains signed subject_ref metadata,
but does not persist the superseded action record; its receipt file is not a chain.

## Legacy data

Version 0.2.1 used non-RFC-8785 serialization. Updated verification intentionally does
not silently accept those nonconforming signatures. Preserve legacy evidence and label
its verification method explicitly. Do not overwrite history with re-signed records.

Report suspected vulnerabilities privately to the maintainer where possible; avoid
publishing exploitable details before a fix is available.

## Numeric precision boundary

Verification interprets JSON numbers as binary64 values. Different decimal literals
can map to the same numeric value and therefore the same signature. This applies to
any RFC 8785 consumer using binary64 semantics. Sign exact money, account IDs and
large integer quantities as strings when preserving every digit matters. Constructors
reject inexact Python integer inputs before signing, but cannot recover precision
already lost by conversion to float or by an upstream JSON parser. This input guard
must not be applied to parsing canonical output: shortest decimal spellings are not
necessarily exact mathematical representations of the underlying binary64.
