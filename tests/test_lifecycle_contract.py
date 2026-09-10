"""End-to-end contracts at serialization, trust, chain and admission boundaries."""
import json
import math
import random
import struct
from pathlib import Path
import pytest
from corrlog_core import (record, retract, unknown, generate_keypair, canonical_json,
                         verify_trusted, verify_chain, chain_checkpoint)
from corrlog_core.replay import ReplayGuard
from verifier import standalone

SAMPLES=json.loads((Path(__file__).parent/'jcs-vectors/appendix-b.json').read_text(encoding='utf-8'))
FINITE=[(bits,expected) for bits,expected in SAMPLES.items() if expected]

@pytest.mark.parametrize('bits,expected',FINITE)
def test_signed_rfc_value_across_whole_lifecycle(bits,expected,tmp_path):
    value=struct.unpack('>d',bytes.fromhex(bits))[0]
    sk,pk=generate_keypair()
    root=record(agent_id='app',action_type='test',private_key=sk,metadata={'n':value})
    correction=retract(prior_record=root,reason='correction',trigger='check_failed',
                       agent_id='app',private_key=sk,metadata={'n':value})
    uncertainty=unknown(agent_id='app',subject='measurement',private_key=sk,metadata={'n':value})
    checkpoint=chain_checkpoint([root,correction])
    guard=ReplayGuard(str(tmp_path/'admission.sqlite'))
    for original in [root,correction,uncertainty]:
        for encoded in [json.dumps(original).encode(),canonical_json(original)]:
            parsed=json.loads(encoded)
            assert verify_trusted(parsed,pk)
            assert standalone.verify_record(parsed,pk)[0]
            assert canonical_json(parsed)==canonical_json(original)
        parsed=json.loads(canonical_json(original))
        assert guard.accept(parsed,pk)
        assert not guard.accept(original,pk)
    received=[json.loads(canonical_json(r)) for r in [root,correction]]
    assert verify_chain(received,pk,checkpoint=checkpoint)
    assert standalone.verify_chain(received,pk,checkpoint=checkpoint)[0]
    assert not verify_chain(received[:-1],pk,checkpoint=checkpoint)


def test_randomized_numeric_codec_closure():
    rng=random.Random(20260910)
    for _ in range(100000):
        value=struct.unpack('>d',rng.getrandbits(64).to_bytes(8,'big'))[0]
        if not math.isfinite(value):continue
        data={'😀':value,'\ue000':[value,'café']}
        wire=canonical_json(data)
        assert canonical_json(json.loads(wire))==wire
        assert standalone.canonical_bytes(json.loads(wire))==wire


def test_inexact_application_integers_rejected_by_all_constructors():
    sk,pk=generate_keypair()
    root=record(agent_id='app',action_type='test',private_key=sk)
    for value in [2**53+1,10**20+1,10**400]:
        for build in [
            lambda:record(agent_id='a',action_type='x',private_key=sk,metadata={'n':value}),
            lambda:unknown(agent_id='a',subject='x',private_key=sk,metadata={'n':value}),
            lambda:retract(prior_record=root,agent_id='a',reason='x',trigger='check_failed',private_key=sk,metadata={'n':value}),
            lambda:record(agent_id='a',action_type='x',private_key=sk,action_args={'n':value}),
            lambda:record(agent_id='a',action_type='x',private_key=sk,action_result={'n':value}),
            lambda:retract(prior_record=root,agent_id='a',reason='x',trigger='check_failed',private_key=sk,corrected_content={'n':value}),
        ]:
            with pytest.raises(ValueError):build()


def test_signed_numbers_bind_binary64_values_not_decimal_spelling():
    sk,pk=generate_keypair()
    original=record(agent_id='a',action_type='x',private_key=sk,metadata={'n':float(2**53)})
    equivalent=json.loads(json.dumps(original))
    equivalent['metadata']['n']=2**53+1 # same binary64 value after JSON numeric interpretation
    assert verify_trusted(equivalent,pk)
    assert standalone.verify_record(equivalent,pk)[0]
    different=json.loads(json.dumps(original))
    different['metadata']['n']=float(2**53+2) # different binary64 value
    assert not verify_trusted(different,pk)
    # For lossless numbers/identifiers, sign strings instead.
    exact=record(agent_id='a',action_type='x',private_key=sk,metadata={'n':str(2**53)})
    exact['metadata']['n']=str(2**53+1)
    assert not verify_trusted(exact,pk)


def test_nested_python_tuple_arrays_agree_between_verifiers():
    sk,pk=generate_keypair()
    r=record(agent_id='a',action_type='t',private_key=sk,
             metadata={'nested':({'n':10**20},(float(2**68),10**20))})
    assert standalone.verify_record(r,pk)[0]
    assert verify_trusted(json.loads(canonical_json(r)),pk)
    assert standalone.verify_record(json.loads(canonical_json(r)),pk)[0]


def test_random_nested_signed_records_roundtrip():
    rng=random.Random(628507)
    sk,pk=generate_keypair()
    def value(depth):
        if depth and rng.randrange(3)==0:
            return {'😀':value(depth-1),'\ue000':(value(depth-1),value(depth-1))}
        if depth and rng.randrange(3)==0:
            return [value(depth-1),value(depth-1)]
        x=struct.unpack('>d',rng.getrandbits(64).to_bytes(8,'big'))[0]
        return rng.choice([None,True,False,10**20,'café\n日本語',x if math.isfinite(x) else 0.0])
    for _ in range(1000):
        r=record(agent_id='app',action_type='test',private_key=sk,metadata={'data':value(3)})
        assert standalone.verify_record(r,pk)[0]
        for wire in [json.dumps(r).encode(),canonical_json(r)]:
            received=json.loads(wire)
            assert verify_trusted(received,pk)
            assert standalone.verify_record(received,pk)[0]
