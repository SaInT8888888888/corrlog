# Agent Correction Record (ACR) — v1.0

**Status:** Draft for implementation. This document defines version 1.0 of the Agent
Correction Record (ACR) format — a cryptographically signed, tamper-evident record of an
agent's *self-disclosed mistake and the corrective action taken*.

ACR is an **extension to the Agent Action Receipt (AAR v1.0)** specification
(`Cyberweasel777/agent-action-receipt-spec`). It does not compete with AAR; it layers
correction semantics on top of the receipt chain AAR already defines.

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**,
**RECOMMENDED**, **MAY**, and **OPTIONAL** are interpreted as described in RFC 2119.

---

## 1. Abstract

AAR records *what an agent did*. ACR records *what the agent later admits was wrong and
what it did to fix it*. Together they form a complete, verifiable audit ledger: successes
(receipts) and corrections (errata).

ACR enables an AI deployer to evidence the corrective-action and incident-reporting duties
imposed by the EU AI Act (Art 20 corrective actions, Art 26(5) monitor/suspend, Art 26(6)
log retention, Art 73 serious-incident reporting) and to align with NIST AI RMF MANAGE 4.3.

## 2. Motivation

Every production agent makes mistakes. Today those mistakes are either hidden or recorded in
ad-hoc, platform-specific, non-cryptographic logs. An auditor cannot distinguish "a system
that never erred" (impossible) from "a system that hid its errors." ACR gives an agent a
standard, signed way to disclose a correction, so the absence of corrections is meaningful —
and a signed correction is proof of disclosure, not proof of failure.

## 3. The key honesty rule: trigger, not confession

An LLM does **not** reliably detect its own mistakes. ACR therefore does **not** require an
agent to spontaneously confess. A correction record is written when a correction is
**detected** by one of four triggers:

| `trigger` value | Meaning |
|---|---|
| `supersede` | A newer write on the same canonical key replaced an older one. |
| `check_failed` | A deterministic validator / write guard / policy engine rejected an action. |
| `human_flagged` | A person marked a prior output as wrong. |
| `self_correction` | The agent itself detected the error (exists, but flagged as the weakest trigger). |

The agent's key signs the record in all cases (so "the agent self-disclosed" holds at the
cryptographic level), but the *trigger* is detection — deterministic or human — never an
LLM's unaided conscience.

## 4. Record format

An ACR record is a UTF-8 JSON object, signed with Ed25519 over canonical JSON
(JCS-sorted, no insignificant whitespace), consistent with AAR v1.0 §5.

### 4.1 Top-level fields

- `correctionId` (string, REQUIRED): globally unique identifier (UUID RECOMMENDED).
- `agent` (object, REQUIRED): identity of the correcting agent — same shape as AAR `agent` (`id`, `name`, `version`, `publicKey`).
- `principal` (object, REQUIRED): identity on whose behalf the correction is made — same shape as AAR `principal` (`id`, `type`).
- `supersedes` (object, REQUIRED): the record being corrected.
  - `receiptId` (string, REQUIRED): the AAR receipt id, or ACR correction id, being amended.
  - `digest` (object, REQUIRED): SHA-256 hash of the superseded record's canonical bytes, in AAR `hashObject` shape (`alg`, `digest`).
- `action` (object, REQUIRED): the corrected action.
  - `type` (string, REQUIRED): semantic label, e.g. `memory.write`, `api.call`, `payment.execute`.
  - `target` (string, OPTIONAL): resource URI/route/contract.
- `reason` (string, REQUIRED): why the correction is made (the validation error, the human note, the contradiction).
- `trigger` (string, REQUIRED): one of `supersede | check_failed | human_flagged | self_correction`.
- `fix` (object, REQUIRED): the corrective action.
  - `type` (string, REQUIRED): `replace | delete | rollback | noop | other`.
  - `contentHash` (object, OPTIONAL): SHA-256 of corrected content (privacy-preserving — raw content SHOULD NOT be embedded).
  - `note` (string, OPTIONAL): human-readable description of the fix.
- `timestamp` (string, REQUIRED): RFC 3339 correction timestamp.
- `signature` (object, REQUIRED): same shape as AAR `signature` (`alg:"Ed25519"`, `kid`, `publicKey`, `canonicalization:"JCS-SORTED-UTF8-NOWS"`, `sig`).
- `metadata` (object, OPTIONAL): extension bag.

### 4.2 Chain semantics

An ACR record links to the record it supersedes via `supersedes.digest` (a content hash, not
just an id). This forms a hash chain: `receipt → correction → correction-of-correction`,
verifiable without trusting the storage layer. Verifiers MUST verify the `supersedes.digest`
matches the referenced record's canonical bytes.

## 5. Signing

Identical to AAR v1.0 §5: Ed25519 over canonical JSON (keys sorted lexicographically,
`signature.sig` removed, no whitespace, UTF-8). `signature.canonicalization` MUST be
`JCS-SORTED-UTF8-NOWS`.

## 6. Verification

1. Validate the record against the schema.
2. Recompute canonical bytes (remove `signature.sig`), verify the Ed25519 signature with the
   key resolved by `signature.kid`.
3. If `supersedes.digest` is resolvable, verify it matches the referenced record.

## 7. Relationship to other standards

- **AAR v1.0** — the receipt layer ACR extends. ACR reuses AAR's agent/principal/signature
  shapes and canonicalization.
- **Microsoft agent-governance-toolkit** — ships Ed25519 receipts with SHA-256 hash chaining
  but is append-only by design; it has no errata/amendment record type. ACR provides the
  missing correction semantics as a compatible layer.
- **IETF draft-mih-sato-agent-accountability-composition** — the four-leg CAN/WHO/WHAT/AUDIT
  accountability composition. ACR is complementary: that draft audits authorization, ACR
  records correction.

## 8. Compliance mapping (what ACR evidences, honestly)

ACR *supports* — it does not certify — the following duties, for systems in scope of the
EU AI Act:

- Art 26(5) deployer monitor/suspend-and-inform → a signed `check_failed`/`human_flagged` correction.
- Art 26(6) log retention ≥6 months → the append-only, hash-chained ledger.
- Art 20 corrective actions + duty of information → the `fix` + `reason` fields.
- Art 73 serious-incident reporting (≤2/10/15 days) → timestamped correction records.
- NIST AI RMF MANAGE 4.3 / 4.1 / GOVERN 4.3 → incident tracking and documentation.

ACR MUST NOT be marketed as "certifying" or "guaranteeing" EU AI Act compliance, and MUST NOT
be described as satisfying Art 12 (automatic event logging), which is a distinct provider
duty for high-risk systems.
