"""Candidate replacement for corrlog_core.canonical_json — true RFC 8785 (JCS).

Differences from the shipped implementation, each traceable to the RFC:

  1. Strings are emitted as RAW UTF-8, not \\uXXXX escapes.
     RFC 8785 3.2.2.2: non-control characters "MUST be serialized as is"
     unless they are U+005C or U+0022.
  2. Only U+0000..U+001F, '"' and '\\' are escaped (with \\b \\t \\n \\f \\r
     for U+0008/09/0A/0C/0D and \\uhhhh — lowercase — for the rest).
     The shipped version additionally escapes U+007F, which the RFC does not.
  3. Numbers use ES6 Number::toString (RFC 8785 3.2.2.3), so 56.0 -> "56",
     1e16 -> "10000000000000000" and 1e-7 -> "1e-7".
  4. Object keys are sorted by UTF-16 code units (RFC 8785 3.2.3), not by
     Unicode code point, so astral-plane keys order correctly.
  5. Lone surrogates are a hard error (RFC 8785 3.2.2.2), not silently emitted.
"""
from __future__ import annotations

import math
from typing import Any

_ESCAPES = {
    0x08: "\\b", 0x09: "\\t", 0x0A: "\\n", 0x0C: "\\f", 0x0D: "\\r",
    0x22: '\\"', 0x5C: "\\\\",
}


def _escape_string(s: str) -> str:
    out = ['"']
    for ch in s:
        o = ord(ch)
        if o in _ESCAPES:
            out.append(_ESCAPES[o])
        elif o < 0x20:
            out.append("\\u%04x" % o)
        elif 0xD800 <= o <= 0xDFFF:
            raise ValueError(
                "cannot canonicalise a lone surrogate (RFC 8785 3.2.2.2 requires an error)"
            )
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _es_number(value: Any) -> str:
    """ES6 Number::toString for JSON numbers (RFC 8785 3.2.2.3)."""
    if isinstance(value, bool):  # bool is an int subclass; guard before int
        raise TypeError("bool is not a JSON number")
    if isinstance(value, int):
        # JSON numbers are IEEE 754 doubles per JCS; integers within the exact
        # double range render verbatim.
        if abs(value) < 2 ** 53:
            return str(value)
        value = float(value)
    x = float(value)
    if math.isnan(x) or math.isinf(x):
        raise ValueError("Out of range IEEE 754 number cannot be serialized")
    if x == 0.0:
        return "0"

    r = repr(x)
    neg = r.startswith("-")
    if neg:
        r = r[1:]
    if "e" in r:
        mant, _, exp = r.partition("e")
        exp = int(exp)
        digits = mant.replace(".", "")
        n = (mant.index(".") if "." in mant else len(mant)) + exp
    elif "." in r:
        int_part, frac = r.split(".")
        digits = int_part + frac
        n = len(int_part)
    else:
        digits, n = r, len(r)

    lead = len(digits) - len(digits.lstrip("0"))
    digits = digits.lstrip("0") or "0"
    n -= lead
    digits = digits.rstrip("0") or "0"
    k = len(digits)

    if k <= n <= 21:
        s = digits + "0" * (n - k)
    elif 0 < n <= 21:
        s = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        s = "0." + "0" * (-n) + digits
    elif k == 1:
        s = digits + "e" + ("+" if n - 1 >= 0 else "-") + str(abs(n - 1))
    else:
        s = digits[0] + "." + digits[1:] + "e" + ("+" if n - 1 >= 0 else "-") + str(abs(n - 1))
    return ("-" if neg else "") + s


def _render(obj: Any, out: list[str]) -> None:
    if obj is None:
        out.append("null")
    elif obj is True:
        out.append("true")
    elif obj is False:
        out.append("false")
    elif isinstance(obj, str):
        out.append(_escape_string(obj))
    elif isinstance(obj, int):
        out.append(_es_number(obj))
    elif isinstance(obj, float):
        out.append(_es_number(obj))
    elif isinstance(obj, dict):
        out.append("{")
        for i, key in enumerate(sorted(obj, key=_utf16_key)):
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings")
            if i:
                out.append(",")
            out.append(_escape_string(key))
            out.append(":")
            _render(obj[key], out)
        out.append("}")
    elif isinstance(obj, (list, tuple)):
        out.append("[")
        for i, item in enumerate(obj):
            if i:
                out.append(",")
            _render(item, out)
        out.append("]")
    else:
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _utf16_key(key: str) -> bytes:
    """Sort key per RFC 8785 3.2.3: compare UTF-16 code units."""
    return key.encode("utf-16-be", "surrogatepass")


def canonical_json(obj: dict[str, Any]) -> bytes:
    out: list[str] = []
    _render(obj, out)
    return "".join(out).encode("utf-8")
