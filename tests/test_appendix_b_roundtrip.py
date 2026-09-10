"""Every finite RFC 8785 Appendix B sample must survive a signed round-trip.

Appendix B contains values whose canonical shortest-round-trip spelling is NOT the
exact mathematical value of the binary64. `float(2**68)` spells as
`295147905179352830000` while its exact value is `295147905179352825856`. A verifier
that demands exact equality between the parsed integer and the double rejects a
legitimate canonical spelling, which is the defect this file guards against.

Values are transcribed from the RFC text, not from the repository's fixtures.
"""
import json
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from corrlog_core import canonical_json, generate_keypair, public_key_b64url, record, verify
from verifier import standalone

VERIFIER = Path(__file__).resolve().parent.parent / "verifier" / "standalone.py"

# (IEEE 754 bits, expected canonical JSON spelling). Empty spelling = not a JSON
# number (NaN / Infinity), which the serializer must reject.
APPENDIX_B = [
    ("0000000000000000", "0"), ("8000000000000000", "0"),
    ("0000000000000001", "5e-324"), ("8000000000000001", "-5e-324"),
    ("7fefffffffffffff", "1.7976931348623157e+308"),
    ("ffefffffffffffff", "-1.7976931348623157e+308"),
    ("4340000000000000", "9007199254740992"),
    ("c340000000000000", "-9007199254740992"),
    ("4430000000000000", "295147905179352830000"),
    ("7fffffffffffffff", ""), ("7ff0000000000000", ""),
    ("44b52d02c7e14af5", "9.999999999999997e+22"),
    ("44b52d02c7e14af6", "1e+23"),
    ("44b52d02c7e14af7", "1.0000000000000001e+23"),
    ("444b1ae4d6e2ef4e", "999999999999999700000"),
    ("444b1ae4d6e2ef4f", "999999999999999900000"),
    ("444b1ae4d6e2ef50", "1e+21"),
    ("3eb0c6f7a0b5ed8c", "9.999999999999997e-7"),
    ("3eb0c6f7a0b5ed8d", "0.000001"),
    ("41b3de4355555553", "333333333.3333332"),
    ("41b3de4355555554", "333333333.33333325"),
    ("41b3de4355555555", "333333333.3333333"),
    ("41b3de4355555556", "333333333.3333334"),
    ("41b3de4355555557", "333333333.33333343"),
    ("becbf647612f3696", "-0.0000033333333333333333"),
    ("43143ff3c1cb0959", "1424953923781206.2"),
]

FINITE = [(b, s) for b, s in APPENDIX_B if s]


def _value(bits):
    return struct.unpack(">d", bytes.fromhex(bits))[0]


@pytest.mark.parametrize("bits,spelling", FINITE)
def test_serializer_matches_the_rfc(bits, spelling):
    assert canonical_json({"v": _value(bits)}) == ('{"v":' + spelling + '}').encode()


@pytest.mark.parametrize("bits,spelling", FINITE)
def test_signed_record_roundtrips(bits, spelling):
    """Only serialization changes, so the verdict must be preserved."""
    private, trusted_public = generate_keypair()
    signed = record(agent_id="appendix-b", action_type="test", private_key=private,
                    timestamp="2026-09-10T00:00:00+00:00", metadata={"v": _value(bits)})
    assert verify(signed, trusted_public)

    from_canonical = json.loads(canonical_json(signed))
    assert verify(from_canonical, trusted_public)
    assert standalone.verify_record(from_canonical, trusted_public)[0]

    from_plain = json.loads(json.dumps(signed))
    assert verify(from_plain, trusted_public)
    assert standalone.verify_record(from_plain, trusted_public)[0]


@pytest.mark.parametrize("bits,spelling", FINITE)
def test_canonical_file_verifies_through_the_cli(bits, spelling, tmp_path):
    """The canonical wire form written to a file must verify, not just the object."""
    private, trusted_public = generate_keypair()
    signed = record(agent_id="appendix-b", action_type="test", private_key=private,
                    timestamp="2026-09-10T00:00:00+00:00", metadata={"v": _value(bits)})

    key_file = tmp_path / "key.json"
    key_file.write_text(json.dumps({"publicKey": public_key_b64url(trusted_public)}),
                        encoding="utf-8")
    canonical_file = tmp_path / "canonical.json"
    canonical_file.write_bytes(canonical_json(signed))

    r = subprocess.run([sys.executable, str(VERIFIER), "--key", str(key_file),
                        str(canonical_file)], capture_output=True, text=True)
    assert r.returncode == 0, f"{r.stdout}{r.stderr}"


@pytest.mark.parametrize("bits,spelling", [("7fffffffffffffff", ""), ("7ff0000000000000", "")])
def test_non_finite_values_are_rejected(bits, spelling):
    with pytest.raises(ValueError):
        canonical_json({"v": _value(bits)})


def test_parsed_spelling_is_accepted_where_exact_equality_would_fail():
    """The regression in plain form: the parsed integer is not the double's exact value."""
    spelling = "295147905179352830000"
    as_int = json.loads(spelling)
    as_double = float(2 ** 68)
    assert isinstance(as_int, int)
    assert int(as_double) != as_int  # exact-equality checks reject this
    # yet it is the canonical spelling, so it must canonicalize to itself
    assert canonical_json({"v": as_int}) == ('{"v":' + spelling + '}').encode()
    assert canonical_json({"v": as_double}) == canonical_json({"v": as_int})
