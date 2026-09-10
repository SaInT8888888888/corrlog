#!/usr/bin/env python3
"""Claim 10: Inspect integration, end to end, driven through the real inspect CLI.

This complements harness/matrix.py (claims 1 to 9, all in-process). Here every
"actual" is the output of a real `inspect eval` subprocess plus a *separate*
verifier process, so nothing is proven by importing the hook by hand.

Deterministic: mockllm/model, a forced-INCORRECT scorer, fixed timestamps are
not needed because receipts are checked structurally and cryptographically.

Run:
    CORRLOG_INSPECT_PY=<env with core>  \
    CORRLOG_NOCORE_PY=<env without core> \
    CORRLOG_ORACLE_PY=<env with rfc8785> \
    python3 inspect_e2e_matrix.py
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
E2E = os.path.join(ROOT, "inspect-e2e")
OUT = os.environ.get("CORRLOG_INSPECT_MATRIX_OUT", os.path.join(ROOT, "evidence", "matrix_inspect.json"))

WITH_CORE = os.environ.get("CORRLOG_INSPECT_PY", os.path.join(ROOT, "env-inspect/bin/python"))
NO_CORE = os.environ.get("CORRLOG_NOCORE_PY", os.path.join(ROOT, "env-nocore/bin/python"))
ORACLE = os.environ.get("CORRLOG_ORACLE_PY", os.path.join(ROOT, "env-oracle/bin/python"))

RESULTS: list = []


def check(tid, scenario, expected, actual, ok, evidence="", code_path="unspecified",
          severity="medium"):
    RESULTS.append({
        "id": tid, "claim": "10", "scenario": scenario,
        "expected": expected, "actual": actual,
        "verdict": "PASS" if ok else "FAIL",
        "evidence": evidence, "code_path": code_path, "severity_if_failed": severity,
    })
    return ok


def run(py, code, *args, env=None, cwd="/tmp"):
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run([py, "-c", code, *args], capture_output=True, text=True, env=e, cwd=cwd)


SEED = open(os.path.join(E2E, "operator.seed")).read().strip()


def eval_run(py, receipts_path, log_dir, env_extra=None):
    """Run a real inspect eval; returns (completion, stdout+stderr, receipt count)."""
    env = {
        "CORRLOG_SIGNING_KEY": SEED,
        "CORRLOG_RECEIPTS_PATH": receipts_path,
    }
    if env_extra is not None:
        env.update(env_extra)
    if receipts_path:
        try:
            os.remove(receipts_path)
        except FileNotFoundError:
            pass
    p = subprocess.run(
        [py.replace("bin/python", "bin/inspect"), "eval", "task_multi.py",
         "--model", "mockllm/model", "--log-dir", log_dir],
        capture_output=True, text=True, env={**os.environ, **env}, cwd=E2E, timeout=300,
    )
    n = 0
    if receipts_path and os.path.exists(receipts_path):
        n = sum(1 for line in open(receipts_path) if line.strip())
    return p, n


print("=" * 78)
print("CLAIM 10: Inspect integration, end to end (real inspect CLI subprocesses)")
print("=" * 78)
print(f"  with-core env : {WITH_CORE}")
print(f"  no-core env   : {NO_CORE}")
print(f"  oracle env    : {ORACLE}")

# --------------------------------------------------------------------------
# C10-01: the hook is registered as an Inspect entry point and is discovered.
# --------------------------------------------------------------------------
code = (
    "import importlib.metadata as md;"
    "eps=md.entry_points();"
    "g=eps.select(group='inspect_ai') if hasattr(eps,'select') else eps.get('inspect_ai',[]);"
    "print(sorted((e.name, e.value) for e in g))"
)
p = run(WITH_CORE, code)
check("C10-01", "corrlog-inspect registers itself in the inspect_ai entry point group",
      "the installed package advertises an inspect_ai entry point",
      f"entry points = {p.stdout.strip()}",
      "corrlog_inspect" in p.stdout,
      evidence=p.stdout.strip(), code_path="corrlog_inspect/pyproject.toml (entry-points)",
      severity="high")

# --------------------------------------------------------------------------
# C10-02: a fully configured run emits one receipt per failing sample.
# --------------------------------------------------------------------------
rec_final = os.path.join(E2E, "receipts-final.jsonl")
p, n = eval_run(WITH_CORE, rec_final, os.path.join(E2E, "logs-final"))
check("C10-02", "a real `inspect eval` over 3 forced-INCORRECT samples emits receipts",
      "one signed receipt per failing sample",
      f"eval exit={p.returncode}; receipts in file = {n}",
      p.returncode == 0 and n == 3,
      evidence=f"tail: {p.stdout.strip().splitlines()[-1][:120] if p.stdout.strip() else ''}",
      code_path="corrlog_inspect/hooks.py:on_sample_end", severity="high")

records = []
if os.path.exists(rec_final):
    records = [json.loads(l) for l in open(rec_final) if l.strip()]

# --------------------------------------------------------------------------
# C10-03: receipt content is the real eval context, not a placeholder.
# --------------------------------------------------------------------------
if records:
    r0 = records[0]
    model = r0.get("agent", {}).get("id")
    meta0 = r0.get("metadata", {})
    ref = meta0.get("subject_ref", "")
    # The receipt must let a reader answer "which sample was this?". Assert the
    # pointer is exactly inspect:<eval_id>/<sample_id>, matching the structured
    # ids in the same receipt (a mismatch would make the pointer untrustworthy).
    # Note: inspect 0.3.263 assigns its own sample UUIDs; the dataset's `id="s0"`
    # does not survive into the eval, so the pointer is checked for internal
    # consistency rather than for a literal dataset id.
    expect_ref = f"inspect:{meta0.get('eval_id')}/{meta0.get('sample_id')}"
    ok = model == "mockllm/model" and ref == expect_ref and bool(meta0.get("sample_id"))
else:
    model, ref, expect_ref, ok = None, "", "", False
check("C10-03", "receipt identifies the evaluated model and the sample it came from",
      "agent.id is the evaluated model; metadata.subject_ref equals inspect/<eval_id>/<sample_id>",
      f"agent.id={model!r}, subject_ref={ref!r}, expected {expect_ref!r}",
      ok, evidence=json.dumps({k: r0.get(k) for k in ("agent", "metadata")})[:220] if records else "",
      code_path="corrlog_inspect/hooks.py:on_task_start, _corrlog.build_correction/Signer.sign",
      severity="medium")

# --------------------------------------------------------------------------
# C10-04: every receipt verifies against the PINNED operator key.
# --------------------------------------------------------------------------
code = (
    "import json,sys;"
    "from corrlog_core import JsonlSink, load_private_key, verify;"
    "seed=open(sys.argv[1]).read().strip();"
    "pub=load_private_key(seed).public_key();"
    "recs=JsonlSink(sys.argv[2]).all();"
    "print(all(verify(r, public_key=pub) is True for r in recs), len(recs),"
    " sum(1 for r in recs if r.get('supersedes')))"
)
p = run(WITH_CORE, code, os.path.join(E2E, "operator.seed"), rec_final)
parts = p.stdout.strip().split()
all_ok = parts and parts[0] == "True"
check("C10-04", "each receipt verifies against the operator's pinned public key",
      "all receipts verify under the pinned key",
      f"all_verify={parts[0] if parts else '?'}, n={parts[1] if len(parts) > 1 else '?'}, "
      f"with supersedes pointer={parts[2] if len(parts) > 2 else '?'}",
      bool(all_ok), evidence=p.stdout.strip(),
      code_path="corrlog_core.verify (Ed25519 over RFC 8785)", severity="high")

# --------------------------------------------------------------------------
# C10-05: tampering with a real receipt is detected.
# --------------------------------------------------------------------------
tamper = (
    "import copy,json,sys;"
    "from corrlog_core import load_private_key, verify;"
    "seed=open(sys.argv[1]).read().strip(); pub=load_private_key(seed).public_key();"
    "r=json.load(open(sys.argv[2])); mut={};"
    "x=copy.deepcopy(r); x['reason']='not actually wrong'; mut['reason']=verify(x, public_key=pub);"
    "x=copy.deepcopy(r); x['metadata']['failing_scorers']['forced_scorer']='C'; mut['scorer']=verify(x, public_key=pub);"
    "x=copy.deepcopy(r); x['injected']='x'; mut['extra field']=verify(x, public_key=pub);"
    "x=copy.deepcopy(r); x.pop('metadata'); mut['deleted metadata']=verify(x, public_key=pub);"
    "x=copy.deepcopy(r); x['agent']['id']='someone-else'; mut['agent id']=verify(x, public_key=pub);"
    "print(json.dumps({k: v for k, v in mut.items()}))"
)
rp = os.path.join(E2E, "receipts-final.jsonl")
tmp = tempfile.mkdtemp(prefix="c10-05-")
r0_path = os.path.join(tmp, "r0.json")
if records:
    json.dump(records[0], open(r0_path, "w"))
p = run(WITH_CORE, tamper, os.path.join(E2E, "operator.seed"), r0_path)
try:
    mut = json.loads(p.stdout.strip())
except Exception:
    mut = {}
all_rejected = bool(mut) and all(v is False for v in mut.values())
check("C10-05", "tamper detection on a receipt produced by a real eval run",
      "every single-field mutation makes verification fail",
      f"verification results per mutation = {mut}",
      all_rejected, evidence=p.stdout.strip() or p.stderr.strip()[:200],
      code_path="corrlog_core.verify", severity="high")

# --------------------------------------------------------------------------
# C10-06: the receipts FILE is not a hash chain, and supersedes is uncheckable.
# --------------------------------------------------------------------------
chain = (
    "import json,sys,glob,os;"
    "from corrlog_core import JsonlSink, load_private_key, verify, verify_chain;"
    "seed=open(sys.argv[1]).read().strip(); pub=load_private_key(seed).public_key();"
    "recs=JsonlSink(sys.argv[2]).all();"
    "ids={r['correctionId'] for r in recs};"
    "dangling=[r['supersedes']['receiptId'] in ids for r in recs if r.get('supersedes')];"
    "print(json.dumps({'n': len(recs), 'chain_pinned': verify_chain(recs, public_key=pub),"
    " 'targets_present_in_file': dangling}))"
)
p = run(WITH_CORE, chain, os.path.join(E2E, "operator.seed"), rec_final)
try:
    d = json.loads(p.stdout.strip())
except Exception:
    d = {}
not_a_chain = d.get("chain_pinned") is False
targets_missing = d.get("targets_present_in_file") == [False] * len(d.get("targets_present_in_file") or [1])
check("C10-06", "is the receipts JSONL a hash chain, as hooks.py and README state",
      "file-order receipts should chain, or the claim must be withdrawn",
      f"verify_chain(file order) = {d.get('chain_pinned')}; "
      f"supersedes targets present in file = {d.get('targets_present_in_file')}",
      False,  # the documented claim is FALSE
      evidence=p.stdout.strip(),
      code_path="corrlog_inspect/hooks.py:1-25 docstring; corrlog_inspect/_corrlog.py:CorrlogSigner.sign",
      severity="high")

# --------------------------------------------------------------------------
# C10-07: with corrlog-core absent, the hook reports DISABLED and stays inert.
# --------------------------------------------------------------------------
verify_enabled = (
    "from corrlog_inspect.hooks import CorrlogReceiptHook as H;"
    "print('ENABLED', H.enabled())"
)
env = {"CORRLOG_SIGNING_KEY": SEED, "CORRLOG_RECEIPTS_PATH": "/tmp/should-not-exist.jsonl"}
p = run(NO_CORE, verify_enabled, env=env)
try:
    os.remove("/tmp/should-not-exist.jsonl")
except FileNotFoundError:
    pass
reports_disabled = "ENABLED False" in p.stdout
check("C10-07", "corrlog-inspect installed WITHOUT corrlog-core (the optional extra)",
      "enabled() reports False: a hook that cannot sign must not claim to be active",
      f"stdout={p.stdout.strip()!r}",
      reports_disabled,
      evidence=(p.stderr.strip().splitlines() or [""])[-1][:200],
      code_path="corrlog_inspect/hooks.py:_core_available, enabled", severity="high")

# --------------------------------------------------------------------------
# C10-08: the no-core run is inert AND does not pollute the eval with tracebacks.
# --------------------------------------------------------------------------
p, n = eval_run(NO_CORE, "/tmp/nocore-receipts.jsonl", "/tmp/nocore-logs")
blob = p.stdout + p.stderr
n_tb = blob.lower().count("traceback")
n_msg = blob.count("corrlog-core is not installed")
check("C10-08", "a full inspect eval in the no-core env: hook is inert, eval still passes",
      "eval completes, zero receipts, one actionable message, no traceback",
      f"exit={p.returncode}, receipts={n}, tracebacks={n_tb}, actionable messages={n_msg}",
      p.returncode == 0 and n == 0 and n_tb == 0 and n_msg >= 1,
      evidence=f"eval stdout tail: {blob.strip().splitlines()[-1][:120] if blob.strip() else ''}",
      code_path="corrlog_inspect/hooks.py:__init__, enabled", severity="medium")

# --------------------------------------------------------------------------
# C10-09: a receipt verified on a DIFFERENT machine (fresh dir, fresh temp env).
# --------------------------------------------------------------------------
clean = tempfile.mkdtemp(prefix="c10-09-cleanroom-")
pub_k = os.path.join(clean, "operator-pub.json")
code = (
    "import json,sys;from corrlog_core import load_private_key, public_key_b64url;"
    "seed=open(sys.argv[1]).read().strip();"
    "json.dump({'publicKey': public_key_b64url(load_private_key(seed).public_key())}, open(sys.argv[2],'w'))"
)
run(WITH_CORE, code, os.path.join(E2E, "operator.seed"), pub_k)
moved = []
if records:
    for i, r in enumerate(records):
        mp = os.path.join(clean, f"moved{i}.json")
        json.dump(r, open(mp, "w"))
        moved.append(mp)
p = subprocess.run([ORACLE, os.path.join(HERE, "independent_verifier.py"), "--key", pub_k, *moved],
                   capture_output=True, text=True, cwd="/tmp")
oracle_ok = bool(moved) and all(line.startswith("PASS") for line in p.stdout.strip().splitlines())
check("C10-09", "receipt generated by Inspect, moved to a clean directory, verified by a "
      "third-party verifier with no corrlog code in the loop",
      "the oracle verifier accepts the moved receipts under the pinned key",
      f"oracle exit={p.returncode}; {p.stdout.strip().splitlines()[0][:80] if p.stdout.strip() else ''}",
      oracle_ok, evidence=p.stdout.strip(),
      code_path="harness/independent_verifier.py (rfc8785 third-party oracle)", severity="high")

# --------------------------------------------------------------------------
# C10-10: a signing failure must not fail the eval.
# --------------------------------------------------------------------------
bad = {"CORRLOG_SIGNING_KEY": "not-a-valid-key"}
try:
    os.remove("/tmp/badkey-receipts.jsonl")
except FileNotFoundError:
    pass
p = subprocess.run(
    [WITH_CORE.replace("bin/python", "bin/inspect"), "eval", "task_multi.py",
     "--model", "mockllm/model", "--log-dir", "/tmp/badkey-logs"],
    capture_output=True, text=True, cwd=E2E, timeout=300,
    env={**os.environ, "CORRLOG_SIGNING_KEY": "not-a-valid-key",
         "CORRLOG_RECEIPTS_PATH": "/tmp/badkey-receipts.jsonl"},
)
n_bad = 0
if os.path.exists("/tmp/badkey-receipts.jsonl"):
    n_bad = sum(1 for line in open("/tmp/badkey-receipts.jsonl") if line.strip())
check("C10-10", "an unusable signing key must not break the eval run",
      "eval still completes (exit 0) and emits no unverifiable receipt",
      f"exit={p.returncode}, receipts written={n_bad}",
      p.returncode == 0 and n_bad == 0,
      evidence=(p.stdout + p.stderr).strip().splitlines()[-1][:120],
      code_path="corrlog_inspect/hooks.py:on_sample_end (guarded sign)", severity="high")

shutil.rmtree(tmp, ignore_errors=True)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(RESULTS, open(OUT, "w"), indent=2)
p = sum(1 for r in RESULTS if r["verdict"] == "PASS")
print()
print(f"claim 10: {p}/{len(RESULTS)} PASS")
for r in RESULTS:
    print(f"  {'PASS' if r['verdict'] == 'PASS' else 'FAIL'}  [{r['id']}] {r['scenario'][:64]}")
print(f"\nwritten: {OUT}")
