#!/usr/bin/env python3
"""AUD-0045 Probe 2: execute gates against empty/absent input; classify fail-open.

A gate that exits 0 on empty input without printing a measured count is fail-open.
Also runs known-bad control: empty catalog / missing path must be non-zero where applicable.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT_DIR = Path(__file__).resolve().parent


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 90, env=None) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd,
            cwd=str(cwd or REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        return r.returncode, ((r.stdout or "") + (r.stderr or ""))[-8000:]
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except OSError as e:
        return 127, f"{type(e).__name__}: {e}"


def has_measured_count(text: str) -> bool:
    return bool(
        re.search(
            r"\b(\d+)\s+(items?|violations?|files?|gates?|checks?|paths?|errors?|findings?)\b"
            r"|items[=:]\s*\d+|violations[=:]\s*\d+|count[=:]\s*\d+|CHECKED\s+\d+|scanned[=:]\s*\d+",
            text,
            re.I,
        )
    )


def classify(exit_code: int, output: str, label: str) -> dict:
    measured = has_measured_count(output)
    fail_open = exit_code == 0 and not measured
    return {
        "label": label,
        "exit_code": exit_code,
        "measured_count_printed": measured,
        "fail_open": fail_open,
        "output_tail": output[-1500:],
    }


def main() -> int:
    cases = []

    # --- validate.py defaults (require_complete default False) ---
    rc, out = run([sys.executable, "tools/command-center/validate.py"])
    cases.append(classify(rc, out, "validate.py defaults (no --require-complete)"))

    rc2, out2 = run([sys.executable, "tools/command-center/validate.py", "--require-complete"])
    cases.append(classify(rc2, out2, "validate.py --require-complete"))

    # Empty catalog input
    with tempfile.TemporaryDirectory() as td:
        empty_cat = Path(td) / "empty-catalog.json"
        empty_cat.write_text(json.dumps({"items": [], "defaults": {}}), encoding="utf-8")
        # also need a graph path — point at missing
        missing_graph = Path(td) / "missing-graph.json"
        rc3, out3 = run(
            [
                sys.executable,
                "tools/command-center/validate.py",
                "--catalog",
                str(empty_cat),
                "--graph",
                str(missing_graph),
            ]
        )
        cases.append(classify(rc3, out3, "validate.py empty-catalog + missing-graph"))

        # known-bad: empty items WITH a graph file present
        graph = Path(td) / "graph.json"
        graph.write_text(json.dumps({"nodes": [], "edges": []}), encoding="utf-8")
        rc4, out4 = run(
            [
                sys.executable,
                "tools/command-center/validate.py",
                "--catalog",
                str(empty_cat),
                "--graph",
                str(graph),
            ]
        )
        cases.append(classify(rc4, out4, "validate.py empty-catalog + empty-graph (known-bad)"))

    # unitgate with no args / help
    if (REPO / "tools/measure-guard/unitgate.py").is_file():
        rc, out = run([sys.executable, "tools/measure-guard/unitgate.py", "--help"])
        cases.append(
            {
                "label": "unitgate.py --help (info only)",
                "exit_code": rc,
                "measured_count_printed": has_measured_count(out),
                "fail_open": False,  # help is not a measurement gate pass
                "output_tail": out[-800:],
            }
        )
        rc, out = run([sys.executable, "tools/measure-guard/unitgate.py"])
        cases.append(classify(rc, out, "unitgate.py no-args"))

    # interpreter_floor_gate
    if (REPO / "command-center/ci/interpreter_floor_gate.py").is_file():
        rc, out = run([sys.executable, "command-center/ci/interpreter_floor_gate.py", "--self-test"])
        cases.append(classify(rc, out, "interpreter_floor_gate.py --self-test"))

    # mcp-audit ci_gate self-test
    if (REPO / "command-center/mcp-audit/ci_gate.py").is_file():
        rc, out = run([sys.executable, "command-center/mcp-audit/ci_gate.py", "--self-test"], timeout=180)
        cases.append(classify(rc, out, "mcp-audit/ci_gate.py --self-test"))

    # rail_count_gate
    if (REPO / "command-center/p2-next/rail_count_gate.py").is_file():
        rc, out = run([sys.executable, "command-center/p2-next/rail_count_gate.py", "--self-test"])
        cases.append(classify(rc, out, "rail_count_gate.py --self-test"))

    # claim_gate
    claim = REPO / ".agents/skills/claim-verify-gate/scripts/claim_gate.py"
    if claim.is_file():
        rc, out = run([sys.executable, str(claim.relative_to(REPO)), "--self-test"])
        cases.append(classify(rc, out, "claim_gate.py --self-test"))

    # check_citations
    if (REPO / "command-center/hook-audit/check_citations.py").is_file():
        rc, out = run([sys.executable, "command-center/hook-audit/check_citations.py", "--self-test"])
        cases.append(classify(rc, out, "check_citations.py --self-test"))

    # ssot_drift_gate
    if (REPO / "command-center/ssot/ssot_drift_gate.py").is_file():
        rc, out = run([sys.executable, "command-center/ssot/ssot_drift_gate.py"])
        cases.append(classify(rc, out, "ssot_drift_gate.py default"))

    # CLEAN + checks:NONE style: create a tiny fake "gate" runner observation for
    # tools that accept empty path lists — suitefloor without suite
    if (REPO / "tools/measure-guard/suitefloor.py").is_file():
        rc, out = run([sys.executable, "tools/measure-guard/suitefloor.py"])
        cases.append(classify(rc, out, "suitefloor.py no-args"))

    fail_open_cases = [c for c in cases if c.get("fail_open")]
    # Control: known-bad empty catalog must be non-zero
    known_bad = next((c for c in cases if "known-bad" in c["label"]), None)
    known_bad_ok = bool(known_bad and known_bad["exit_code"] != 0)
    # Measuring-nothing: exit 0 on both empty and known-bad
    empty_case = next((c for c in cases if "empty-catalog + missing-graph" in c["label"]), None)
    measures_nothing = bool(
        empty_case
        and known_bad
        and empty_case["exit_code"] == 0
        and known_bad["exit_code"] == 0
    )

    result = {
        "unit": "AUD-0045",
        "stage": "linux-local-remeasure",
        "cases": cases,
        "case_count": len(cases),
        "fail_open_count": len(fail_open_cases),
        "fail_open_labels": [c["label"] for c in fail_open_cases],
        "known_bad_nonzero": known_bad_ok,
        "measures_nothing_validate": measures_nothing,
        "ok": len(cases) > 0 and known_bad_ok,
    }
    (OUT_DIR / "probe2-execution-results.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "AUD-0045 NAMED PROBE 2: execute gates on empty/absent/known-bad inputs",
        f"unit=AUD-0045",
        f"case_count={len(cases)}",
        f"fail_open_count={len(fail_open_cases)}",
        f"fail_open_labels={result['fail_open_labels']!r}",
        f"known_bad_nonzero={known_bad_ok}",
        f"measures_nothing_validate={measures_nothing}",
    ]
    for c in cases:
        lines.append(
            f"CASE {c['label']}: exit={c['exit_code']} measured={c['measured_count_printed']} fail_open={c.get('fail_open')}"
        )
    lines.append("SUCCESS:AUD-0045-probe2" if result["ok"] else "FAILED:AUD-0045-probe2")
    raw = "\n".join(lines) + "\n"
    (OUT_DIR / "probe2-execution.raw.txt").write_text(raw, encoding="utf-8")
    sys.stdout.write(raw)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
