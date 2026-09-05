"""Regression tests for bugs found in the 2026-09-05 adversarial campaign.

F1: JsonlSink.all() raised on a partial trailing line (crashed writer) -> the
    whole history was unreadable through the API. Fix: skip unparseable lines
    and report via damaged_lines.
F2: canonical_json emitted bare NaN/Infinity tokens (not strict JSON) when
    metadata contained them. Fix: allow_nan=False -> record()/retract() raise
    ValueError instead of producing non-JSON content.
F5: JsonlSink.append used ensure_ascii=False, so lone surrogates in content
    raised UnicodeEncodeError at write time even though signing (canonical,
    ensure_ascii=True) succeeded. Fix: ensure_ascii=True in append.
"""
import json
import math
import os
import tempfile

import pytest

from corrlog_core import (
    JsonlSink,
    canonical_json,
    generate_keypair,
    record,
    retract,
    verify,
)


def _receipt(metadata=None):
    priv, pub = generate_keypair()
    r = retract(
        prior_record=record(agent_id="m", action_type="t", private_key=priv,
                            metadata={"i": 1}),
        reason="r", trigger="check_failed", agent_id="m", private_key=priv,
        metadata=metadata or {},
    )
    return r, pub


# ---- F1: partial trailing line must not make history unreadable ----
def test_all_tolerates_partial_trailing_line():
    r, pub = _receipt()
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "s.jsonl")
        with open(p, "w") as f:
            f.write(json.dumps(r) + "\n")
            f.write('{"correctionId": "crashed-mid-write", "unterminated')  # no \n
        sink = JsonlSink(p)
        recs = sink.all()  # must NOT raise (regression: JSONDecodeError)
        assert len(recs) == 1
        assert sink.damaged_lines == 1
        assert verify(recs[0], pub) is True
        # appends must continue safely after damage
        sink.append(r)
        assert len(JsonlSink(p).all()) == 2


def test_all_tolerates_damaged_middle_line():
    r, _ = _receipt()
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "s.jsonl")
        with open(p, "w") as f:
            f.write(json.dumps(r) + "\n")
            f.write("NOT JSON AT ALL\n")
            f.write(json.dumps(r) + "\n")
        sink = JsonlSink(p)
        recs = sink.all()
        assert len(recs) == 2
        assert sink.damaged_lines == 1


def test_all_empty_and_missing_file():
    with tempfile.TemporaryDirectory() as td:
        assert JsonlSink(os.path.join(td, "nope.jsonl")).all() == []
        p = os.path.join(td, "empty.jsonl")
        open(p, "w").close()
        assert JsonlSink(p).all() == []


# ---- F2: NaN / Infinity must be rejected, not emitted as non-JSON ----
def test_canonical_json_rejects_nan():
    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})
    with pytest.raises(ValueError):
        canonical_json({"x": float("inf")})
    # finite floats still fine
    canonical_json({"x": 1.5, "y": -0.0})


def test_record_rejects_nan_metadata():
    priv, _ = generate_keypair()
    with pytest.raises(ValueError):
        retract(
            prior_record=record(agent_id="m", action_type="t", private_key=priv),
            reason="r", trigger="check_failed", agent_id="m", private_key=priv,
            metadata={"bad": float("nan")},
        )


# ---- F5: lone surrogates must persist, not raise UnicodeEncodeError ----
def test_sink_persists_lone_surrogates():
    priv, _ = generate_keypair()
    # A genuinely UNPAIRED lone surrogate (high surrogate with no low partner).
    # json.loads keeps it as-is (unlike a valid pair, which coalesces to the
    # astral character), so the round-trip must be lossless.
    r = retract(
        prior_record=record(agent_id="m", action_type="t", private_key=priv),
        reason="r", trigger="check_failed", agent_id="m", private_key=priv,
        metadata={"text": "truncated \ud800 utf16"},
    )
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "s.jsonl")
        JsonlSink(p).append(r)  # must NOT raise UnicodeEncodeError
        line = open(p, encoding="utf-8").read()
        assert "\\ud800" in line  # escaped, strict ASCII JSON
        recs = JsonlSink(p).all()
        assert len(recs) == 1
        assert recs[0]["metadata"]["text"] == "truncated \ud800 utf16"
