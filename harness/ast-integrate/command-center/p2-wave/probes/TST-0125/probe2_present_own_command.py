#!/usr/bin/env python3
"""test_present_thresholds_file_runs_its_own_enforcement_command"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from resolver import FAIL, NOT_CHECKED, PASS, evaluate_project  # noqa: E402


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def plant(project: Path, token: str, line: int, branch: int) -> Path:
    write(project / "pyproject.toml", f"[project]\nname='{project.name}'\nversion='0'\n")
    marker = project / "ran.txt"
    enforce = project / "enforce.py"
    write(
        enforce,
        (
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text({token!r} + '\\n', encoding='utf-8')\n"
        ),
    )
    thresholds = project / ".coverage-thresholds.json"
    write(
        thresholds,
        json.dumps(
            {
                "thresholds": {"line": line, "branch": branch},
                "enforcement": {"command": "python3 enforce.py"},
            },
            indent=2,
        )
        + "\n",
    )
    return thresholds


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0125-p2-") as tmp:
        root = Path(tmp)
        proj_a = root / "proj-a"
        proj_b = root / "proj-b"
        file_a = plant(proj_a, "TOKEN-A-OWN-COMMAND", 81, 70)
        file_b = plant(proj_b, "TOKEN-B-OWN-COMMAND", 92, 80)

        row_a = evaluate_project(proj_a, repo=root)
        row_b = evaluate_project(proj_b, repo=root)

        ran_a = (proj_a / "ran.txt").read_text(encoding="utf-8").strip() if (proj_a / "ran.txt").is_file() else ""
        ran_b = (proj_b / "ran.txt").read_text(encoding="utf-8").strip() if (proj_b / "ran.txt").is_file() else ""

        # Cross-wiring trap: A's tree must not contain B's token and vice versa.
        a_files = "\n".join(p.read_text(encoding="utf-8") for p in proj_a.iterdir() if p.is_file())
        b_files = "\n".join(p.read_text(encoding="utf-8") for p in proj_b.iterdir() if p.is_file())

    if row_a["verdict"] != PASS or row_b["verdict"] != PASS:
        print("FAILED:TST-0125-probe2 present file did not PASS on its own command")
        print(json.dumps({"a": row_a, "b": row_b}, indent=2)[:4000])
        return 1
    if row_a["verdict"] == NOT_CHECKED or row_b["verdict"] == NOT_CHECKED:
        print("FAILED:TST-0125-probe2 present file emitted NOT-CHECKED")
        return 1
    if row_a["exit_code"] != 0 or row_b["exit_code"] != 0:
        print("FAILED:TST-0125-probe2 enforcement exit was not 0")
        return 1
    if ran_a != "TOKEN-A-OWN-COMMAND" or ran_b != "TOKEN-B-OWN-COMMAND":
        print(f"FAILED:TST-0125-probe2 tokens a={ran_a!r} b={ran_b!r}")
        return 1
    if row_a.get("thresholds_file") != ".coverage-thresholds.json" and not str(
        row_a.get("thresholds_file")
    ).endswith("proj-a/.coverage-thresholds.json"):
        print(f"FAILED:TST-0125-probe2 A did not name its thresholds file: {row_a.get('thresholds_file')}")
        return 1
    if row_b.get("thresholds_file") != ".coverage-thresholds.json" and not str(
        row_b.get("thresholds_file")
    ).endswith("proj-b/.coverage-thresholds.json"):
        print(f"FAILED:TST-0125-probe2 B did not name its thresholds file: {row_b.get('thresholds_file')}")
        return 1
    if "TOKEN-B-OWN-COMMAND" in a_files or "TOKEN-A-OWN-COMMAND" in b_files:
        print("FAILED:TST-0125-probe2 cross-project command leak")
        return 1
    if row_a.get("enforcement_command") != "python3 enforce.py":
        print(f"FAILED:TST-0125-probe2 A used unexpected command {row_a.get('enforcement_command')}")
        return 1
    if (row_a.get("thresholds") or {}).get("line") != 81:
        print("FAILED:TST-0125-probe2 A threshold value not taken from its own file")
        return 1
    if (row_b.get("thresholds") or {}).get("line") != 92:
        print("FAILED:TST-0125-probe2 B threshold value not taken from its own file")
        return 1
    if row_a["thresholds_file"] == row_b["thresholds_file"]:
        print("FAILED:TST-0125-probe2 both projects named the same thresholds file")
        return 1

    out = {
        "probe": "probe2-present-own-command",
        "unit_id": "TST-0125",
        "test": "test_present_thresholds_file_runs_its_own_enforcement_command",
        "a": {
            "verdict": row_a["verdict"],
            "thresholds_file": row_a["thresholds_file"],
            "thresholds": row_a["thresholds"],
            "command": row_a["enforcement_command"],
            "exit_code": row_a["exit_code"],
            "token": ran_a,
            "named_file": str(file_a.name),
        },
        "b": {
            "verdict": row_b["verdict"],
            "thresholds_file": row_b["thresholds_file"],
            "thresholds": row_b["thresholds"],
            "command": row_b["enforcement_command"],
            "exit_code": row_b["exit_code"],
            "token": ran_b,
            "named_file": str(file_b.name),
        },
        "cross_project_leak": False,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"A={row_a['verdict']} file={row_a['thresholds_file']} token={ran_a} "
        f"B={row_b['verdict']} file={row_b['thresholds_file']} token={ran_b} "
        f"FAIL={FAIL}"
    )
    print("SUCCESS:TST-0125-probe2 present file runs its own enforcement command")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
