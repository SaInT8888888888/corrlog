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
signed receipt that is appended to the file at `CORRLOG_RECEIPTS_PATH` — one
receipt per failing sample, durable and hash-chained by file order. A sample
that scores correct produces nothing.

The hook requires both variables deliberately: a signing key without a
receipts file would sign and discard (the 0.1.0 behaviour, fixed in 0.1.1).
Signing or file-write failures are logged and never break the eval run.

Verify the receipts with corrlog's verifier, pinned to the public half of that
key — the file is plain JSONL, so it also works with any downstream tooling
that reads `corrlog_core.JsonlSink` output.

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
