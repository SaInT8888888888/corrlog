import glob, json, os, random, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rfc8785
from jcs_candidate import canonical_json

print("="*74); print("1. OFFICIAL JCS CONFORMANCE VECTORS"); print("="*74)
VEC = os.environ.get("CORRLOG_JCS_VECTORS", "/home/shane/corrlog-validation/vectors/jcs-testdata")
IN, OUT = f"{VEC}/input", f"{VEC}/output"
ok = fail = 0
for f in sorted(glob.glob(IN + "/*.json")):
    name = os.path.basename(f)[:-5]
    data = json.load(open(f))
    expected = open(os.path.join(OUT, name + ".json"), "rb").read()
    got = canonical_json(data)
    if got == expected: ok += 1; print(f"  PASS  {name}")
    else:
        fail += 1; print(f"  FAIL  {name}")
        i = next((k for k in range(min(len(got),len(expected))) if got[k]!=expected[k]), 0)
        print(f"        expected ...{expected[max(0,i-30):i+50]!r}")
        print(f"        got      ...{got[max(0,i-30):i+50]!r}")
print(f"  -> {ok}/{ok+fail} vectors pass")

print()
print("="*74); print("2. FUZZ vs third-party oracle rfc8785 (10k random values)"); print("="*74)
random.seed(20260910)
def rand_val(depth=0):
    r = random.random()
    if depth > 3 or r < 0.28:
        c = random.random()
        if c < 0.18: return random.randint(-2**60, 2**60)
        if c < 0.36:
            return struct.unpack("<d", struct.pack("<Q", random.getrandbits(64)))[0]
        if c < 0.42: return random.choice([0, -0.0, 1e16, 1e-7, 1e21, 1e-6, 5e-324, 1.7976931348623157e308, 2**53, 1e30, -0.0])
        if c < 0.62: return "".join(random.choice("abcXYZ019 \t\n\"\\é€日本語\U0001F600\u007f\u0000") for _ in range(random.randint(0,6)))
        if c < 0.72: return random.choice([True, False, None])
        if c < 0.80: return random.choice(["\u2028","\u2029","\u0080","\ufffd","\U00010000"])
        return random.choice(["-", "", " ", "\u0000"])
    if r < 0.64: return [rand_val(depth+1) for _ in range(random.randint(0,4))]
    return {"".join(random.choice("abzAZ09é\U0001F600\ufffd\u0001") for _ in range(random.randint(0,3))): rand_val(depth+1) for _ in range(random.randint(0,4))}

mismatch = errors = checked = 0
examples = []
for n in range(10000):
    v = rand_val()
    try:
        theirs = rfc8785.dumps(v)
    except Exception:
        continue          # oracle rejects (e.g. non-string keys); not a comparable case
    try:
        ours = canonical_json(v)
    except Exception as e:
        errors += 1
        if len(examples) < 5: examples.append(("we raised", v, f"{type(e).__name__}: {e}"))
        continue
    checked += 1
    if ours != theirs:
        mismatch += 1
        if len(examples) < 5: examples.append(("mismatch", v, (theirs[:70], ours[:70])))
print(f"  comparable cases : {checked}")
print(f"  byte-identical   : {checked-mismatch}  ({(checked-mismatch)/max(1,checked)*100:.3f}%)")
print(f"  MISMATCH         : {mismatch}")
print(f"  we raised        : {errors}")
for kind, v, d in examples:
    print(f"    {kind}: {json.dumps(v)[:90]}\n       {d}")
