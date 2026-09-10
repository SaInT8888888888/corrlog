# Deliverable C: Reproduction Instructions

Everything in this report can be reproduced from a bare machine. Nothing
requires CorrLog's servers, a CorrLog instance, network access at verification
time, or any resource not listed below.

---

## 1. What you need

- A Linux or macOS machine (the validation was run on Debian 13, Python 3.13.5).
- Python 3.10 to 3.13 available as `python3`.
- `git`.
- `uv` (`curl -LsSf https://astral.sh/uv/install.sh | sh`). `uv` is used only
  because it creates venvs reliably; plain `python3 -m venv` works too if your
  system has `ensurepip`.
- Network access for the initial installs and the `git clone` only.

## 2. One command

```bash
CORRLOG_REPO=https://github.com/SaInT8888888888/corrlog.git \
VALIDATION_DIR=/path/to/corrlog-validation \
WORK=/tmp/corrlog-cleanroom \
bash /path/to/corrlog-validation/harness/run_all.sh
```

That script performs, in order:

1. clones `corrlog` and checks out `b85910d`
2. applies `report/corrlog-validation-fixes.patch` (the six fixes from this
   validation; verified to apply cleanly to `b85910d`)
3. builds five separate venvs: fixed build, published `corrlog-core 0.2.1`,
   oracle only, Inspect with core, Inspect without core
4. builds both wheels from the patched source
5. runs all six suites and rewrites the evidence JSON files
6. regenerates deliverable B from the fresh evidence

Expected final output: 35 core tests pass, 15 Inspect tests pass, 6 of 6 official
JCS vectors pass, the core matrix reports 72 of 91, the Inspect matrix reports 9
of 10, and the migration impact table shows non-ASCII records from 0.2.1 no
longer verifying.

### Important: the fixes are not committed

The six production fixes live in an uncommitted working tree at
`/home/shane/corrlog-sdk`. They are captured as
`report/corrlog-validation-fixes.patch`. A third party reproducing this must
apply that patch, or check out a commit that contains the same changes. Without
it, the matrix reproduces the pre-fix numbers (57 of 91) instead of the final
ones (72 of 91).

---

## 3. Reproducing each claim by hand

Every command below is run from `/tmp` with absolute paths, because that is
what was actually executed. Set `VALIDATION=/path/to/corrlog-validation` and
`WORK=/tmp/corrlog-cleanroom` first.

### Claim: record creation, alteration detection, deterministic verification

```bash
# core matrix, claims 1 to 9 (91 tests)
CORRLOG_PY=$WORK/env-fixed/bin/python \
CORRLOG_ORACLE_PY=$WORK/env-oracle/bin/python \
CORRLOG_MATRIX_OUT=$VALIDATION/evidence/matrix_FINAL.json \
$WORK/env-fixed/bin/python $VALIDATION/harness/matrix.py
```

Each test prints PASS or FAIL with its evidence. The JSON file holds the full
recorded result, including the code path and the severity if it failed.

### Claim: canonicalization is RFC 8785

```bash
# 6 official vectors from cyberphone/json-canonicalization, plus a 10k-case fuzz
# against the third-party rfc8785 implementation
$WORK/env-oracle/bin/python $VALIDATION/harness/test_jcs_candidate.py
```

The conformance vectors are vendored at
`$VALIDATION/vectors/jcs-testdata` (from
`https://github.com/cyberphone/json-canonicalization`, commit `19d51d7`).
Override the location with `CORRLOG_JCS_VECTORS`.

### Claim: independently verifiable

Produce a record, then verify it with a verifier that shares no code with
CorrLog and delegates canonicalization to a third-party implementation:

```bash
# 1. sign a record with the fixed build
$WORK/env-fixed/bin/python - <<'PY'
import json
from corrlog_core import generate_keypair, record, retract, public_key_b64url
priv, pub = generate_keypair()
r = record(agent_id="agent-alpha", action_type="db.write",
           action_args={"y": 1420}, private_key=priv, correction_id="root")
c = retract(prior_record=r, reason="wrong unit: café vs tonne",
            trigger="check_failed", agent_id="agent-alpha", private_key=priv,
            correction_id="c1")
json.dump(c, open("/tmp/rec.json", "w"))
json.dump({"publicKey": public_key_b64url(pub)}, open("/tmp/key.json", "w"))
PY

# 2. verify it with the oracle-based verifier (no corrlog code in the loop)
$WORK/env-oracle/bin/python $VALIDATION/harness/independent_verifier.py \
  --key /tmp/key.json /tmp/rec.json
echo "exit=$?"     # 0

# 3. tamper with one field and verify again
$WORK/env-fixed/bin/python -c "
import json; r=json.load(open('/tmp/rec.json')); r['reason']='not wrong'; json.dump(r,open('/tmp/rec-tampered.json','w'))"
$WORK/env-oracle/bin/python $VALIDATION/harness/independent_verifier.py \
  --key /tmp/key.json /tmp/rec-tampered.json
echo "exit=$?"     # 1, signature verification failed
```

The non-ASCII reason is deliberate. It is the case that the published 0.2.1
gets wrong.

### Claim: the published 0.2.1 does not produce third-party verifiable records

```bash
CORRLOG_OLD_PY=$WORK/env-clean/bin/python \
CORRLOG_NEW_PY=$WORK/env-fixed/bin/python \
$WORK/env-clean/bin/python $VALIDATION/harness/migration_impact.py
```

Shows, per case: 0.2.1 verifies its own record, the fixed build does not, for
any non-ASCII text. To see that the oracle agrees with the fixed build rather
than with 0.2.1, run `mig_oracle.py` (see the harness directory) or repeat the
by-hand sequence above against a record signed by `env-clean`.

### Claim: Inspect integration end to end

```bash
CORRLOG_INSPECT_PY=$WORK/env-inspect/bin/python \
CORRLOG_NOCORE_PY=$WORK/env-nocore/bin/python \
CORRLOG_ORACLE_PY=$WORK/env-oracle/bin/python \
CORRLOG_INSPECT_MATRIX_OUT=$VALIDATION/evidence/matrix_inspect.json \
$WORK/env-fixed/bin/python $VALIDATION/harness/inspect_e2e_matrix.py
```

Every one of those ten tests drives a real `inspect eval` subprocess with
`mockllm/model` and a forced-INCORRECT scorer, then verifies the receipts in a
separate process. Nothing is proven by importing the hook by hand.

To see one receipt yourself:

```bash
CORRLOG_SIGNING_KEY=$(cat $VALIDATION/inspect-e2e/operator.seed) \
CORRLOG_RECEIPTS_PATH=/tmp/my-receipts.jsonl \
$WORK/env-inspect/bin/inspect eval $VALIDATION/inspect-e2e/task_multi.py \
  --model mockllm/model --log-dir /tmp/my-logs
cat /tmp/my-receipts.jsonl | head -1
```

---

## 4. Reading the evidence without running anything

The recorded evidence is checked in:

| File | Contents |
|---|---|
| `evidence/matrix_BEFORE.json` | Claims 1 to 9 before any fix: 57 of 91 |
| `evidence/matrix_FINAL.json` | Claims 1 to 9 after the fixes: 72 of 91 |
| `evidence/matrix_inspect.json` | Claim 10, Inspect end to end: 9 of 10 |
| `report/B_TEST_MATRIX.md` | All of the above rendered as one table |

Each record has: `id`, `claim`, `scenario`, `expected`, `actual`, `verdict`,
`evidence`, `code_path`, `severity_if_failed`. Diff `matrix_BEFORE.json`
against `matrix_FINAL.json` to see exactly which tests the fixes changed. There
are 15 fixed and 0 regressions.

---

## 5. Environment notes

- The two Inspect environments are deliberate. `env-inspect` has the `core`
  extra; `env-nocore` does not, and is used to prove the hook reports itself
  disabled rather than silently doing nothing.
- `env-clean` installs `corrlog-core==0.2.1` from PyPI, unmodified. It is the
  only environment in which the published artifact is exercised.
- `env-oracle` contains no CorrLog code at all. It exists so that verdicts
  about CorrLog's output are produced by something that cannot share its bugs.
- If a matrix test fails during reproduction, compare `actual` in your
  `matrix_FINAL.json` against the checked-in one. The tests print byte-level
  diffs for canonicalization failures, so a failure tells you what differed,
  not just that something did.
