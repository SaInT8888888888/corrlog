# corrlog-inspect

An [Inspect](https://inspect.aisi.org.uk/) extension that emits a signed
[corrlog](https://github.com/SaInT8888888888/corrlog) ACR correction receipt
whenever an eval sample scores `INCORRECT`.

It ships as a `Hooks` subclass in its own package, so it is an extension, not a
core change. It sits alongside Inspect's own hook examples and requires no change
to your scoring.

## What it does, and what it does not claim

On `on_sample_end`, the hook reads `data.sample.scores`. If any scorer returned
`INCORRECT`, it builds one ACR correction (`trigger=check_failed`,
`fix_type=other`), signs it with the eval operator's key, and records it. A
sample that scored correct produces nothing.

The receipt attests exactly one thing: that this eval run, signed by this key,
observed this sample fail these scorers. It is evidence with integrity and
attribution. It is not a certification, and it says nothing about completeness:
it proves what was recorded, not that everything was recorded. That boundary is
documented in corrlog's `SECURITY.md`.

## Model identity

The receipt's `agent_id` is the eval's primary model, captured from
`spec.model` at task start. That is the field Inspect treats as the eval's
model identity for cross-eval queries, confirmed by the Inspect maintainers.

One caveat, from the same guidance: an eval can involve additional models via
model roles (a grader, a tool-calling model, or similar that is not the
primary). Treat `spec.model` as the headline identity of the eval, not an
exhaustive list of every model that participated. Receipts are keyed to that
headline model, and role-level attribution is out of scope for the ACR's
agent field.

## Install

```bash
pip install "corrlog-inspect[core]"
```

The `[core]` extra pulls in `corrlog` itself. corrlog is required at signing
time but is not imported at module load, so the package installs and imports
without it; only receipt emission needs it.

## Use

The hook is opt-in. It stays dormant until you set both a signing key and a
receipts file in the environment, so installing the package changes nothing on
its own:

```bash
export CORRLOG_SIGNING_KEY=...     # Ed25519 seed, base64url or hex
export CORRLOG_RECEIPTS_PATH=...   # append-only JSONL file, e.g. ./corrlog-receipts.jsonl
inspect eval your_task.py --model ...
```

With both variables set, `enabled()` returns true, Inspect discovers the hook
through the `inspect_ai` entry point, and every failing sample produces a
signed receipt that is appended to the file at `CORRLOG_RECEIPTS_PATH`: one
receipt per failing sample, durable, each independently verifiable. A sample
that scores correct produces nothing.

Known limitation (2026-09-10 validation): the file is NOT a hash chain. Each
receipt carries a `supersedes` pointer to the action record it corrects, but
that action record is not persisted, so `supersedes.digest` cannot be checked
and reordering or deleting receipt lines is not detectable from the file alone.
Verify receipts individually (or treat the file as an untrusted transport), and
do not rely on file order as evidence. If `corrlog-core` is not installed,
`enabled()` returns false and the hook stays inert rather than silently
emitting nothing.

The hook requires both variables deliberately: a signing key without a
receipts file would sign and discard (the 0.1.0 behaviour, fixed in 0.1.1).
Signing or file-write failures are logged and never break the eval run.

Verify the receipts with corrlog's verifier, pinned to the public half of that
key — the file is plain JSONL, so it also works with any downstream tooling
that reads `corrlog_core.JsonlSink` output.

## Platforms and compatibility (tested, not aspirational)

- Python 3.10–3.13: the full test suite runs in CI on all four versions.
- Operating systems: the full test suite runs in CI on ubuntu-latest,
  windows-latest and macos-latest (GitHub Actions), covering install,
  persistence, partial-tail tolerance and verification on all three.
- Concurrent appends from several processes writing one receipts file were
  stress-tested on Linux (8 processes, 1,000 records each, up to 150 KB per
  record: no interleaving). On Windows, multi-process concurrent append to one
  file is UNTESTED — Windows does not guarantee atomic O_APPEND appends, so
  treat one receipts file as single-writer per process on Windows until
  proven otherwise.
- Inspect AI: tested against inspect-ai 0.3.260 and 0.3.263. The extension is
  registered through Inspect's entry-point discovery; we have not verified
  every Inspect release, so "works with Inspect" should be read as "works with
  the tested 0.3.x releases".

## Durability (exact guarantee, no stronger claim)

Receipts are appended one complete JSON line per write. There is no fsync: a
hard kill (SIGKILL, power loss) during the final write can lose the most
recent receipts still in the OS page cache, and a write killed mid-record can
leave a partial trailing line. Readers handle that: `JsonlSink.all()` skips
unparseable lines instead of raising, reports how many via `damaged_lines`,
and a subsequent append first closes any unterminated tail so new receipts are
never glued onto a damaged line. Earlier history is always readable and
verifiable after a crash.

## How it maps to ACR

| Inspect                                   | ACR correction field            |
| ----------------------------------------- | ------------------------------- |
| a scorer returns `INCORRECT`              | `trigger = check_failed`        |
| the verdict (a detection, not a fix)      | `fix_type = other`              |
| `eval_id` / `sample_id`                   | `subject_ref`                   |
| which scorers failed, plus run context    | structured `metadata`           |

The verdict lives in structured metadata under an enum-style `severity` key, not
free text, so a consumer can filter on it as a first-class value. If the core
later grows a typed severity slot, promote it out of metadata.

## Tests

The suite runs against the real `inspect_ai` classes (`SampleEnd`, `EvalSample`,
`Score`), not mocks. Only the corrlog core is stubbed, through a `FakeSigner`,
since it is the one seam this package deliberately does not own.

```bash
pip install -e . pytest
pytest -q
```

Covered: correct sample emits nothing, incorrect emits exactly one receipt,
multiple failing scorers aggregate into a single receipt, no-scores is a no-op,
a signing failure is caught and never breaks the eval run, the payload
builder is pure, receipts are persisted to the JSONL file and verify against
the pinned key, `enabled()` requires both key and receipts path, and a
broken sink is non-fatal.

## License

MIT.

## Remediation candidate: trust and delivery boundaries

Use the reviewed core 0.2.2 and Inspect 0.1.3 source/wheels together. These version
numbers do not imply publication or approval. The `core` extra now requires the
canonicalization/schema fixes. The published older packages do not contain them.

For verification, provision the operator's public key independently and call
`verify_trusted(receipt, trusted_operator_key)`. The evaluated model's agent.id is
an operator assertion; it does not mean the model possesses the signing key.
`metadata.subject_ref` preserves the supplied sample reference even if caller
metadata contains a conflicting value. Each receipt is individually signed.

The superseded action record is still not persisted. Its digest cannot be resolved
from the receipt alone. Receipt files provide no ordering, completeness, duplicate
or replay guarantee. Consumers can use ReplayGuard with protected persistent state
for unique-ID admission. Equivalent events emitted with fresh IDs remain an
application concern. enabled() reports configuration/import availability; signing
and write failures are logged and do not fail an evaluation. Reconcile receipt
counts and monitor errors if delivery matters. JSONL appends are not fsync-backed.
