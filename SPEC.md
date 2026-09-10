# Agent Correction Record: implemented v1 profile

## 1. Scope

CorrLog signs disclosures about actions, corrections and uncertainty. Ed25519
signatures bind canonical record content to a key. A trusted public key is required
for attribution. A signature does not prove the statement is true, that a referenced
source is correct, that an agent performed an action, or that all events were recorded.

JSONL files are untrusted transport/storage. They are not tamper-evident ledgers.
Insertion, deletion, reordering, truncation, substitution by another valid signed
record and replay are not detected by checking each record individually.

## 2. Record family and schema

The normative implemented schema is `corrlog_core/schema/acr-v1.json` (JSON Schema
2020-12). `verifier/acr-v1.json` is a byte-identical copy for offline distribution.
All constructors validate their output, and `verify` enforces the schema, including
RFC 3339 date-time format, before signature verification. Invalid constructor
arguments raise ValueError or a type/canonicalization error; no invalid record is returned.

Common required fields: correctionId (nonempty string), agent.id, principal.id and
principal.type, timestamp, and signature. Metadata is an optional object.

- Action roots: action.type, reason, trigger and fix.type; no supersedes. An empty
  reason is allowed for action receipts. Legacy roots omit kind; kind=action is allowed.
- Corrections: the action fields plus nonempty reason and supersedes containing the
  predecessor's receiptId and SHA-256 digest. kind=correction is optional.
- Uncertainty: kind=unknown and nonempty subject, optional note; no action, fix or
  supersedes. It can serve as a root when later corrected.

Triggers: supersede, check_failed, human_flagged, self_correction. Fix types: replace,
delete, rollback, noop, other. Optional fix.source has a type (schema, document,
database, api, human, other) and nonempty reference. A source is an assertion to
investigate, not independent proof. Unknown extension properties remain allowed and
are signed. Timestamps and identity strings are assertions, not externally attested facts.

## 3. Signing

1. Construct signature with alg=Ed25519, canonicalization=RFC8785, nonempty kid,
   publicKey (32 bytes, unpadded base64url), and sig="".
2. Canonicalize the entire object using RFC 8785: UTF-16 key ordering, UTF-8 strings,
   prescribed escapes and ECMAScript number formatting.
3. Sign these bytes using Ed25519 and store the 64-byte signature as unpadded base64url.

Nonfinite numbers and lone surrogates are rejected. Python integers outside
[-9007199254740991, 9007199254740991] are rejected: encode exact large integers as
strings. Finite floats are binary64 values; signatures bind their canonical value,
not the original spelling, whitespace or object-member order. Do not interpret this
as byte-for-byte integrity of an input JSON file. Duplicate JSON members must be
rejected at parsing; the standalone CLI does so. The dictionary API cannot recover
members already discarded by an upstream parser.

For historical compatibility, hashes of dictionary action arguments/results and
corrected content use canonical JSON; other content uses Python str(value).encode().
These auxiliary content hashes are not a language-neutral content serialization
contract. The whole record signature is independently verifiable.

## 4. Verification and trust

`verify(record, public_key=None)` returns False for malformed input, schema violations,
unsupported values, inconsistent embedded keys or invalid signatures. With no key it
checks only consistency under the supplied embedded key. It does not establish trust.
Use `verify_trusted(record, trusted_key)` for admission decisions; it rejects missing
keys. `load_public_key` decodes an unpadded base64url key but does not establish trust.
The key must be provisioned through an authenticated channel and bound to the expected
operator. kid is signed metadata, not a trusted key directory or authorization policy.

## 5. Correction chains and checkpoints

`verify_chain` requires a nonempty list starting with a root, valid signatures, unique
correctionIds, and every later record pointing to the immediate predecessor by both
ID and SHA-256 digest of the entire signed canonical record. This is a linear
correction chain, not a file-order chain of unrelated receipts.

Without a checkpoint a valid prefix passes. Complete-history verification requires a
separately trusted checkpoint {length, genesis, head} and a trusted public key. Genesis
and head are SHA-256 base64url digests of the first and last signed records. The
checkpoint binds the exact rooted sequence through its links. `chain_checkpoint`
only computes a description; it neither signs nor establishes trust in it. A trusted
producer must distribute it through an authenticated channel; consumers must retain
the latest expected checkpoint and prevent rollback. A checkpoint supplied by the
same untrusted transport as the chain cannot establish completeness or freshness.

Checkpoint verification detects insertion, deletion (including prefix/suffix),
reordering, substitution and duplicate insertion relative to that checkpoint.
It cannot detect undisclosed events, a malicious authorized signer, competing histories,
or replay of an entire previously valid chain without consumer state. No automatic
checkpoint service, witness, key rotation service or recovery protocol is provided.

## 6. Replay and storage

MemorySink rejects duplicate correctionIds and copies records at its boundaries.
JsonlSink is a permissive transport: it does not enforce schema, trust or uniqueness.
Its readers skip malformed JSON lines and expose damaged_lines. A successful read
must never be interpreted as successful security verification. There is no fsync
promise and no power-loss durability guarantee. Inspect uses this transport.

`corrlog_core.replay.ReplayGuard` verifies under a required trusted key and inserts
correctionId into a SQLite primary-key table transactionally. Across cooperating
consumers sharing that database, only one admission per ID succeeds, including across
restarts. Reuse of an ID with different signed content is rejected. SQLite errors
propagate; the consumer must fail closed. The database must be retained and protected
against deletion/rollback. This is at-most-once admission, not exactly-once business
processing. An admission committed before a consumer crash may leave work unprocessed.
Coordinate side effects and admission in an application transaction/outbox when needed.
Fresh-ID semantic duplicates and cross-domain replay require application-level event
identity and authorization. The guard is opt-in; Inspect receipt emission does not use it.

## 7. Compatibility and release boundary

0.2.1's nonconforming canonicalization produced signatures that this verifier may reject,
including records containing non-ASCII text. No silent legacy fallback is permitted.
Preserve original archives and their provenance. Any re-signing is a new attestation,
not proof that the old signature met RFC 8785. Schema enforcement also rejects previously
accepted malformed signed records. Evaluate this behavior change before release.

This format provides evidence artifacts, not regulatory certification, retention,
truthfulness, tamper-evident ledger integrity or automatic production readiness.
