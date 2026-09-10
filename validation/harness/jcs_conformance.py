import json, os, sys, glob
from corrlog_core import canonical_json
BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vectors", "jcs-testdata")
IN = os.path.join(BASE, "input"); OUT = os.path.join(BASE, "output")
files = sorted(glob.glob(os.path.join(IN, "*.json")))
passed, failed, errs = [], [], []
for f in files:
    name = os.path.basename(f)[:-5]
    outpath = os.path.join(OUT, name + ".json")
    if not os.path.exists(outpath):
        continue
    with open(f, "rb") as fh:
        data = json.load(fh)
    expected = open(outpath, "rb").read()
    try:
        got = canonical_json(data)
    except Exception as e:
        errs.append((name, f"raised {type(e).__name__}: {e}")); continue
    if got == expected:
        passed.append(name)
    else:
        failed.append((name, expected[:90], got[:90]))
print(f"OFFICIAL JCS CONFORMANCE SUITE (cyberphone/json-canonicalization)")
print(f"  vectors run : {len(passed)+len(failed)+len(errs)}")
print(f"  PASS        : {len(passed)}  {passed}")
print(f"  FAIL        : {len(failed)}")
for n, e, g in failed:
    print(f"     - {n}\n         expected: {e!r}\n         got     : {g!r}")
if errs:
    print(f"  ERRORED     : {len(errs)}")
    for n, e in errs:
        print(f"     - {n}: {e}")
