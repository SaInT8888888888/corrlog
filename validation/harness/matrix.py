#!/usr/bin/env python3
"""CorrLog end-to-end validation matrix.

Deterministic tests only -- no LLM judges. Every test records:
  id, claim, scenario, expected, actual, verdict, evidence, code_path, severity.

Run with the CLEAN-ROOM interpreter so `import corrlog_core` resolves to the
published PyPI artifact, not the working tree:

    /home/shane/corrlog-validation/cleanroom/env-clean/bin/python matrix.py

Outputs JSON evidence to ../evidence/matrix.json and prints a table.
"""
from __future__ import annotations

import base64
import copy
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid

import corrlog_core as cc
from corrlog_core import (JsonlSink, MemorySink, canonical_json, generate_keypair,
                          load_private_key, public_key_b64url, record, retract,
                          tamper_evident, unknown, verify, verify_chain)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CLEAN_PY = os.environ.get("CORRLOG_PY", os.path.join(ROOT, "cleanroom/env-clean/bin/python"))
ORACLE_PY = os.environ.get("CORRLOG_ORACLE_PY", os.path.join(ROOT, "env-oracle/bin/python"))
INDEP = os.path.join(HERE, "independent_verifier.py")
OUT_PATH = os.environ.get("CORRLOG_MATRIX_OUT", os.path.join(ROOT, "evidence", "matrix.json"))

RESULTS: list[dict] = []


def check(tid, claim, scenario, expected, actual, ok, evidence="", code_path="unspecified",
          severity="medium"):
    RESULTS.append({
        "id": tid, "claim": claim, "scenario": scenario,
        "expected": expected, "actual": actual,
        "verdict": "PASS" if ok else "FAIL",
        "evidence": evidence, "code_path": code_path, "severity_if_failed": severity,
    })
    return ok


def priv_path_of(rec):
    """Canonical JSON bytes of a record as a Python expression for evidence."""
    return canonical_json(rec).decode()[:200]


# ===========================================================================
# Shared fixtures
# ===========================================================================
PRIV, PUB = generate_keypair()
OTHER_PRIV, OTHER_PUB = generate_keypair()
ATT_PRIV, ATT_PUB = generate_keypair()

DETERMINISTIC_TS = "2026-09-10T00:00:00+00:00"

R1 = record(agent_id="agent-alpha", agent_name="Alpha", action_type="db.write",
            action_target="table:yields", action_args={"yield_kg": 1420},
            action_result={"rows": 1}, private_key=PRIV,
            correction_id="0000-1111", timestamp=DETERMINISTIC_TS)
C1 = retract(prior_record=R1, reason="wrong unit: kg vs tonne", trigger="check_failed",
             agent_id="agent-alpha", private_key=PRIV, fix_type="replace",
             fix_note="divide by 1000", corrected_content={"yield_kg": 1.42},
             source_type="schema", source_reference="zespri/yield.fields",
             correction_id="0000-2222", timestamp=DETERMINISTIC_TS)
C2 = retract(prior_record=C1, reason="source field was itself stale", trigger="human_flagged",
             agent_id="agent-alpha", private_key=PRIV, fix_type="replace",
             correction_id="0000-3333", timestamp=DETERMINISTIC_TS)
CHAIN = [R1, C1, C2]


# ===========================================================================
# CLAIM 1 -- a correction/evidence record can be created
# ===========================================================================
def claim1():
    ok = verify(C1, public_key=PUB)
    check("C1-01", "1", "create a correction record (retract) and verify it",
          "record created; signature verifies under the creating key",
          f"verify(pinned)={ok}; correctionId={C1['correctionId']}",
          ok, json.dumps({k: C1[k] for k in ("correctionId", "reason", "trigger", "fix", "timestamp")}),
          "corrlog_core.retract / corrlog_core.verify", "critical")

    required = ["correctionId", "agent", "principal", "supersedes", "action", "reason",
                "trigger", "fix", "timestamp", "signature"]
    missing = [f for f in required if f not in C1]
    check("C1-02", "1", "correction record carries every ACR-required field",
          "all required fields present", f"missing={missing or 'none'}", not missing,
          f"present={sorted(C1)}", "corrlog_core.retract", "critical")

    a = record(agent_id="a", action_type="x", private_key=PRIV)
    check("C1-03", "1", "create an action record (record)",
          "record created and signed", f"verify={verify(a, public_key=PUB)}",
          verify(a, public_key=PUB), "corrlog_core.record", "high")

    u = unknown(agent_id="a", private_key=PRIV, subject="s", note="n")
    check("C1-04", "1", "create an uncertainty record (unknown)",
          "record created and signed, has kind=unknown, no supersedes",
          f"verify={verify(u, public_key=PUB)}; kind={u.get('kind')}; has_supersedes={'supersedes' in u}",
          verify(u, public_key=PUB) and u.get("kind") == "unknown" and "supersedes" not in u,
          json.dumps({k: u[k] for k in ("kind", "subject", "note")}),
          "corrlog_core.unknown", "high")

    s = retract(prior_record=R1, reason="r", trigger="check_failed", agent_id="a",
                private_key=PRIV, source_type="schema", source_reference="ref")
    check("C1-05", "1", "source/trust field recorded when supplied",
          "fix.source == {type, reference}", f"fix.source={s['fix'].get('source')}",
          s["fix"].get("source") == {"type": "schema", "reference": "ref"},
          "corrlog_core.retract", "medium")

    try:
        retract(prior_record=R1, reason="r", trigger="NOT_A_TRIGGER", agent_id="a", private_key=PRIV)
        ok2 = False
    except ValueError:
        ok2 = True
    check("C1-06", "1", "invalid trigger rejected at creation",
          "ValueError raised", f"ValueError raised={ok2}", ok2,
          "corrlog_core.retract trigger validation", "medium")

    # Deterministic inputs honoured (needed for reproducible vectors)
    ok3 = C1["correctionId"] == "0000-2222" and C1["timestamp"] == DETERMINISTIC_TS
    check("C1-07", "1", "explicit correction_id and timestamp honoured",
          "record uses the supplied id/timestamp verbatim",
          f"id={C1['correctionId']} ts={C1['timestamp']}", ok3,
          "corrlog_core.retract(correction_id=, timestamp=)", "low")


# ===========================================================================
# CLAIM 2 -- independently verifiable
# ===========================================================================
def claim2():
    # 2a: clean-room subprocess verification from an unrelated cwd
    with tempfile.TemporaryDirectory() as td:
        rec_p = os.path.join(td, "record.json")
        key_p = os.path.join(td, "key.json")
        json.dump(C1, open(rec_p, "w"))
        json.dump({"publicKey": public_key_b64url(PUB)}, open(key_p, "w"))
        proc = subprocess.run(
            [CLEAN_PY, "-c",
             "import json,sys;from corrlog_core import verify,JsonlSink,load_private_key;"
             "from cryptography.hazmat.primitives.asymmetric import ed25519;"
             "import base64;"
             "r=json.load(open(sys.argv[1]));k=json.load(open(sys.argv[2]));"
             "raw=base64.urlsafe_b64decode(k['publicKey']+'='*(-len(k['publicKey'])%4));"
             "pub=ed25519.Ed25519PublicKey.from_public_bytes(raw);"
             "print(verify(r,public_key=pub))", rec_p, key_p],
            capture_output=True, text=True, cwd="/tmp")
        out = proc.stdout.strip()
        check("C2-01", "2", "verify a record from a clean environment (separate process, unrelated cwd, PyPI-installed package)",
              "True", f"stdout={out!r}", out == "True",
              f"cmd: python -c 'verify(rec, public_key=pinned)' cwd=/tmp; stderr={proc.stderr.strip()[:120]}",
              "corrlog_core.verify", "critical")

    # 2b: self-authenticating verification accepts an attacker-signed forgery
    forged = record(agent_id="agent-alpha", action_type="db.write",
                    action_result={"yield_kg": 999999}, private_key=ATT_PRIV,
                    correction_id="forged-01", timestamp=DETERMINISTIC_TS)
    selfauth = verify(forged)
    pinned_ok = verify(forged, public_key=PUB)
    check("C2-02", "2", "attacker signs a record with their OWN key and embeds it (key substitution)",
          "forged record must be rejected",
          f"verify(no pin)={selfauth} (accepted); verify(pinned to real key)={pinned_ok}",
          (selfauth is False),
          "corrlog_core.verify: when public_key is None the key embedded in the record is used",
          "critical")

    # 2c/2d: independent RFC 8785 oracle verifier vs corrlog's own verifier
    ascii_rec = retract(prior_record=R1, reason="ascii only reason", trigger="check_failed",
                        agent_id="agent-alpha", private_key=PRIV,
                        correction_id="ascii-01", timestamp=DETERMINISTIC_TS)
    nonascii_rec = retract(prior_record=R1, reason="wrong unit: café vs tonne (2 µs)",
                           trigger="check_failed", agent_id="agent-alpha", private_key=PRIV,
                           correction_id="nonascii-01", timestamp=DETERMINISTIC_TS)

    def indep_verify(rec):
        with tempfile.TemporaryDirectory() as td:
            rp, kp = os.path.join(td, "r.json"), os.path.join(td, "k.json")
            json.dump(rec, open(rp, "w"))
            json.dump({"publicKey": public_key_b64url(PUB)}, open(kp, "w"))
            p = subprocess.run([ORACLE_PY, INDEP, "--key", kp, rp],
                               capture_output=True, text=True, cwd="/tmp")
            return p.stdout.strip(), p.returncode

    out_a, rc_a = indep_verify(ascii_rec)
    check("C2-03", "2", "independent verifier (third-party RFC 8785 oracle, no corrlog code) verifies an ASCII record",
          "PASS", out_a, rc_a == 0, out_a, "harness/independent_verifier.py + rfc8785 0.1.4", "critical")

    out_n, rc_n = indep_verify(nonascii_rec)
    check("C2-04", "2", "independent verifier verifies a record containing non-ASCII text (café, µ)",
          "PASS -- a conforming third party must reproduce the canonical bytes",
          out_n, rc_n == 0,
          f"corrlog verify(pinned)={verify(nonascii_rec, public_key=PUB)} but oracle verifier rc={rc_n}: {out_n}",
          "corrlog_core.canonical_json (ensure_ascii=True) vs RFC 8785 3.2.2.2", "critical")

    # 2e: official JCS conformance
    jcs = subprocess.run([CLEAN_PY, os.path.join(HERE, "jcs_conformance.py")],
                         capture_output=True, text=True, cwd="/tmp")
    tail = jcs.stdout.strip().splitlines()
    passed = next((l for l in tail if "PASS" in l), "?")
    check("C2-05", "2", "official JCS conformance vectors (cyberphone/json-canonicalization)",
          "all vectors byte-identical", passed.strip(), passed.strip().endswith("[6]") or "PASS        : 6" in passed,
          jcs.stdout.strip()[:400], "corrlog_core.canonical_json", "critical")

    # 2f: corrlog's own standalone verifier
    with tempfile.TemporaryDirectory() as td:
        rp, kp = os.path.join(td, "r.json"), os.path.join(td, "k.json")
        json.dump(C1, open(rp, "w"))
        json.dump({"publicKey": public_key_b64url(PUB)}, open(kp, "w"))
        p = subprocess.run([CLEAN_PY, os.path.join(ROOT, "..", "verifier", "standalone.py"),
                            "--key", kp, rp], capture_output=True, text=True, cwd="/tmp")
        check("C2-06", "2", "corrlog's shipped standalone verifier accepts a genuine record (pinned)",
              "PASS", p.stdout.strip(), p.returncode == 0, p.stdout.strip(),
              "corrlog-sdk/verifier/standalone.py", "high")

    # 2g: "moved to another machine" -- file copied elsewhere, verified by another process
    with tempfile.TemporaryDirectory() as td:
        rp = os.path.join(td, "moved.json")
        json.dump(C1, open(rp, "w"))
        p = subprocess.run([CLEAN_PY, "-c",
                            "import json,sys;from corrlog_core import verify;"
                            "print(verify(json.load(open(sys.argv[1]))))", rp],
                           capture_output=True, text=True, cwd="/")
        check("C2-07", "2", "record moved to another location and verified without trusting the origin store",
              "True (self-authenticating)", p.stdout.strip(), p.stdout.strip() == "True",
              "record is self-contained; no network or store lookup", "corrlog_core.verify", "high")


# ===========================================================================
# CLAIM 3 -- alteration is detected
# ===========================================================================
def claim3():
    def mut(label, fn, tid, severity="critical"):
        t = copy.deepcopy(C1)
        fn(t)
        ok = verify(t, public_key=PUB) is False
        check(tid, "3", f"alter {label} after creation",
              "verification fails", f"verify(pinned)={verify(t, public_key=PUB)}", ok,
              f"mutated record id={t.get('correctionId')}", "corrlog_core.verify", severity)

    mut("the correction text (reason)", lambda t: t.__setitem__("reason", "not actually wrong"), "C3-01")
    mut("the fix note", lambda t: t["fix"].__setitem__("note", "no fix needed"), "C3-02")
    mut("the actor/owner (agent.id)", lambda t: t["agent"].__setitem__("id", "someone-else"), "C3-03")
    mut("the principal", lambda t: t["principal"].__setitem__("id", "other-org"), "C3-04")
    mut("the timestamp", lambda t: t.__setitem__("timestamp", "2020-01-01T00:00:00+00:00"), "C3-05")
    mut("the record ID", lambda t: t.__setitem__("correctionId", "9999-9999"), "C3-06")
    mut("the trigger", lambda t: t.__setitem__("trigger", "self_correction"), "C3-07")
    mut("the metadata", lambda t: t["metadata"].__setitem__("injected", 1), "C3-08")
    mut("the signature bytes", lambda t: t["signature"].__setitem__("sig", "A" * 86), "C3-09")
    mut("the signature alg", lambda t: t["signature"].__setitem__("alg", "RSA"), "C3-10")
    mut("the canonicalization declaration",
        lambda t: t["signature"].__setitem__("canonicalization", "JCS-SORTED-UTF8-NOWS"), "C3-11")
    mut("the supersedes digest",
        lambda t: t["supersedes"]["digest"].__setitem__("digest", "A" * 43), "C3-12")

    # field deletion
    for field, tid in [("reason", "C3-13"), ("trigger", "C3-14"), ("correctionId", "C3-15"),
                       ("agent", "C3-16"), ("timestamp", "C3-17"), ("signature", "C3-18"),
                       ("supersedes", "C3-19"), ("metadata", "C3-20")]:
        t = copy.deepcopy(C1)
        t.pop(field, None)
        r = None
        try:
            r = verify(t, public_key=PUB)
        except Exception as e:
            r = f"RAISED {type(e).__name__}"
        check(tid, "3", f"delete field '{field}' after creation",
              "verification fails (False)", f"verify(pinned)={r}", r is False,
              f"verify result for record missing '{field}'", "corrlog_core.verify",
              "critical" if field != "metadata" else "medium")

    # unexpected fields
    for label, fn, tid in [
        ("top-level unexpected field", lambda t: t.__setitem__("evil", "x"), "C3-21"),
        ("extra field inside signature", lambda t: t["signature"].__setitem__("evil", "x"), "C3-22"),
        ("extra field inside agent", lambda t: t["agent"].__setitem__("evil", "x"), "C3-23"),
        ("extra field inside fix.source", lambda t: t["fix"]["source"].__setitem__("evil", "x"), "C3-24"),
        ("extra field inside supersedes.digest",
         lambda t: t["supersedes"]["digest"].__setitem__("evil", "x"), "C3-25"),
    ]:
        t = copy.deepcopy(C1)
        fn(t)
        check(tid, "3", f"add {label}", "verification fails", f"verify(pinned)={verify(t, public_key=PUB)}",
              verify(t, public_key=PUB) is False, "signed body is the whole record minus signature",
              "corrlog_core.verify + canonical_json", "high")

    # the "original error" -- substituting the superseded record
    r_other = record(agent_id="agent-alpha", action_type="db.write",
                     action_args={"yield_kg": 999}, private_key=PRIV,
                     correction_id="other-root", timestamp=DETERMINISTIC_TS)
    check("C3-26", "3", "swap the superseded ('original error') record for a different validly-signed one",
          "chain verification fails (supersedes.digest no longer matches)",
          f"verify_chain([other, C1])={verify_chain([r_other, C1], public_key=PUB)}",
          verify_chain([r_other, C1], public_key=PUB) is False,
          "the digest is bound to the prior record's canonical bytes, not its id",
          "corrlog_core.verify_chain", "critical")

    # cross-key: a validly signed record substituted for another validly signed record
    c_other = retract(prior_record=R1, reason="a different, also-signed correction",
                      trigger="check_failed", agent_id="agent-alpha", private_key=PRIV,
                      correction_id="0000-2222", timestamp=DETERMINISTIC_TS)
    check("C3-27", "3", "swap in a different but validly-signed correction with the SAME correctionId",
          "detected -- a duplicate-id substitution must not verify as the original",
          f"verify(c_other)={verify(c_other, public_key=PUB)}; "
          f"c_other==C1? {c_other == C1}",
          c_other != C1,
          "both records are individually valid but differ in reason; nothing binds an id to one body",
          "corrlog_core.retract", "high")


# ===========================================================================
# CLAIM 4 -- history preserved and traceable
# ===========================================================================
def claim4():
    check("C4-01", "4", "multiple successive corrections form a verifiable chain",
          "verify_chain([r,c1,c2]) is True", f"{verify_chain(CHAIN, public_key=PUB)}",
          verify_chain(CHAIN, public_key=PUB) is True, "3-record linear chain",
          "corrlog_core.verify_chain", "critical")

    # interaction C: is a correction-of-correction linked to the correction, not the root?
    check("C4-02", "4", "each correction points at its immediate predecessor",
          "c2.supersedes.receiptId == c1.correctionId",
          f"c2 -> {C2['supersedes']['receiptId']}; c1 id {C1['correctionId']}",
          C2["supersedes"]["receiptId"] == C1["correctionId"],
          "supersedes.receiptId is copied from the prior record", "corrlog_core.retract", "medium")

    # interior deletion IS detected
    check("C4-03", "4", "delete an interior record of the chain",
          "verify_chain fails", f"{verify_chain([R1, C2], public_key=PUB)}",
          verify_chain([R1, C2], public_key=PUB) is False, "chain [r1, c2] (c1 removed)",
          "corrlog_core.verify_chain", "critical")

    # ROOT deletion is NOT detected
    r = verify_chain(CHAIN[1:], public_key=PUB)
    check("C4-04", "4", "delete the ROOT (first) record of the chain",
          "verify_chain fails -- the remaining chain is an orphaned fragment",
          f"verify_chain([c1,c2])={r}", r is False,
          "verify_chain skips the supersedes check for element 0 (`if i == 0: continue`)",
          "corrlog_core.verify_chain", "critical")

    r = verify_chain([C2], public_key=PUB)
    check("C4-05", "4", "present a single orphaned correction with no predecessor",
          "verify_chain fails", f"verify_chain([c2])={r}", r is False,
          "element 0 is never required to be a root", "corrlog_core.verify_chain", "high")

    r = verify_chain([], public_key=PUB)
    check("C4-06", "4", "empty record list",
          "verify_chain fails (no history presented)",
          f"verify_chain([])={r}", r is False,
          "vacuous truth: the loop body never executes", "corrlog_core.verify_chain", "high")

    # reordering
    check("C4-07", "4", "reorder corrections in a chain",
          "verify_chain fails", f"verify_chain([c1,r1,c2])={verify_chain([C1, R1, C2], public_key=PUB)}",
          verify_chain([C1, R1, C2], public_key=PUB) is False, "swapped r1 and c1",
          "corrlog_core.verify_chain", "critical")

    # receiptId is not cross-checked
    body = {k: v for k, v in C1.items() if k != "signature"}
    body["supersedes"] = dict(C1["supersedes"])
    body["supersedes"]["receiptId"] = "TOTALLY-UNRELATED-ID"
    cc._sign(body, PRIV, public_key_b64url(PUB))
    r = verify_chain([R1, body], public_key=PUB)
    check("C4-08", "4", "correction whose supersedes.receiptId points at an unrelated id",
          "verify_chain fails -- receiptId must be cross-checked against the predecessor's id",
          f"verify_chain([r1, crafted])={r}; crafted receiptId='TOTALLY-UNRELATED-ID'", r is False,
          "only supersedes.digest is compared; supersedes.receiptId is never verified",
          "corrlog_core.verify_chain", "medium")

    # back-dated timestamp
    back = retract(prior_record=R1, reason="backdated", trigger="human_flagged",
                   agent_id="agent-alpha", private_key=PRIV, timestamp="1999-01-01T00:00:00+00:00")
    r = verify_chain([R1, back], public_key=PUB)
    check("C4-09", "4", "correction timestamped BEFORE the action it supersedes",
          "rejected, or at minimum flagged as temporally impossible",
          f"verify_chain={r}; correction ts=1999, action ts=2026", r is False,
          "no timestamp ordering/plausibility check anywhere in the core",
          "corrlog_core.retract / verify_chain", "medium")

    # contradictory corrections
    cA = retract(prior_record=R1, reason="the value is 1.42", trigger="check_failed",
                 agent_id="agent-alpha", private_key=PRIV, corrected_content={"yield_kg": 1.42},
                 correction_id="contra-A", timestamp=DETERMINISTIC_TS)
    cB = retract(prior_record=R1, reason="the value is 1420", trigger="human_flagged",
                 agent_id="agent-alpha", private_key=PRIV, corrected_content={"yield_kg": 1420},
                 correction_id="contra-B", timestamp=DETERMINISTIC_TS)
    both_ok = verify(cA, public_key=PUB) and verify(cB, public_key=PUB)
    check("C4-10", "4", "two contradictory corrections both supersede the same record",
          "both are individually valid; a contradiction should be detectable/flaggable",
          f"verify(cA)={verify(cA, public_key=PUB)} verify(cB)={verify(cB, public_key=PUB)}; "
          f"verify_chain([r1,cA,cB])={verify_chain([R1, cA, cB], public_key=PUB)}",
          False,
          "no contradiction detection exists: both records are valid, signed, and neither is flagged",
          "corrlog_core.verify_chain", "medium")


# ===========================================================================
# CLAIM 5 -- cannot be silently overwritten or modified without detection
# ===========================================================================
def claim5():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "ledger.jsonl")
        open(p, "w").close()
        sink = JsonlSink(p)
        for rec in CHAIN:
            sink.append(rec)
        baseline = len(JsonlSink(p).all())

        # in-place modification
        lines = open(p).read().splitlines()
        rec0 = json.loads(lines[0]); rec0["reason"] = "silently rewritten"
        lines[0] = json.dumps(rec0)
        open(p, "w").write("\n".join(lines) + "\n")
        recs = JsonlSink(p).all()
        detected = not verify(recs[0], public_key=PUB)
        check("C5-01", "5", "modify a record in place inside the ledger file",
              "detected by signature verification", f"verify(record 0)={verify(recs[0], public_key=PUB)}",
              detected, "signature over canonical bytes", "corrlog_core.verify", "critical")

        # reset the ledger, then delete a whole record from the middle
        open(p, "w").close()
        open(p, "w").close()
        sink = JsonlSink(p)
        for rec in CHAIN:
            sink.append(rec)
        lines = open(p).read().splitlines()
        del lines[1]                       # remove the C1 line entirely
        open(p, "w").write("\n".join(lines) + "\n")
        recs = JsonlSink(p).all()
        all_verify = all(verify(x, public_key=PUB) for x in recs)
        check("C5-02", "5", "delete an entire record line from the ledger file",
              "detected -- a missing record in an append-only ledger must be evident",
              f"{len(recs)} records remain, all individually valid={all_verify}; "
              f"verify_chain(remaining)={verify_chain(recs, public_key=PUB)}",
              False,
              "each record is independently signed; nothing links consecutive LEDGER entries, "
              "so a deleted line leaves a file that still verifies record-by-record",
              "corrlog_core.JsonlSink (no ledger-level chain)", "critical")

        # reorder ledger lines
        open(p, "w").close()
        sink = JsonlSink(p)
        for rec in CHAIN:
            sink.append(rec)
        lines = open(p).read().splitlines()
        lines = lines[::-1]
        open(p, "w").write("\n".join(lines) + "\n")
        recs = JsonlSink(p).all()
        check("C5-03", "5", "reorder the record lines in the ledger file",
              "detected", f"all individually valid={all(verify(x, public_key=PUB) for x in recs)}; "
                          f"no ledger-level order binding exists", False,
              "file order is not itself signed or chained", "corrlog_core.JsonlSink", "high")

        # truncate the tail
        open(p, "w").close()
        sink = JsonlSink(p)
        for rec in CHAIN:
            sink.append(rec)
        lines = open(p).read().splitlines()
        open(p, "w").write("\n".join(lines[:-1]) + "\n")
        recs = JsonlSink(p).all()
        check("C5-04", "5", "truncate the tail of the ledger (drop the most recent record)",
              "detected", f"{len(recs)} records remain, all valid="
                          f"{all(verify(x, public_key=PUB) for x in recs)}", False,
              "no head/anchor is published, so a truncated tail is indistinguishable from a shorter history",
              "corrlog_core.JsonlSink", "high")

        # corrupt a line -> silent disappearance
        open(p, "w").close()
        sink = JsonlSink(p)
        for rec in CHAIN:
            sink.append(rec)
        lines = open(p).read().splitlines()
        lines[0] = '{"correctionId": "AAAA", "reason": ' + lines[0][:40]
        open(p, "w").write("\n".join(lines) + "\n")
        s = JsonlSink(p)
        recs = s.all()
        check("C5-05", "5", "corrupt one line so it no longer parses",
              "the corrupt record is reported as an error, not silently dropped",
              f"all() returned {len(recs)} records; damaged_lines={s.damaged_lines}",
              False,
              "all() swallows the failure: the caller must know to read .damaged_lines",
              "corrlog_core.JsonlSink.all", "high")

        # is the file append-only in any enforced sense?
        mode = oct(os.stat(p).st_mode & 0o777)
        check("C5-06", "5", "is the JSONL ledger structurally append-only (not just by convention)?",
              "append-only is enforced (e.g. by an OS-level or hash-chain mechanism)",
              f"file mode={mode}; plain regular file, freely rewritable; no fsync, no chaining",
              False, "JsonlSink opens with 'ab+' and imposes no protection on the file",
              "corrlog_core.JsonlSink.append", "high")


# ===========================================================================
# CLAIM 6 -- duplicate / replayed records handled safely
# ===========================================================================
def claim6():
    m = MemorySink()
    m.append(C1)
    try:
        m.append(C1); m.append(C1)
    except ValueError:
        pass
    check("C6-01", "6", "append the same record three times to a MemorySink",
          "duplicate detected or rejected", f"len(sink.all())={len(m.all())}", len(m.all()) == 1,
          "MemorySink.append has no idempotency check", "corrlog_core.MemorySink", "high")

    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "l.jsonl")
        s = JsonlSink(p)
        s.append(C1); s.append(C1)
        recs = JsonlSink(p).all()
        check("C6-02", "6", "append the same record twice to a JsonlSink (replay a receipt)",
              "duplicate detected or rejected", f"len(all())={len(recs)}; duplicates stored={recs[0]==recs[1]}",
              False, "no dedup; both copies are byte-identical",
              "corrlog_core.JsonlSink.append", "high")

        check("C6-03", "6", "in-chain replay (same record twice inside a chain)",
              "verify_chain fails", f"{verify_chain([R1, C1, C1], public_key=PUB)}",
              verify_chain([R1, C1, C1], public_key=PUB) is False,
              "the second copy supersedes the wrong predecessor", "corrlog_core.verify_chain", "high")

        # duplicate ids, different bodies
        dup = retract(prior_record=R1, reason="a different correction with the same id",
                      trigger="check_failed", agent_id="agent-alpha", private_key=PRIV,
                      correction_id=C1["correctionId"], timestamp=DETERMINISTIC_TS)
        s2 = JsonlSink(os.path.join(td, "d.jsonl"))
        s2.append(C1); s2.append(dup)
        got = s2.get(C1["correctionId"])
        check("C6-04", "6", "two different records sharing one correctionId in the same ledger",
              "rejected, or get() reports ambiguity",
              f"get(id) returned the record whose reason is {got['reason']!r}; both stored",
              False,
              "correctionId is documented as globally unique but uniqueness is never enforced",
              "corrlog_core.JsonlSink.get", "high")


# ===========================================================================
# CLAIM 7 -- missing / malformed / corrupted records fail clearly
# ===========================================================================
def claim7():
    for bad, tid in [(None, "C7-01"), ([], "C7-02"), ("a string", "C7-03"),
                     (42, "C7-04"), (True, "C7-05")]:
        try:
            r = verify(bad, public_key=PUB)
            outcome, ok = f"returned {r}", r is False
        except Exception as e:
            outcome, ok = f"RAISED {type(e).__name__}", False
        check(tid, "7", f"verify() on a non-object record: {bad!r}",
              "returns False (clean failure, no exception)", outcome, ok,
              "verify() calls record.get() without an isinstance guard",
              "corrlog_core.verify", "high")

    for sig, tid in [("abc", "C7-06"), (123, "C7-07"), (True, "C7-08"), ([], "C7-09")]:
        t = copy.deepcopy(C1); t["signature"] = sig
        try:
            r = verify(t, public_key=PUB)
            outcome, ok = f"returned {r}", r is False
        except Exception as e:
            outcome, ok = f"RAISED {type(e).__name__}", False
        check(tid, "7", f"verify() when signature is a non-object: {sig!r}",
              "returns False", outcome, ok, "sig_meta.get() assumes a mapping",
              "corrlog_core.verify", "medium")

    t = copy.deepcopy(C1); del t["signature"]
    check("C7-10", "7", "record with no signature at all",
          "returns False", f"verify={verify(t, public_key=PUB)}", verify(t, public_key=PUB) is False,
          "empty sig_meta -> alg check fails", "corrlog_core.verify", "critical")

    try:
        r = verify_chain([R1, "not a record"], public_key=PUB)
        outcome, ok = f"returned {r}", r is False
    except Exception as e:
        outcome, ok = f"RAISED {type(e).__name__}", False
    check("C7-11", "7", "verify_chain() over a list containing a non-object",
          "returns False", outcome, ok, "verify_chain assumes dict elements",
          "corrlog_core.verify_chain", "medium")

    # malformed JSON on disk
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "bad.jsonl")
        open(p, "w").write("this is not json\n{\"also\": not json\n")
        s = JsonlSink(p)
        recs = s.all()
        check("C7-12", "7", "JsonlSink.all() over a wholly malformed file",
              "raises or reports clearly", f"returned {recs}, damaged_lines={s.damaged_lines}",
              False, "malformed content is silently reduced to a counter",
              "corrlog_core.JsonlSink.all", "medium")

    # schema validation
    schema = json.load(open(os.path.join(
        os.path.dirname(os.path.abspath(cc.__file__)), "schema", "acr-v1.json")))
    try:
        import jsonschema
        v = jsonschema.Draft202012Validator(schema)
        empty = copy.deepcopy(C1)
        empty["reason"] = ""
        empty["agent"]["id"] = ""
        cc._sign(empty, PRIV, public_key_b64url(PUB))
        errs = [e.message for e in v.iter_errors(empty)]
        check("C7-13", "7", "signed record that violates the bundled JSON Schema (empty reason, empty agent id)",
              "verify() fails -- SPEC 6 step 1 requires schema validation before signature check",
              f"verify()={verify(empty, public_key=PUB)}; schema errors={errs[:2]}",
              verify(empty, public_key=PUB) is False,
              "verify() never validates against schema/acr-v1.json",
              "corrlog_core.verify vs SPEC.md 6.1", "high")

        check("C7-14", "7", "record() action records validate against the ACR schema",
              "action records are ACR-valid",
              f"schema errors for record(): {[e.message for e in v.iter_errors(R1)][:2]}",
              not list(v.iter_errors(R1)),
              "record() emits reason='' and no supersedes; the schema requires both",
              "corrlog_core.record", "low")

        check("C7-15", "7", "unknown() uncertainty records validate against the ACR schema",
              "SPEC 4.1b defines them as ACR records (kind=unknown)",
              f"schema errors: {[e.message for e in v.iter_errors(unknown(agent_id='a', private_key=PRIV, subject='s'))][:3]}",
              not list(v.iter_errors(unknown(agent_id="a", private_key=PRIV, subject="s"))),
              "schema has no notion of kind=unknown; supersedes/action/reason/trigger/fix all required",
              "corrlog_core.unknown vs schema/acr-v1.json", "medium")
    except ImportError:
        pass


# ===========================================================================
# CLAIM 8 -- deterministic verification
# ===========================================================================
def claim8():
    runs = [verify(C1, public_key=PUB) for _ in range(50)]
    check("C8-01", "8", "verify the same record 50 times in one process",
          "identical result every time", f"set(results)={set(runs)}", set(runs) == {True},
          "Ed25519 verification is deterministic", "corrlog_core.verify", "high")

    shuffled = {k: C1[k] for k in reversed(list(C1))}
    check("C8-02", "8", "verification independent of dict key insertion order",
          "True", f"verify(shuffled keys)={verify(shuffled, public_key=PUB)}",
          verify(shuffled, public_key=PUB) is True,
          "canonical_json sorts keys recursively", "corrlog_core.canonical_json", "high")

    # re-serialize / deserialize round trip
    rt = json.loads(json.dumps(C1))
    check("C8-03", "8", "verify after JSON serialization/deserialization round trip",
          "True", f"verify(round-trip)={verify(rt, public_key=PUB)}",
          verify(rt, public_key=PUB) is True, "json.dumps -> json.loads preserves the record",
          "corrlog_core.verify", "critical")

    # pretty-printed / reformatted on disk
    pretty = json.loads(json.dumps(C1, indent=4, sort_keys=False))
    check("C8-04", "8", "verify a record that was pretty-printed and re-read",
          "True", f"verify(pretty)={verify(pretty, public_key=PUB)}",
          verify(pretty, public_key=PUB) is True, "whitespace is not part of canonical bytes",
          "corrlog_core.canonical_json", "high")

    # cross-process determinism
    with tempfile.TemporaryDirectory() as td:
        rp, kp = os.path.join(td, "r.json"), os.path.join(td, "k.json")
        json.dump(C1, open(rp, "w")); json.dump({"publicKey": public_key_b64url(PUB)}, open(kp, "w"))
        outs = set()
        for _ in range(3):
            p = subprocess.run([CLEAN_PY, "-c",
                                "import json,sys,base64;from corrlog_core import verify;"
                                "from cryptography.hazmat.primitives.asymmetric import ed25519;"
                                "r=json.load(open(sys.argv[1]));k=json.load(open(sys.argv[2]));"
                                "raw=base64.urlsafe_b64decode(k['publicKey']+'='*(-len(k['publicKey'])%4));"
                                "print(verify(r, public_key=ed25519.Ed25519PublicKey.from_public_bytes(raw)))",
                                rp, kp], capture_output=True, text=True, cwd="/tmp")
            outs.add(p.stdout.strip())
        check("C8-05", "8", "verification across three separate interpreter processes",
              "identical results in every process", f"results={outs}", outs == {"True"},
              "no hidden process state", "corrlog_core.verify", "high")

    # determinism of tamper detection
    t = copy.deepcopy(C1); t["reason"] = "x"
    runs = {verify(t, public_key=PUB) for _ in range(50)}
    check("C8-06", "8", "tampered record rejected deterministically (50 runs)",
          "identical (False) every time", f"set(results)={runs}", runs == {False},
          "deterministic rejection", "corrlog_core.verify", "high")

    # unicode determinism within this implementation
    uni = retract(prior_record=R1, reason="é", trigger="check_failed", agent_id="a",
                  private_key=PRIV, correction_id="uni-1", timestamp=DETERMINISTIC_TS)
    same = canonical_json(uni) == canonical_json(copy.deepcopy(uni))
    check("C8-07", "8", "canonical bytes stable for non-ASCII content within this implementation",
          "byte-identical across calls", f"stable={same}",
          same, "deterministic within corrlog, but see C2-04 for cross-implementation divergence",
          "corrlog_core.canonical_json", "medium")


# ===========================================================================
# CLAIM 9 -- timestamps / identifiers / provenance / ownership
# ===========================================================================
def claim9():
    a = record(agent_id="x", action_type="t", private_key=PRIV)
    b = record(agent_id="x", action_type="t", private_key=PRIV)
    check("C9-01", "9", "correctionId defaults to a fresh UUID per record",
          "two records get different ids", f"{a['correctionId']} vs {b['correctionId']}",
          a["correctionId"] != b["correctionId"] and len(a["correctionId"]) == 36,
          "uuid.uuid4()", "corrlog_core.record", "medium")

    check("C9-02", "9", "correctionId is covered by the signature",
          "changing it invalidates the signature",
          f"verify={verify({**C1, 'correctionId': 'zzz'}, public_key=PUB)}",
          verify({**C1, "correctionId": "zzz"}, public_key=PUB) is False,
          "correctionId is inside the signed body", "corrlog_core.verify", "critical")

    rejected = False
    try:
        retract(prior_record=R1, reason="r", trigger="check_failed", agent_id="a",
                private_key=PRIV, timestamp="not-a-timestamp")
    except ValueError:
        rejected = True
    check("C9-03", "9", "invalid timestamp rejected", "rejected at creation",
          str(rejected), rejected, "constructor schema validation", "retract", "medium")

    check("C9-04", "9", "agent.id and principal.id are separately recorded and signed",
          "both present, both tamper-evident",
          f"agent={C1['agent']['id']} principal={C1['principal']['id']}; "
          f"tamper principal -> {verify({**C1, 'principal': {'id': 'evil', 'type': 'organization'}}, public_key=PUB)}",
          verify({**C1, "principal": {"id": "evil", "type": "organization"}}, public_key=PUB) is False,
          "principal is in the signed body", "corrlog_core.verify", "medium")

    # kid is never resolved against any key: legitimately signing with a nonsense kid still verifies
    weird_kid = retract(prior_record=R1, reason="kid is decorative", trigger="check_failed",
                        agent_id="agent-alpha", private_key=PRIV, kid="NOT-ANY-KEY-ID",
                        correction_id="kid-1", timestamp=DETERMINISTIC_TS)
    check("C9-05", "9", "signature.kid is present but never resolved to a key",
          "kid is resolved against a key (or its non-validation is documented)",
          f"record signed with kid='NOT-ANY-KEY-ID' verifies={verify(weird_kid, public_key=PUB)}; "
          f"kid is never compared to anything",
          False,
          "SPEC 6.2 says the key is 'resolved by signature.kid'; verify() only checks the pinned key "
          "or the embedded signature.publicKey, and ignores kid entirely",
          "corrlog_core.verify", "medium")

    # agent.publicKey vs signature.publicKey
    body = retract(prior_record=R1, reason="signed by attacker, claims victim identity",
                   trigger="check_failed", agent_id="agent-alpha", private_key=ATT_PRIV,
                   correction_id="imp-1", timestamp=DETERMINISTIC_TS)
    body["agent"]["publicKey"] = public_key_b64url(PUB)
    body.pop("signature")
    cc._sign(body, ATT_PRIV, public_key_b64url(PUB))
    check("C9-06", "9", "agent.publicKey and signature.publicKey are independently settable",
          "a record whose agent.publicKey is not the signing key must be rejected",
          f"verify(no pin)={verify(body)} (uses signature.publicKey); "
          f"verify(pinned to agent.publicKey claim)={verify(body, public_key=PUB)}",
          False,
          "verification uses signature.publicKey; nothing requires it to equal agent.publicKey, "
          "so a consumer reading agent.publicKey can be misled when no key is pinned",
          "corrlog_core.verify", "high")

    check("C9-07", "9", "the supersedes pointer binds to prior-record BYTES, not just its id",
          "the digest is a content hash",
          f"supersedes.digest.alg={C1['supersedes']['digest']['alg']}",
          C1["supersedes"]["digest"]["alg"] == "sha256",
          "sha256 of canonical JSON", "corrlog_core.retract", "high")

    # seed-loading prefixes documented in load_private_key
    from cryptography.hazmat.primitives import serialization as _ser
    raw = PRIV.private_bytes(_ser.Encoding.Raw, _ser.PrivateFormat.Raw, _ser.NoEncryption())
    b64 = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    expect_pub = public_key_b64url(PUB)
    bad = []
    for label, val in [("bare base64url", b64), ("hex", raw.hex()),
                       ("sk_<b64url>", "sk_" + b64), ("sk_<hex>", "sk_" + raw.hex()),
                       ("priv_<b64url>", "priv_" + b64), ("ed25519:<b64url>", "ed25519:" + b64)]:
        try:
            got = public_key_b64url(load_private_key(val).public_key())
            if got != expect_pub:
                bad.append(f"{label}=WRONG KEY")
        except Exception as e:
            bad.append(f"{label}={type(e).__name__}")
    check("C9-08", "9", "load_private_key accepts every documented seed prefix",
          "every documented prefix loads the same key",
          f"failures={bad or 'none'}", not bad,
          "docstring advertises sk_, priv_ and ed25519: prefixes",
          "corrlog_core.load_private_key", "medium")


# ===========================================================================
# Driver
# ===========================================================================
def main():
    for fn in (claim1, claim2, claim3, claim4, claim5, claim6, claim7, claim8, claim9):
        fn()
    out = OUT_PATH
    json.dump(RESULTS, open(out, "w"), indent=2)

    fails = [r for r in RESULTS if r["verdict"] == "FAIL"]
    print(f"\n{'ID':8} {'CLAIM':6} {'VERDICT':8} SCENARIO")
    print("-" * 110)
    for r in RESULTS:
        print(f"{r['id']:8} {r['claim']:6} {r['verdict']:8} {r['scenario'][:78]}")
    print("-" * 110)
    print(f"TOTAL {len(RESULTS)}   PASS {len(RESULTS)-len(fails)}   FAIL {len(fails)}")
    print(f"\nevidence -> {out}")
    if fails:
        print("\nFAILURES:")
        for r in fails:
            print(f"\n  [{r['id']}] severity={r['severity_if_failed']}  ({r['code_path']})")
            print(f"      scenario : {r['scenario']}")
            print(f"      expected : {r['expected']}")
            print(f"      actual   : {r['actual']}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
