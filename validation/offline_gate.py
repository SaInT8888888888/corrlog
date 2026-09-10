"""Run with an oracle-only interpreter, SOURCE_ROOT and RECORD_DIRECTORY.
Network creation is disabled for the verification phase. No CorrLog import.
"""
import importlib.util, json, pathlib, socket, sys
assert importlib.util.find_spec('corrlog_core') is None
root=pathlib.Path(sys.argv[1]);data=pathlib.Path(sys.argv[2])
spec=importlib.util.spec_from_file_location('independent',root/'verifier/standalone.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
def denied(*args,**kwargs):raise AssertionError('network forbidden during verification')
socket.socket=denied
key=v.load_pub_from_file(data/'trusted-key.json')
chain=[v.read_json(data/name) for name in ['root.json','correction.json']]
checkpoint=v.read_json(data/'checkpoint.json')
assert v.verify_chain(chain,key,checkpoint=checkpoint)[0]
assert not v.verify_chain(chain[:-1],key,checkpoint=checkpoint)[0]
assert not v.verify_record(v.read_json(data/'tampered.json'),key)[0]
assert not v.verify_record(v.read_json(data/'attacker.json'),key)[0]
for bad in [None,[],{},1,'x',{'signature':[]}]:assert not v.verify_record(bad,key)[0]
print('PASS: no CorrLog installed; network disabled; trusted chain accepted; truncation, tamper, attacker and malformed records rejected')
