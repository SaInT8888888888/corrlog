# Offline verification without CorrLog imports

Distribute `standalone.py` and `acr-v1.json` together. Install `cryptography`,
`rfc8785`, and `jsonschema[format-nongpl]` in a fresh environment without CorrLog.
The verifier implements signature and chain verification separately from the core
and uses Trail of Bits' RFC 8785 implementation. It shares the published schema,
not the core's verification or canonicalization code.

```sh
python standalone.py --key trusted-key.json record.json
python standalone.py --key trusted-key.json --chain --checkpoint trusted-head.json root.json correction.json
```

Provision trusted-key.json (`{"publicKey":"<unpadded-base64url>"}`) through an
authenticated operator channel. Never derive it from the record being inspected.
Likewise retain the expected latest checkpoint through an independent trusted path.
A sender-supplied key/checkpoint establishes neither attribution nor completeness.

`--signature-only` explicitly checks consistency under an embedded key; it cannot
establish trusted origin. Without a checkpoint, a valid chain prefix passes. JSONL
file order is not a chain. Exit 0 means the requested checks passed; malformed,
wrong-key or tampered records exit nonzero. Parsing rejects duplicate JSON members.

Historical vectors are examples with public test seeds, not production identities.
Version 0.2.1 canonicalization was nonconforming; the corrected verifier may reject
its records. Do not interpret agreement between two in-tree tools as independent
proof of every assumption. See SECURITY.md and RELEASE_READINESS.md.
