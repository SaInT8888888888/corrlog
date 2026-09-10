"""F-01 regression: one numeric domain across construction, canonicalization,
JSON parsing and both verification implementations.

A record the library accepts and signs must still verify after being written to
canonical JSON and parsed back. Python's int/float distinction must not silently
invalidate a record that was accepted and signed, and genuinely inexact integers
must be rejected rather than rounded.

Policy under test: a JSON number is accepted when it is exactly representable as
an IEEE 754 binary64 value, so Python int and float are the same JSON number
whenever they hold the same value. This matches RFC 8785 / I-JSON, where JSON
numbers MUST be expressible as doubles.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from corrlog_core import canonical_json, generate_keypair, record, verify, validate_record
from verifier import standalone

VERIFIER = Path(__file__).resolve().parent.parent / "verifier" / "standalone.py"

# Values accepted by the constructor. Large floats canonicalize to integer-looking
# literals, which is what made the round-trip fail before the fix.
ROUNDTRIP_VALUES = [
    1e16, 1e20, 1e21, 56.0, -56.0, 0.0, 0.1, 1e-7, 1e-6,
    2 ** 53, 2 ** 53 + 2, 10 ** 16, 10 ** 20, 10 ** 21, 5, -5,
]

# Pairs of wire spellings that denote the same number: the first parses as a
# float, the second as an int. Both must canonicalize to identical bytes.
WIRE_SPELLING_PAIRS = [
    ("1e+16", "10000000000000000"),
    ("1e20", "100000000000000000000"),
    ("1e+21", "1e+21"),
    ("56.0", "56"),
    ("0.1", "0.1"),
    ("-56.0", "-56"),
    ("9007199254740992.0", "9007199254740992"),
    ("1e-7", "1e-7"),
]

INEXACT_INTEGERS = [2 ** 53 + 1, 2 ** 64 + 1, 10 ** 30 + 1, 10 ** 20 + 1]


def _signed(value):
    private, trusted_public = generate_keypair()
    signed = record(agent_id="regression", action_type="test", private_key=private,
                    timestamp="2026-09-10T00:00:00+00:00", metadata={"value": value})
    return signed, trusted_public


@pytest.mark.parametrize("value", ROUNDTRIP_VALUES)
def test_accepted_record_survives_canonical_json_roundtrip(value):
    """Only serialization changed, so the verdict must be preserved."""
    signed, trusted_public = _signed(value)
    assert verify(signed, trusted_public)
    received = json.loads(canonical_json(signed))
    assert verify(received, trusted_public)
    assert standalone.verify_record(received, trusted_public)[0]


@pytest.mark.parametrize("value", ROUNDTRIP_VALUES)
def test_accepted_record_survives_plain_json_roundtrip(value):
    """The same guarantee for ordinary json.dumps output, not only canonical."""
    signed, trusted_public = _signed(value)
    received = json.loads(json.dumps(signed))
    assert verify(received, trusted_public)
    assert standalone.verify_record(received, trusted_public)[0]


@pytest.mark.parametrize("float_spelling,int_spelling", WIRE_SPELLING_PAIRS)
def test_wire_spellings_are_equivalent(float_spelling, int_spelling):
    """Two spellings of the same number are one JSON number, not two."""
    as_float = json.loads('{"v":' + float_spelling + '}')["v"]
    as_int = json.loads('{"v":' + int_spelling + '}')["v"]

    signed, trusted_public = _signed(as_float)
    assert verify(signed, trusted_public)

    variant = json.loads(json.dumps(signed))
    variant["metadata"]["value"] = as_int

    # identical canonical bytes: the signature covers the same content
    assert (canonical_json(variant) == canonical_json(signed))
    assert verify(variant, trusted_public)
    assert standalone.verify_record(variant, trusted_public)[0]


@pytest.mark.parametrize("value", ROUNDTRIP_VALUES)
def test_canonical_wire_form_verifies_through_the_cli(value, tmp_path):
    """The exact CLI path: write the canonical wire form to a file and verify it."""
    signed, trusted_public = _signed(value)
    from corrlog_core import public_key_b64url

    key_file = tmp_path / "key.json"
    key_file.write_text(json.dumps({"publicKey": public_key_b64url(trusted_public)}),
                        encoding="utf-8")

    canonical_file = tmp_path / "canonical.json"
    canonical_file.write_bytes(canonical_json(signed))
    plain_file = tmp_path / "plain.json"
    plain_file.write_text(json.dumps(signed), encoding="utf-8")

    for target in (canonical_file, plain_file):
        r = subprocess.run([sys.executable, str(VERIFIER), "--key", str(key_file),
                            str(target)], capture_output=True, text=True)
        assert r.returncode == 0, f"{target.name}: {r.stdout}{r.stderr}"


@pytest.mark.parametrize("value", INEXACT_INTEGERS)
def test_inexact_integers_are_rejected_not_rounded(value):
    with pytest.raises(ValueError):
        canonical_json({"v": value})
    with pytest.raises(ValueError):
        record(agent_id="a", action_type="t", private_key=generate_keypair()[0],
               metadata={"v": value})


def test_exact_integers_verify_and_match_their_double_spelling():
    """Integers exactly representable as binary64 are valid JSON numbers."""
    expected = {2 ** 53: b'{"v":9007199254740992}',
                2 ** 53 + 2: b'{"v":9007199254740994}',
                10 ** 16: b'{"v":10000000000000000}',
                10 ** 20: b'{"v":100000000000000000000}',
                10 ** 21: b'{"v":1e+21}'}
    for value, spelling in expected.items():
        assert canonical_json({"v": value}) == spelling
        signed, trusted_public = _signed(value)
        assert verify(json.loads(canonical_json(signed)), trusted_public)
        validate_record(json.loads(canonical_json(signed)))
