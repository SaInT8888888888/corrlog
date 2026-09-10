#!/usr/bin/env bash
# Clean-room reproduction of the full CorrLog validation.
#
# From a bare machine with only `uv` and `git`, this script:
#   1. clones corrlog at the validated commit
#   2. applies the validation fixes (report/corrlog-validation-fixes.patch)
#   3. builds fresh venvs: fixed build, published 0.2.1, oracle-only, two Inspect envs
#   4. runs every suite and writes the evidence JSON files
#
# Usage:
#   CORRLOG_REPO=https://github.com/SaInT8888888888/corrlog.git \
#   VALIDATION_DIR=/path/to/this/directory \
#   WORK=/tmp/corrlog-cleanroom \
#   bash run_all.sh
#
# Everything is deterministic. Re-running overwrites the evidence files.

set -euo pipefail

REPO="${CORRLOG_REPO:-https://github.com/SaInT8888888888/corrlog.git}"
VALIDATION_DIR="${VALIDATION_DIR:-/home/shane/corrlog-validation}"
WORK="${WORK:-/tmp/corrlog-cleanroom}"
HEAD_COMMIT="${CORRLOG_COMMIT:-b85910d}"
PATCH="$VALIDATION_DIR/report/corrlog-validation-fixes.patch"

SRC="$WORK/corrlog"            # patched source tree
ENV_FIXED="$WORK/env-fixed"    # fixed build
ENV_CLEAN="$WORK/env-clean"    # published 0.2.1 from PyPI
ENV_ORACLE="$WORK/env-oracle"  # third-party oracle only, no corrlog code
ENV_INSPECT="$WORK/env-inspect" # fixed build + inspect-ai
ENV_NOCORE="$WORK/env-nocore"  # inspect-ai + corrlog-inspect WITHOUT core extra
WHL="$WORK/wheels"
EVID="$VALIDATION_DIR/evidence"

echo "== 0. workspace $WORK"
mkdir -p "$WORK" "$WHL" "$EVID"

echo "== 1. source"
if [ ! -d "$SRC/.git" ]; then
  git clone -q "$REPO" "$SRC"
fi
git -C "$SRC" fetch -q origin || true
git -C "$SRC" reset -q --hard "$HEAD_COMMIT"
git -C "$SRC" apply "$PATCH"
echo "   source at $(git -C "$SRC" rev-parse --short HEAD) with validation fixes applied"

echo "== 2. venvs"
for e in "$ENV_FIXED" "$ENV_CLEAN" "$ENV_ORACLE" "$ENV_INSPECT" "$ENV_NOCORE"; do
  [ -d "$e" ] || uv venv --quiet "$e"
done
PY_FIXED="$ENV_FIXED/bin/python"; PY_CLEAN="$ENV_CLEAN/bin/python"
PY_ORACLE="$ENV_ORACLE/bin/python"; PY_INSPECT="$ENV_INSPECT/bin/python"
PY_NOCORE="$ENV_NOCORE/bin/python"

echo "== 3. wheels"
uv build --quiet --out-dir "$WHL" "$SRC"
uv build --quiet --out-dir "$WHL" "$SRC/corrlog_inspect"

echo "== 4. install"
uv pip install --quiet --python "$PY_FIXED" \
  "$WHL"/corrlog_core-*.whl cryptography pytest jsonschema
uv pip install --quiet --python "$PY_CLEAN" corrlog-core==0.2.1
uv pip install --quiet --python "$PY_ORACLE" rfc8785 cryptography
uv pip install --quiet --python "$PY_INSPECT" \
  "$WHL"/corrlog_core-*.whl "$WHL"/corrlog_inspect-*.whl inspect-ai pytest
uv pip install --quiet --python "$PY_NOCORE" \
  "$WHL"/corrlog_inspect-*.whl inspect-ai --no-deps
uv pip install --quiet --python "$PY_NOCORE" inspect-ai

echo
echo "############################################################"
echo "# 1. project test suite (fixed build)"
echo "############################################################"
(cd /tmp && "$PY_FIXED" -m pytest "$SRC/tests" -q --no-header -p no:cacheprovider \
  --ignore="$SRC/tests/test_inspect.py")

echo
echo "############################################################"
echo "# 2. project test suite (Inspect adapter)"
echo "############################################################"
(cd /tmp && "$PY_INSPECT" -m pytest "$SRC/tests/test_inspect.py" -q --no-header -p no:cacheprovider)

echo
echo "############################################################"
echo "# 3. RFC 8785 conformance: official vectors + third-party oracle"
echo "############################################################"
(cd /tmp && "$PY_ORACLE" "$VALIDATION_DIR/harness/test_jcs_candidate.py")

echo
echo "############################################################"
echo "# 4. core matrix, claims 1 to 9"
echo "############################################################"
# The matrix exits non-zero when tests fail. That is a RESULT, not a script
# error: the run must continue so claim 10 and the migration check still run.
# The FAIL count is printed above and recorded in the evidence JSON.
(cd /tmp && CORRLOG_PY="$PY_FIXED" CORRLOG_ORACLE_PY="$PY_ORACLE" \
  CORRLOG_MATRIX_OUT="$EVID/matrix_FINAL.json" \
  "$PY_FIXED" "$VALIDATION_DIR/harness/matrix.py") || echo "   (matrix exited non-zero: see the FAIL count above)"

echo
echo "############################################################"
echo "# 5. Inspect end-to-end matrix, claim 10"
echo "############################################################"
(cd /tmp && CORRLOG_INSPECT_PY="$PY_INSPECT" CORRLOG_NOCORE_PY="$PY_NOCORE" \
  CORRLOG_ORACLE_PY="$PY_ORACLE" \
  CORRLOG_INSPECT_MATRIX_OUT="$EVID/matrix_inspect.json" \
  "$PY_FIXED" "$VALIDATION_DIR/harness/inspect_e2e_matrix.py") || echo "   (see the claim 10 PASS/FAIL count above)"

echo
echo "############################################################"
echo "# 6. migration impact: published 0.2.1 vs fixed"
echo "############################################################"
(cd /tmp && CORRLOG_OLD_PY="$PY_CLEAN" CORRLOG_NEW_PY="$PY_FIXED" \
  "$PY_CLEAN" "$VALIDATION_DIR/harness/migration_impact.py") || true

echo
echo "############################################################"
echo "# 7. render deliverable B from the fresh evidence"
echo "############################################################"
(cd /tmp && "$PY_FIXED" "$VALIDATION_DIR/harness/gen_matrix_md.py")

echo
echo "done. evidence in $EVID, matrix in $VALIDATION_DIR/report/B_TEST_MATRIX.md"
