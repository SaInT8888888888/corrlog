# Agent Correction Record (ACR) — v1.0

**Status:** Draft for implementation. This document defines version 1.0 of the Agent
Correction Record (ACR) format — a cryptographically signed, tamper-evident record of a
*correction to a prior agent action, plus the corrective action taken*.

ACR is an **extension to the Agent Action Receipt (AAR v1.0)** specification
(`Cyberweasel777/agent-action-receipt-spec`). It does not compete with AAR; it layers
correction semantics on top of the receipt chain AAR already defines.

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**,
**RECOMMENDED**, **MAY**, and **OPTIONAL** are interpreted as described in RFC 2119.

---

## 1. Abstract

AAR records *what an agent did*. ACR records *a correction that was made to a prior
action* — what was wrong, who/what detected it, and what was done to fix it. Together they
form a verifiable audit ledger: actions (receipts) and corrections (errata).

ACR enables an AI deployer to evidence the corrective-action and incident-reporting duties
imposed by the EU AI Act (Art 20 corrective actions, Art 26(5) monitor/suspend, Art 26(6)
log retention, Art 73 serious-incident reporting) and to align with NIST AI RMF MANAGE 4.3.

## 2. Motivation — and the scope of what ACR proves

Every production agent makes mistakes. Today those mistakes are either hidden or recorded in
ad-hoc, platform-specific, non-cryptographic logs. ACR gives a standard, signed way to
record a correction when one is detected and disclosed.

**What ACR proves, precisely:**

- **Integrity** — the records were not altered or re-ordered after being written (Ed25519
  signature over canonical bytes, hash-chained). This is a strong, complete guarantee.
- **Attribution** — a given correction record was signed by the holder of a specific signing
  key (the agent's key, or the orchestrator/runtime that holds it on the agent's behalf).

**What ACR does NOT prove:**

- **Completeness.** ACR cannot prove the *absence* of undetected or undisclosed mistakes.
  The absence of correction records means only "no corrections were detected and recorded
  through the configured mechanisms" — it does NOT mean "no mistakes were made." A party
  that controls its own signing key and touches nothing external can simply never write a
  correction. ACR is therefore strong evidence of *integrity*, and weaker evidence of
  *disclosure*, unless the deployment adds independent observers (see §9).

This is not a rhetorical hedge — it is the boundary that keeps ACR honest and defensible to
a sharp auditor. The design's job (see §9) is to widen the set of independent signers as
cheaply as possible, so "no undisclosed mistakes" can be *approached* — never absolutely
claimed.

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

The correction is **signed by the key that holds authority over the action** — the agent's
key, or the runtime/orchestrator that holds it on the agent's behalf. The signature proves
*attribution* ("this key-holder recorded the correction"), not *autonomous self-recognition*
("the model itself realised its error"). The *trigger* field records who/what detected it —
deterministic or human — never an LLM's unaided conscience.



## 4. Record format

An ACR record is a UTF-8 JSON object, signed with Ed25519 over canonical JSON
per **RFC 8785 (JCS — JSON Canonicalization Scheme)**.

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
- `signature` (object, REQUIRED): same shape as AAR `signature` (`alg:"Ed25519"`, `kid`, `publicKey`, `canonicalization:"RFC8785"`, `sig`).
- `metadata` (object, OPTIONAL): extension bag.

### 4.2 Chain semantics

An ACR record links to the record it supersedes via `supersedes.digest` (a content hash, not
just an id). This forms a hash chain: `receipt → correction → correction-of-correction`,
verifiable without trusting the storage layer. Verifiers MUST verify the `supersedes.digest`
matches the referenced record's canonical bytes.

## 5. Signing and canonicalization

Signing uses **Ed25519 over RFC 8785 (JCS)** canonical JSON. `signature.canonicalization`
MUST be `"RFC8785"`.

RFC 8785 (JSON Canonicalization Scheme) is chosen over a bespoke "JCS-sorted" description
for one reason: **interoperability across implementations.** RFC 8785 specifies the exact
rules for key ordering, string escaping (including Unicode and control characters), and
number serialization. A verifier written in Rust, Go, or TypeScript that implements RFC 8785
MUST reproduce byte-identical canonical output to this Python reference — which a
"JCS-sorted, no whitespace, UTF-8" description does not guarantee.

Signing procedure:
1. Build the record with `signature.sig` set to `""`.
2. Canonicalize the whole object per RFC 8785 (recursive key sort, RFC 8785 string/number
   escaping, no insignificant whitespace).
3. Sign the canonical bytes with the Ed25519 key selected by `signature.kid`.
4. Base64url-encode the signature (no padding) into `signature.sig`.

## 6. Verification

1. Validate the record against the JSON Schema (see `schema/`).
2. Recompute canonical bytes per RFC 8785 (with `signature.sig` empty), verify the Ed25519
   signature with the key resolved by `signature.kid`.
3. If `supersedes.digest` is resolvable, verify it matches the referenced record's canonical
   bytes.

## 7. Relationship to other standards

- **AAR v1.0** — the receipt layer ACR extends. ACR reuses AAR's agent/principal/signature
  shapes. NOTE: AAR v1.0 declares `canonicalization:"JCS-SORTED-UTF8-NOWS"`; ACR pins the
  concrete, interoperable RFC 8785 scheme instead. Implementations bridging the two SHOULD
  treat AAR's declaration as RFC 8785 in practice.
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

## 9. Completeness — the residual trust, and how to narrow it

ACR gives strong **integrity** and **attribution**, but weaker **completeness** (§2). This
section states the residual trust plainly and describes the layers that narrow it. This is
the roadmap, not a claim — ACR v1.0 ships integrity + attribution only.

**Residual trust, stated plainly:** completeness holds only relative to the set of
independent signers that touch an action. A single-key, no-counterparty, air-gapped
deployment is integrity-only. The design's job is to widen the set of independent observers
as cheaply as possible.

**Layer 1 — gapless sequence.** Add a monotonic per-agent `seq` alongside `prev_hash`. An
auditor seeing `seq 41` then `46` knows four records are missing. Cheap; on its own
defeatable by renumbering, so it only bites combined with Layer 2.

**Layer 2 — external anchor.** Every K records or T seconds, submit the current head (or a
Merkle root over the batch) to an append-only log the subject cannot rewrite — Sigstore
Rekor, a CT-style witnessed log, or at minimum an RFC 3161 timestamp — and store the
inclusion proof. Any record dated before the last anchor can no longer be inserted or
dropped without the reconstructed head diverging from the anchored one. Trust collapses to
"the interval since the last anchor."

**Layer 3 — independent witness.** Anchoring alone does not stop *equivocation* (honest
chain to auditor A, sanitised chain to auditor B). The CT fix: the anchor log is observed by
≥1 independent witness that co-signs each head. Showing two histories now requires the
witness to co-sign both — i.e. collusion.

**Layer 4 — counterparty reconciliation.** For any action that mutates external state, have
the affected resource return a signed acknowledgement embedding the record hash.
Completeness becomes a reconciliation between two independently held logs: every mutation
maps to an ack, every ack maps to a record. An unmatched ack is a hole you can point at.
This only covers actions that hit a co-signing resource — which is exactly the scope where
hiding matters.

**The highest-leverage piece — keyed trigger authorities.** Give the *detector* its own key.
Our honesty rule (§3) already says corrections fire from the guard/validator/human, not the
agent's conscience. So let the guard co-sign the `check_failed` record on its own anchored
chain. Now suppressing a caught failure means suppressing the guard itself, and the guard's
chain has its own gaps and anchor. This costs almost nothing on top of v1.0 and closes the
most important omission path: the agent quietly dropping its own caught mistakes.

**Auditor's full predicate:** integrity is always checkable. Completeness is checkable
*relative to the set of independent signers* — and the design widens that set one cheap layer
at a time.

