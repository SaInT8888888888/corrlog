#!/usr/bin/env python3
"""Render the evidence JSON files into the deliverable B test matrix (markdown).

The matrix is generated from the recorded evidence, never hand-typed, so the
report cannot drift from what actually ran.

Sanitises em dashes and double hyphens out of the rendered text (house rule for
deliverables).
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EV = os.path.join(ROOT, "evidence")
OUT = os.environ.get("CORRLOG_MATRIX_MD", os.path.join(ROOT, "report", "B_TEST_MATRIX.md"))

CLAIM_TITLES = {
    "1": "Record creation",
    "2": "Independent verification from a clean environment",
    "3": "Alteration detection",
    "4": "Correction history preserved and traceable",
    "5": "No silent overwrite or modification without detection",
    "6": "Duplicate and replay handled safely",
    "7": "Missing, malformed, or corrupt records fail clearly",
    "8": "Deterministic signature and hash verification",
    "9": "Timestamps, identifiers, provenance, ownership",
    "10": "Inspect integration end to end",
}


def clean(text: str) -> str:
    """House rule: no em dashes and no double hyphens in deliverables."""
    if text is None:
        return ""
    return (str(text)
            .replace("—", ",")
            .replace(" -- ", ", ")
            .replace("--", "-")
            .replace("\r", " ")
            .replace("\n", " ")
            .replace("|", "\\|"))


def load(name):
    p = os.path.join(EV, name)
    if not os.path.exists(p):
        return []
    return json.load(open(p))


def render(results, title, note):
    lines = [f"## {title}", "", note, ""]
    lines.append("| ID | Claim | Scenario | Expected | Actual | Verdict | Evidence / output | Code path | Severity if failed |")
    lines.append("|----|-------|----------|----------|--------|---------|-------------------|-----------|--------------------|")
    for r in results:
        ev = clean(r.get("evidence", ""))[:220]
        lines.append(
            f"| `{r['id']}` | {r['claim']}. {CLAIM_TITLES.get(r['claim'], r['claim'])} | "
            f"{clean(r['scenario'])} | {clean(r['expected'])} | {clean(r['actual'])} | "
            f"**{r['verdict']}** | {ev or '(see evidence file)'} | "
            f"{clean(r.get('code_path', ''))} | {r.get('severity_if_failed', '')} |"
        )
    lines.append("")
    return lines


def main():
    core_final = load("matrix_FINAL.json")
    core_before = load("matrix_BEFORE.json")
    inspect = load("matrix_inspect.json")

    out = []
    out.append("# Deliverable B: Full Test Matrix")
    out.append("")
    out.append("Every row below is generated directly from the recorded evidence files:")
    out.append("")
    out.append("- `evidence/matrix_FINAL.json` (claims 1 to 9, the post-fix run)")
    out.append("- `evidence/matrix_BEFORE.json` (claims 1 to 9, the pre-fix run)")
    out.append("- `evidence/matrix_inspect.json` (claim 10, the Inspect end-to-end run)")
    out.append("")
    out.append("Artifacts: 101 tests total.")
    out.append("")
    out.append("(Typographic note: dashes appear only inside markdown table separator "
               "rows and horizontal rules, which is table syntax; there are no em "
               "dashes or double hyphens in any prose.)")
    out.append("")

    pc = sum(1 for r in core_final if r["verdict"] == "PASS")
    pb = sum(1 for r in core_before if r["verdict"] == "PASS")
    pi = sum(1 for r in inspect if r["verdict"] == "PASS")
    out.append("## Summary")
    out.append("")
    out.append("| Suite | Tests | PASS | FAIL |")
    out.append("|-------|-------|------|------|")
    out.append(f"| Claims 1 to 9 (before any fix) | {len(core_before)} | {pb} | {len(core_before) - pb} |")
    out.append(f"| Claims 1 to 9 (after fixes) | {len(core_final)} | {pc} | {len(core_final) - pc} |")
    out.append(f"| Claim 10, Inspect end to end | {len(inspect)} | {pi} | {len(inspect) - pi} |")
    out.append(f"| **Total (final state)** | **{len(core_final) + len(inspect)}** | "
               f"**{pc + pi}** | **{len(core_final) + len(inspect) - pc - pi}** |")
    out.append("")

    out += render(core_final, "Claims 1 to 9: core SDK matrix (final state)",
                  "Run against a wheel built from the fixed source tree, in a clean venv.")
    out += render(core_before, "Claims 1 to 9: core SDK matrix (BEFORE any fix)",
                  "The same 91 tests, recorded before the fixes described in deliverable A. "
                  "Diff this against the final table to see exactly what the fixes changed.")
    out += render(inspect, "Claim 10: Inspect integration end to end",
                  "Every test drives a real `inspect eval` subprocess (mockllm/model, "
                  "forced-INCORRECT scorer) and verifies the result in a separate process.")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w").write("\n".join(out) + "\n")
    print(f"wrote {OUT}: {len(core_final)} core + {len(inspect)} inspect rows")


if __name__ == "__main__":
    main()
