#!/usr/bin/env python3
"""Offline ACR verifier: no corrlog imports; third-party RFC 8785 implementation.

Install cryptography, rfc8785 and jsonschema. Keep acr-v1.json alongside this
file. CLI requires a separately trusted key; --signature-only explicitly opts
into checking consistency without establishing signer trust.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
import rfc8785
from jsonschema import Draft202012Validator, FormatChecker
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

_SCHEMA = json.loads(Path(__file__).with_name('acr-v1.json').read_text(encoding='utf-8'))
_VALIDATOR = Draft202012Validator(_SCHEMA, format_checker=FormatChecker())


def _to_double_domain(value):
    """Map parsed JSON numbers onto the binary64 domain.

    All finite parsed JSON numbers use binary64 semantics, including integer
    literals, matching ECMAScript ``JSON.parse`` and RFC 8785. The shortest
    canonical spelling of a binary64 can differ from its exact mathematical integer
    (``float(2**68)`` spells as ``295147905179352830000`` while it is exactly
    ``295147905179352825856``), so an application-level lossless-integer guard must
    not be applied to received canonical JSON. Canonicalization remains delegated to
    the independent rfc8785 library.

    Tuples are normalised to arrays so an in-memory record verifies the same way
    here as in the core, which already treats tuples as JSON arrays.
    """
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        try:
            as_double = float(value)
        except OverflowError:
            raise ValueError('integer outside the IEEE 754 double range')
        if not math.isfinite(as_double):
            raise ValueError('integer outside the IEEE 754 double range')
        return as_double
    if isinstance(value, dict):
        return {k: _to_double_domain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_double_domain(v) for v in value]
    return value


def canonical_bytes(obj):
    return rfc8785.dumps(_to_double_domain(obj))


def _b64url_decode(value, length=None):
    raw = base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)
    if base64.urlsafe_b64encode(raw).decode().rstrip('=') != value or (length is not None and len(raw) != length):
        raise ValueError('invalid base64url')
    return raw


def _digest(record):
    return base64.urlsafe_b64encode(hashlib.sha256(canonical_bytes(record)).digest()).decode().rstrip('=')


def verify_record(record, pinned_pub=None):
    try:
        _VALIDATOR.validate(record)
        signature = record['signature']
        raw = _b64url_decode(signature['publicKey'], 32)
        if record['agent'].get('publicKey', signature['publicKey']) != signature['publicKey']:
            return False, 'agent key mismatch'
        if pinned_pub is not None:
            if pinned_pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw) != raw:
                return False, 'untrusted signer'
            key = pinned_pub
        else:
            key = ed25519.Ed25519PublicKey.from_public_bytes(raw)
        payload = dict(record)
        payload['signature'] = dict(signature, sig='')
        key.verify(_b64url_decode(signature['sig'], 64), canonical_bytes(payload))
        return True, 'valid under pinned key' if pinned_pub is not None else 'signature consistency only; signer untrusted'
    except Exception:
        return False, 'invalid record, schema, key or signature'


def verify_chain(records, pinned_pub=None, *, checkpoint=None):
    try:
        if not isinstance(records, list) or not records:
            return False, 'empty or malformed chain'
        identifiers = set()
        for i, record in enumerate(records):
            ok, reason = verify_record(record, pinned_pub)
            if not ok:
                return False, reason
            if record['correctionId'] in identifiers:
                return False, 'duplicate ID'
            identifiers.add(record['correctionId'])
            if i == 0:
                if 'supersedes' in record:
                    return False, 'missing genesis'
            else:
                previous = records[i-1]
                sup = record.get('supersedes', {})
                if sup.get('receiptId') != previous['correctionId'] or sup.get('digest') != {'alg':'sha256', 'digest':_digest(previous)}:
                    return False, 'broken link'
        if checkpoint is not None:
            if pinned_pub is None or not isinstance(checkpoint, dict) or type(checkpoint.get('length')) is not int:
                return False, 'checkpoint requires trusted key and integer length'
            if checkpoint != {'length':len(records), 'genesis':_digest(records[0]), 'head':_digest(records[-1])}:
                return False, 'checkpoint mismatch'
        return True, 'consistent chain; completeness only relative to supplied trusted checkpoint'
    except Exception:
        return False, 'malformed chain'


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON member')
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=_unique_object,
                      parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))


def load_pub_from_file(path):
    value = read_json(path)
    value = value['publicKey'] if isinstance(value, dict) else value
    return ed25519.Ed25519PublicKey.from_public_bytes(_b64url_decode(value, 32))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='+')
    trust = parser.add_mutually_exclusive_group(required=True)
    trust.add_argument('--key', help='independently trusted JSON public key file')
    trust.add_argument('--signature-only', action='store_true')
    parser.add_argument('--chain', action='store_true')
    parser.add_argument('--checkpoint', help='separately trusted checkpoint JSON (requires --chain and --key)')
    args = parser.parse_args(argv)
    if args.checkpoint and not (args.chain and args.key):
        parser.error('--checkpoint requires --chain and --key')
    try:
        key = load_pub_from_file(args.key) if args.key else None
        checkpoint = read_json(args.checkpoint) if args.checkpoint else None
        records = [read_json(p) for p in args.files]
        results = [verify_record(r, key) for r in records]
        if args.chain:
            results.append(verify_chain(records, key, checkpoint=checkpoint))
        for ok, reason in results:
            print(('PASS ' if ok else 'FAIL ') + reason)
        return 0 if all(ok for ok, _ in results) else 1
    except Exception as exc:
        print('FAIL: ' + str(exc))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
