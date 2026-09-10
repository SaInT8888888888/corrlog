#!/usr/bin/env python3
"""Fresh wheel validation. Usage: python validation/run_current.py --work NEW_DIRECTORY.
Network needed for installs only. No reset, commit, push or publishing operations.
Use --redirect-inspect-data on a restricted macOS host (test path shim only).
Historical matrices may fail on withdrawn claims; their exit codes are recorded.
"""
import argparse, json, os, pathlib, shutil, subprocess, sys
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--work', required=True)
p.add_argument('--redirect-inspect-data', action='store_true')
a=p.parse_args();w=pathlib.Path(a.work).resolve();w.mkdir(parents=True,exist_ok=False)
root=pathlib.Path(__file__).resolve().parents[1]
evidence=w/'evidence';evidence.mkdir()
status={}
def run(name,cmd,env=None,required=True,cwd=None):
    r=subprocess.run([str(x) for x in cmd],env=env,cwd=cwd or w,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    (evidence/(name+'.log')).write_text(r.stdout)
    status[name]=r.returncode
    (evidence/'status.json').write_text(json.dumps(status,indent=2))
    print(name,r.returncode,flush=True)
    if required and r.returncode:raise SystemExit(r.returncode)
def py(name):return w/name/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
for name in ['builder','installed','oracle','nocore','legacy']:
    run('venv-'+name,[sys.executable,'-m','venv',w/name])
run('build-install',[py('builder'),'-m','pip','install','build'])
run('build-core',[py('builder'),'-m','build','--outdir',w/'wheels',root])
run('build-inspect',[py('builder'),'-m','build','--outdir',w/'wheels',root/'corrlog_inspect'])
core=next((w/'wheels').glob('corrlog_core-*.whl'));inspect=next((w/'wheels').glob('corrlog_inspect-*.whl'))
run('install',[py('installed'),'-m','pip','install',core,inspect,'pytest','rfc8785'])
run('oracle-install',[py('oracle'),'-m','pip','install','rfc8785','cryptography','jsonschema[format-nongpl]'])
run('nocore-install',[py('nocore'),'-m','pip','install',inspect])
run('legacy-install',[py('legacy'),'-m','pip','install','corrlog-core==0.2.1'])
for name in ['installed','oracle','nocore','legacy']:
    run('requirements-'+name,[py(name),'-m','pip','freeze'])
    run('pip-check-'+name,[py(name),'-m','pip','check'])
run('oracle-isolation',[py('oracle'),'-c','import importlib.util; assert importlib.util.find_spec("corrlog_core") is None'])
tests=w/'test-copy';tests.mkdir()
for name in ['tests','verifier']:
    shutil.copytree(root/name,tests/name,ignore=shutil.ignore_patterns('__pycache__'))
(tests/'corrlog_core/schema').mkdir(parents=True)
shutil.copy(root/'corrlog_core/schema/acr-v1.json',tests/'corrlog_core/schema/acr-v1.json')
run('installed-suite',[py('installed'),'-m','pytest',tests/'tests','-q','-p','no:cacheprovider'])
env=dict(os.environ,CORRLOG_PY=str(py('installed')),CORRLOG_ORACLE_PY=str(py('oracle')),
         CORRLOG_MATRIX_OUT=str(evidence/'core-matrix.json'),CORRLOG_INSPECT_PY=str(py('installed')),
         CORRLOG_NOCORE_PY=str(py('nocore')),CORRLOG_INSPECT_MATRIX_OUT=str(evidence/'inspect-matrix.json'),
         CORRLOG_OLD_PY=str(py('legacy')),CORRLOG_NEW_PY=str(py('installed')))
if a.redirect_inspect_data:
    shim=w/'path-shim';shim.mkdir()
    shutil.copy(root/'validation/inspect-path-shim.py',shim/'sitecustomize.py')
    env.update(PYTHONPATH=str(shim),CORRLOG_TEST_APPDATA=str(w/'appdata'))
for label,script,python in [('core-matrix','matrix.py','installed'),('inspect-matrix','inspect_e2e_matrix.py','installed'),('migration','migration_impact.py','legacy')]:
    run(label,[py(python),root/'validation/harness'/script],env,required=False)
run('create-offline-records',[py('installed'),root/'validation/create_offline_records.py',w/'offline-records'])
run('offline-gate',[py('oracle'),root/'validation/offline_gate.py',root,w/'offline-records'])
print('Evidence:', evidence)
