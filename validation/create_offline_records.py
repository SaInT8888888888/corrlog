import json,sys
from pathlib import Path
from corrlog_core import generate_keypair,record,retract,chain_checkpoint,public_key_b64url
p=Path(sys.argv[1]);p.mkdir(exist_ok=True)
sk,pk=generate_keypair()
r=record(agent_id='model',action_type='test',private_key=sk)
c=retract(prior_record=r,reason='café 😀',trigger='check_failed',agent_id='model',private_key=sk)
attacker,_=generate_keypair()
objects={'root.json':r,'correction.json':c,'trusted-key.json':{'publicKey':public_key_b64url(pk)},'checkpoint.json':chain_checkpoint([r,c]),'tampered.json':dict(c,reason='changed'),'attacker.json':record(agent_id='model',action_type='test',private_key=attacker)}
for name,obj in objects.items():(p/name).write_text(json.dumps(obj))
