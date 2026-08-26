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

## Install

```bash
pip install "corrlog-inspect[core]"
```

The `[core]` extra pulls in `corrlog` itself. corrlog is required at signing
time but is not imported at module load, so the package installs and imports
without it; only receipt emission needs it.

## Use

The hook is opt-in. It stays dormant until you set a signing key in the
environment, so installing the package changes nothing on its own:

```bash
export CORRLOG_SIGNING_KEY=...   # key, or a path to one; your core decides
inspect eval your_task.py --model ...
```

With the variable set, `enabled()` returns true, Inspect discovers the hook
through the `inspect_ai` entry point, and failing samples produce receipts.
Verify them with corrlog's standalone verifier, pinned to the public half of
that key.

## The one thing to wire

This package owns the Inspect side end to end. The single call it cannot know is
your corrlog core's mint-and-sign function, isolated in `CorrlogSigner.sign`
(`src/corrlog_inspect/_corrlog.py`) behind a marked `ADJUST` block. The
correction payload is already built and shaped correctly before it reaches that
call; you replace two lines with your real corrlog invocation and return the
signed receipt. Nothing else needs changing.

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
a signing failure is caught and never breaks the eval run, and the payload
builder is pure.

## License

MIT.
