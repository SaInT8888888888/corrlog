"""F-01 regression: one numeric domain across construction, canonicalization,
JSON parsing and both verification implementations.

A record the library accepts and signs must still verify after being written to
canonical JSON and parsed back. Python's int/float distinction must not silently
invalidate a record that was accepted and signed, and genuinely inexact integers
must be rejected rather than rounded.

Policy under test: wire-format and canonicalization numbers carry binary64
semantics, so a JSON literal is the double it maps to. Precision loss is refused at
the application boundary instead: constructors reject inexact Python integer inputs
before signing. Exact quantities such as money and identifiers belong in strings.
"""
import json
import math
import random
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from corrlog_core import (canonical_json, generate_keypair, record, retract, unknown,
                          validate_record, verify)
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
def test_inexact_integers_are_rejected_at_the_application_boundary(value):
    """Two sides of one contract, both pinned here.

    The codec interprets a JSON number literal as the binary64 it maps to, matching
    ECMAScript and RFC 8785, so canonicalization does NOT raise for an inexact
    integer. Rejection happens where precision would be lost for a caller: the
    constructors refuse to sign an inexact Python integer. Signing such a value
    should fail loudly rather than silently storing a rounded number.
    """
    assert canonical_json({"v": value}) == canonical_json({"v": float(value)})
    with pytest.raises(ValueError):
        record(agent_id="a", action_type="t", private_key=generate_keypair()[0],
               metadata={"v": value})


@pytest.mark.parametrize("value", INEXACT_INTEGERS)
def test_inexact_integers_rejected_by_every_constructor(value):
    """Every constructor path refuses inexact integers, including hashed content."""
    private, _ = generate_keypair()
    root = record(agent_id="a", action_type="t", private_key=private)
    builders = [
        lambda: record(agent_id="a", action_type="x", private_key=private,
                       metadata={"v": value}),
        lambda: unknown(agent_id="a", subject="s", private_key=private,
                        metadata={"v": value}),
        lambda: retract(prior_record=root, reason="r", trigger="check_failed",
                        agent_id="a", private_key=private, metadata={"v": value}),
        lambda: record(agent_id="a", action_type="x", private_key=private,
                       action_args={"v": value}),
        lambda: record(agent_id="a", action_type="x", private_key=private,
                       action_result={"v": value}),
        lambda: retract(prior_record=root, reason="r", trigger="check_failed",
                        agent_id="a", private_key=private, corrected_content={"v": value}),
    ]
    for build in builders:
        with pytest.raises(ValueError):
            build()


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


def test_canonicalization_roundtrip_fuzz():
    """Serialise, parse, serialise again must be stable for random finite doubles.

    This is the failure class found in retest: a double whose shortest canonical
    spelling looks like an integer but is not the exact value of that double, so an
    exact-equality check rejects a spelling the RFC mandates. Seeded for determinism.
    """
    rng = random.Random(8785)
    private, trusted_public = generate_keypair()
    checked = 0
    signed_checked = 0
    while checked < 5000:
        bits = rng.getrandbits(64)
        value = struct.unpack(">d", bits.to_bytes(8, "big"))[0]
        if not math.isfinite(value):
            continue
        checked += 1

        first = canonical_json({"v": value})
        second = canonical_json(json.loads(first))
        assert second == first, f"unstable canonicalization for bits {bits:016x}"

        if signed_checked < 200:
            signed_checked += 1
            rec = record(agent_id="fuzz", action_type="test", private_key=private,
                         timestamp="2026-09-10T00:00:00+00:00", metadata={"v": value})
            assert verify(rec, trusted_public)
            reparsed = json.loads(canonical_json(rec))
            assert verify(reparsed, trusted_public), f"round-trip failed for bits {bits:016x}"
            assert standalone.verify_record(reparsed, trusted_public)[0]
    assert checked == 5000 and signed_checked == 200


# Values whose shortest canonical spelling is NOT the exact mathematical value of
# their binary64. An exact-equality numeric check rejects these, but the RFC requires
# the shortest spelling, so they must be accepted and must stay stable on the wire.
SHORTEST_SPELLING_CASES = [
    (float(2 ** 68), "295147905179352830000"),          # RFC Appendix B 4430000000000000
    (999999999999999700000.0, "999999999999999700000"),  # RFC Appendix B 444b1ae4d6e2ef4e
    (999999999999999900000.0, "999999999999999900000"),  # RFC Appendix B 444b1ae4d6e2ef4f
    (float(10 ** 18 + 128), "1000000000000000100"),      # adjacent case from retest
]


@pytest.mark.parametrize("value,spelling", SHORTEST_SPELLING_CASES)
def test_shortest_spelling_is_not_the_exact_double_value(value, spelling):
    # the exact-equality rule this replaced would reject every one of these
    assert int(value) != int(spelling)
    assert canonical_json({"v": value}) == ('{"v":' + spelling + '}').encode()

    # the spelling is stable: parsing it and re-serialising gives the same bytes
    as_int = json.loads(spelling)
    assert canonical_json({"v": as_int}) == canonical_json({"v": value})

    # and a signed record survives the round-trip through both verifiers
    signed, trusted_public = _signed(value)
    assert verify(signed, trusted_public)
    reparsed = json.loads(canonical_json(signed))
    assert verify(reparsed, trusted_public)
    assert standalone.verify_record(reparsed, trusted_public)[0]
    assert verify(json.loads(json.dumps(signed)), trusted_public)
