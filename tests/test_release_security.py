"""Release gates for explicit trust, schema, replay and bounded chain completeness."""
import copy
import json
import random
import struct
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
import rfc8785
from corrlog_core import (record, retract, unknown, generate_keypair, verify, verify_trusted,
    verify_chain, chain_checkpoint, canonical_json, validate_record, load_private_key, public_key_b64url)
from corrlog_core.replay import ReplayGuard
from verifier import standalone


def make_chain():
    sk, pk = generate_keypair()
    chain = [record(agent_id='a', action_type='x', private_key=sk)]
    for i in range(2):
        chain.append(retract(prior_record=chain[-1], reason='café 😀', trigger='check_failed', agent_id='a', private_key=sk))
    return sk, pk, chain


@pytest.mark.parametrize('bad',[None, [], 1, 'x', {}, {'signature':[]}, {'signature':{'alg':'Ed25519','canonicalization':'RFC8785','sig':4}}, {'agent':None}])
def test_malformed(bad):
    assert verify(bad) is False
    assert verify_chain(bad) is False
    assert standalone.verify_record(bad)[0] is False
    assert standalone.verify_chain(bad)[0] is False


def test_signed_schema_violations():
    from corrlog_core import _sign
    sk, pk, chain = make_chain()
    for field, value in [('agent',{}),('timestamp','yesterday'),('reason',''),('fix',{'type':'invalid'}),('metadata',[]),('supersedes',None)]:
        bad = copy.deepcopy(chain[-1]); bad[field]=value
        _sign(bad,sk,public_key_b64url(pk))
        assert not verify(bad,pk), field
        assert not standalone.verify_record(bad,pk)[0], field


def test_constructor_schema_and_input_ownership():
    sk, pk, chain = make_chain()
    for r in chain+[unknown(agent_id='a',subject='x',private_key=sk)]:
        validate_record(r)
    for kwargs in [{'agent_id':''},{'timestamp':'today'},{'metadata':[]},{'action_type':''}]:
        args=dict(agent_id='a',action_type='x',private_key=sk);args.update(kwargs)
        with pytest.raises(ValueError):record(**args)
    meta={'nested':{'x':1}}
    r=record(agent_id='a',action_type='x',private_key=sk,metadata=meta)
    meta['nested']['x']=2
    assert verify(r,pk)


def test_checkpoint_attacks():
    sk, pk, chain=make_chain(); checkpoint=chain_checkpoint(chain)
    other=record(agent_id='a',action_type='x',private_key=sk)
    attacks=[[],chain[1:],chain[:-1],[chain[0],chain[2]],chain[::-1],
             [chain[0],other,*chain[1:]],[other,*chain[1:]],chain+chain[-1:]]
    assert verify_chain(chain,pk,checkpoint=checkpoint)
    assert standalone.verify_chain(chain,pk,checkpoint=checkpoint)[0]
    for attack in attacks:
        assert not verify_chain(attack,pk,checkpoint=checkpoint)
        assert not standalone.verify_chain(attack,pk,checkpoint=checkpoint)[0]
    assert verify_chain(chain[:-1],pk)  # documented prefix limitation
    assert not verify_chain(chain,checkpoint=checkpoint) # missing key
    assert not verify_chain(chain,pk,checkpoint={**checkpoint,'length':True})
    # A malicious checkpoint provided by the sender is no anchor.
    assert verify_chain(chain[:-1],pk,checkpoint=chain_checkpoint(chain[:-1]))


def test_duplicate_id_validly_signed_and_wrong_link_id():
    from corrlog_core import _sign
    sk,pk,chain=make_chain()
    dup=retract(prior_record=chain[0],reason='x',trigger='check_failed',agent_id='a',private_key=sk,correction_id=chain[0]['correctionId'])
    assert not verify_chain([chain[0],dup],pk)
    bad=copy.deepcopy(chain[1]);bad['supersedes']['receiptId']='wrong';_sign(bad,sk,public_key_b64url(pk))
    assert not verify_chain([chain[0],bad],pk)


def test_trust_and_persistent_concurrent_replay(tmp_path):
    sk,pk,chain=make_chain(); r=chain[0]
    _,wrong=generate_keypair()
    assert not verify_trusted(r,None)
    assert not verify_trusted(r,wrong)
    path=str(tmp_path/'admissions.db')
    guard=ReplayGuard(path)
    assert not guard.accept(r,wrong)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(lambda _: ReplayGuard(path).accept(r,pk),range(16)))
    assert sum(results)==1
    assert not ReplayGuard(path).accept(r,pk)
    substitute=record(agent_id='a',action_type='different',private_key=sk,correction_id=r['correctionId'])
    assert not guard.accept(substitute,pk)


def test_key_prefixes():
    seed='42'*32
    for prefix in ['', 'sk_', 'priv_', 'ed25519:']:
        assert public_key_b64url(load_private_key(prefix+seed).public_key()) == public_key_b64url(load_private_key(seed).public_key())


def test_jcs_official_and_differential():
    vectors=Path(__file__).parent/'jcs-vectors'
    for path in sorted((vectors/'input').glob('*.json')):
        obj=json.loads(path.read_text(encoding='utf-8'));expected=(vectors/'output'/path.name).read_bytes()
        assert canonical_json(obj)==expected
        assert standalone.canonical_bytes(obj)==expected
    rng=random.Random(8785)
    for _ in range(10000):
        number=struct.unpack('>d',rng.getrandbits(64).to_bytes(8,'big'))[0]
        import math
        if not math.isfinite(number):continue
        value={'😀':number,'\ue000':[number,'café\n\x00',rng.randrange(-2**53+1,2**53)]}
        assert canonical_json(value)==rfc8785.dumps(value)
    for invalid in [2**53,2**53+1,float('nan'),float('inf'),'\ud800']:
        with pytest.raises((ValueError,TypeError)):canonical_json(invalid)


def test_standalone_duplicate_json_members(tmp_path):
    p=tmp_path/'bad.json';p.write_text('{"a":1,"a":2}', encoding='utf-8')
    with pytest.raises(ValueError):standalone.read_json(p)


def test_schema_copies_identical():
    root=Path(__file__).parents[1]
    assert (root/'verifier/acr-v1.json').read_bytes()==(root/'corrlog_core/schema/acr-v1.json').read_bytes()


def test_jsonl_ledger_limitations_are_explicit(tmp_path):
    from corrlog_core import JsonlSink
    sk,pk,chain=make_chain()
    other=record(agent_id='a',action_type='other',private_key=sk)
    # All attacks leave individually valid records: JSONL is not an integrity gate.
    for changed in [chain[1:],chain[:-1],chain[::-1],chain+[chain[-1]],
                    [other,*chain[1:]],[chain[0],other,*chain[1:]]]:
        path=tmp_path/'transport.jsonl'
        path.write_text(''.join(json.dumps(r)+'\n' for r in changed), encoding='utf-8')
        assert all(verify(r,pk) for r in JsonlSink(str(path)).all())


def test_subject_ref_overrides_conflicting_metadata():
    from corrlog_inspect._corrlog import CorrlogSigner
    signer=CorrlogSigner('42'*32)
    receipt=signer.sign({'agent_id':'model','subject_ref':'actual', 'detail':'failed', 'trigger':'check_failed', 'fix_type':'noop',
                         'metadata':{'subject_ref':'forged'}})
    assert receipt['metadata']['subject_ref']=='actual'


def test_rfc8785_appendix_b():
    values=json.loads((Path(__file__).parent/'jcs-vectors/appendix-b.json').read_text(encoding='utf-8'))
    assert len(values)==26
    for bits, expected in values.items():
        value=struct.unpack('>d',bytes.fromhex(bits))[0]
        if not expected:
            with pytest.raises(ValueError):canonical_json(value)
        else:
            assert canonical_json(value)==expected.encode(),bits
            assert standalone.canonical_bytes(value)==expected.encode(),bits
