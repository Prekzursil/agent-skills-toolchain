"""BUILD-R1 probe: execute every rule-audit gate and record its terminal state.

Read-only with respect to the repo: each gate is run with NO output arguments, so
rule_audit.py's --json/--md writers stay dormant. Writes only its own JSON receipt.

Why: the grounding claims 0 of 8 gates are CI-wired. Before wiring them, measure
which ones actually execute -- the sibling lane found 5 of 14 could not run.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

GATES = [
    "rule_audit.py",
    "lazy_predict.py",
    "r2_control_count_gate.py",
    "r2_failclosed_mutation.py",
    "r2_pathrefs.py",
    "r3_corpus_parity_gate.py",
    "r4_credential_rule_gate.py",
    "r4_receipt_argv_gate.py",
]

TIMEOUT_SEC = 120


def tail(text: str, n: int = 1200) -> str:
    text = text.replace("\r\n", "\n")
    return text[-n:] if len(text) > n else text


def main() -> int:
    results = []
    for name in GATES:
        path = HERE / name
        rec: dict[str, object] = {"gate": name, "exists": path.is_file()}
        if not path.is_file():
            rec["state"] = "MISSING"
            results.append(rec)
            continue
        try:
            proc = subprocess.run(
                [sys.executable, str(path)],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SEC,
            )
            rec["returncode"] = proc.returncode
            rec["stdout_tail"] = tail(proc.stdout)
            rec["stderr_tail"] = tail(proc.stderr)
            rec["stdout_bytes"] = len(proc.stdout)
            if proc.returncode == 0:
                rec["state"] = "RUNS_PASS"
            elif "Traceback" in proc.stderr:
                rec["state"] = "CRASHES"
            else:
                rec["state"] = "RUNS_FAIL"
        except subprocess.TimeoutExpired:
            rec["state"] = "TIMEOUT"
        except OSError as exc:  # pragma: no cover - defensive
            rec["state"] = "SPAWN_ERROR"
            rec["error"] = str(exc)
        results.append(rec)
        print(f"{name}: {rec['state']} rc={rec.get('returncode')}", flush=True)

    out = {
        "repo": str(REPO),
        "python": sys.version.split()[0],
        "gates": results,
        "summary": {
            state: sum(1 for r in results if r.get("state") == state)
            for state in sorted({str(r.get("state")) for r in results})
        },
    }
    (HERE / "_b1_gate_runner.json").write_text(
        json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(out["summary"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
