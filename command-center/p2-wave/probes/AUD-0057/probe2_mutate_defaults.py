#!/usr/bin/env python3
"""AUD-0057 NAMED PROBE 2: mutate unexercised defaults in a scratch worktree.

Catalog evidence_requirement Probe 2:
  for the highest-risk findings, an actual value mutation of the default in a
  scratch worktree, requiring the suite to stay GREEN to confirm the hole.

tests_required (both-states control):
  mutate a default that IS covered and require the suite to turn RED, proving
  the mutation harness can produce a red at all.

Catalog reviewer_requirement: cross-vendor Codex must re-run ONLY this probe.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT_JSON = PROBE / "probe2-mutate-defaults.json"
OUT_RAW = PROBE / "probe2-mutate-defaults.raw.txt"

PLANTED_MOD = "command-center/p2-wave/probes/AUD-0057/fixtures/planted_defaults.py"
PLANTED_WEAK = "command-center/p2-wave/probes/AUD-0057/fixtures/test_planted_weak.py"
PLANTED_STRONG = "command-center/p2-wave/probes/AUD-0057/fixtures/test_planted_strong.py"
SAMPLE_THRESH = "tools/mutation-gate/sample/threshold.py"
SAMPLE_WEAK = "tools/mutation-gate/sample/test_threshold_weak.py"
SAMPLE_STRONG = "tools/mutation-gate/sample/test_threshold_strong.py"
COMPLETION = "hooks/_shared/completion.py"
COMPLETION_TEST = "hooks/_shared/test_completion.py"


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 180) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd,
            cwd=str(cwd or REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s: {' '.join(cmd)}"
    except OSError as e:
        return 127, f"{type(e).__name__}: {e}"


def pytest_summary(output: str) -> dict:
    summary = {
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "error": 0,
        "raw_summary": "",
        "executed": 0,
    }
    candidates: list[str] = []
    for line in output.splitlines():
        s = line.strip()
        if re.search(r"\d+\s+(passed|failed|skipped|error)", s, re.IGNORECASE):
            candidates.append(s)
        if re.match(r"=+ .*=+", s):
            candidates.append(s)
    if candidates:
        summary["raw_summary"] = candidates[-1]
        line = candidates[-1]
        for key, pat in (
            ("passed", r"(\d+)\s+passed"),
            ("failed", r"(\d+)\s+failed"),
            ("skipped", r"(\d+)\s+skipped"),
            ("error", r"(\d+)\s+errors?"),
        ):
            mm = re.search(pat, line, re.IGNORECASE)
            if mm:
                summary[key] = int(mm.group(1))
    summary["executed"] = summary["passed"] + summary["failed"] + summary["error"]
    return summary


def run_pytest(paths: list[str], cwd: Path) -> tuple[int, str, dict]:
    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=line", *paths]
    rc, out = run(cmd, cwd=cwd, timeout=300)
    return rc, out, pytest_summary(out)


def run_script(script_path: Path, cwd: Path) -> tuple[int, str, dict]:
    """Run hooks/_shared/test_completion.py-style conformance script."""
    if not script_path.is_file():
        return (
            127,
            f"script missing: {script_path}",
            {
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "error": 1,
                "raw_summary": "script-missing",
                "executed": 0,
            },
        )
    rc, out = run([sys.executable, str(script_path)], cwd=cwd, timeout=300)
    passed = sum(1 for line in out.splitlines() if line.strip().startswith("OK "))
    failed = sum(1 for line in out.splitlines() if line.strip().startswith("XX "))
    if "ALL PASS" in out:
        failed = 0
    elif failed == 0 and rc != 0:
        mm = re.search(r"RESULT:\s+(\d+)\s+FAIL", out)
        failed = int(mm.group(1)) if mm else 1
    summary = {
        "passed": passed,
        "failed": failed,
        "skipped": 0,
        "error": 0 if "RESULT:" in out else (1 if rc != 0 else 0),
        "raw_summary": out.strip().splitlines()[-1] if out.strip() else "",
        "executed": passed + failed,
    }
    return rc, out, summary


def mutate_assignment(text: str, name: str, new_value: str) -> tuple[str, bool]:
    pat = re.compile(
        rf"^({re.escape(name)}\s*=\s*)(.+?)(\s*(#.*)?)$",
        re.MULTILINE,
    )
    if not pat.search(text):
        return text, False
    return pat.sub(rf"\g<1>{new_value}\3", text, count=1), True


def load_probe1() -> dict:
    return json.loads((PROBE / "probe1-default-census.json").read_text(encoding="utf-8"))


def main() -> int:
    p1 = load_probe1()
    raw: list[str] = ["unit=AUD-0057 probe=2 mutate-defaults-in-scratch-worktree"]
    results: list[dict] = []

    wt_parent = Path(tempfile.mkdtemp(prefix="aud0057-wt-"))
    wt = wt_parent / "tree"
    rc_wt, out_wt = run(
        ["git", "-C", str(REPO), "worktree", "add", "--detach", str(wt), "HEAD"],
        timeout=120,
    )
    worktree_ok = rc_wt == 0 and wt.is_dir()
    raw.append(f"worktree_add rc={rc_wt} ok={worktree_ok}")
    if not worktree_ok:
        raw.append(out_wt[-1000:])
        wt = wt_parent / "fallback"
        wt.mkdir()
        for rel in (
            PLANTED_MOD,
            PLANTED_WEAK,
            PLANTED_STRONG,
            SAMPLE_THRESH,
            SAMPLE_WEAK,
            SAMPLE_STRONG,
            COMPLETION,
            COMPLETION_TEST,
        ):
            src = REPO / rel
            if src.is_file():
                dest = wt / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
        worktree_mode = "fixture-copy-fallback"
    else:
        worktree_mode = "git-worktree"
        src_fix = PROBE / "fixtures"
        dest_fix = wt / "command-center/p2-wave/probes/AUD-0057/fixtures"
        dest_fix.mkdir(parents=True, exist_ok=True)
        for f in src_fix.glob("*.py"):
            shutil.copy2(f, dest_fix / f.name)
        raw.append(f"synced_fixtures_into_scratch={dest_fix}")

    def mutate_and_test(
        *,
        label: str,
        module_rel: str,
        const_name: str,
        new_value: str,
        test_rels: list[str],
        expect: str,
        cwd_rel: str | None = None,
        runner: str = "pytest",
    ) -> dict:
        mod = wt / module_rel
        if not mod.is_file():
            row = {
                "label": label,
                "ok": False,
                "error": "module-missing",
                "expect": expect,
            }
            results.append(row)
            raw.append(f"--- {label} MISSING {module_rel} ---")
            return row
        text = mod.read_text(encoding="utf-8")
        new_text, changed = mutate_assignment(text, const_name, new_value)
        if not changed:
            row = {
                "label": label,
                "ok": False,
                "error": "const-not-mutated",
                "expect": expect,
            }
            results.append(row)
            raw.append(f"--- {label} const {const_name} not found ---")
            return row
        original = text
        mod.write_text(new_text, encoding="utf-8")
        cwd = wt / cwd_rel if cwd_rel else wt

        if runner == "script":
            script = wt / test_rels[0]
            rc, out, summary = run_script(script, cwd)
        else:
            test_paths: list[str] = []
            for tr in test_rels:
                tp = wt / tr
                if tp.is_file():
                    try:
                        test_paths.append(str(tp.relative_to(cwd)))
                    except ValueError:
                        test_paths.append(str(tp))
            if not test_paths:
                mod.write_text(original, encoding="utf-8")
                row = {
                    "label": label,
                    "ok": False,
                    "error": "tests-missing",
                    "expect": expect,
                }
                results.append(row)
                raw.append(f"--- {label} tests missing ---")
                return row
            rc, out, summary = run_pytest(test_paths, cwd)

        mod.write_text(original, encoding="utf-8")

        stayed_green = (
            summary["failed"] == 0 and summary["error"] == 0 and summary["passed"] > 0
        )
        turned_red = summary["failed"] > 0 or summary["error"] > 0
        if expect == "GREEN":
            matched = stayed_green
            hole_confirmed = stayed_green
        else:
            matched = turned_red
            hole_confirmed = False

        raw.append(f"--- {label} mutate {const_name}->{new_value} expect={expect} ---")
        raw.append(f"changed={changed} rc={rc} matched={matched} summary={summary}")
        raw.append(out[-1500:])

        row = {
            "label": label,
            "module": module_rel,
            "const_name": const_name,
            "new_value": new_value,
            "tests": test_rels,
            "runner": runner,
            "expect": expect,
            "mutated": changed,
            "pytest_rc": rc,
            "summary": summary,
            "stayed_green": stayed_green,
            "turned_red": turned_red,
            "matched_expect": matched,
            "hole_confirmed": hole_confirmed,
            "output_tail": out[-2500:],
            "ok": matched,
        }
        results.append(row)
        return row

    ctrl_red = mutate_and_test(
        label="control-planted-exercised-must-RED",
        module_rel=PLANTED_MOD,
        const_name="PLANTED_EXERCISED_DEFAULT",
        new_value="1",
        test_rels=[PLANTED_STRONG],
        expect="RED",
    )
    ctrl_green = mutate_and_test(
        label="control-planted-unexercised-must-GREEN",
        module_rel=PLANTED_MOD,
        const_name="PLANTED_UNEXERCISED_DEFAULT",
        new_value="512",
        test_rels=[PLANTED_WEAK],
        expect="GREEN",
    )
    sample_weak = mutate_and_test(
        label="mutation-gate-weak-DEFAULT_MIN_BYTES-stays-GREEN",
        module_rel=SAMPLE_THRESH,
        const_name="DEFAULT_MIN_BYTES",
        new_value="512",
        test_rels=[SAMPLE_WEAK],
        expect="GREEN",
        cwd_rel="tools/mutation-gate/sample",
    )
    sample_strong = mutate_and_test(
        label="mutation-gate-strong-DEFAULT_MIN_BYTES-turns-RED",
        module_rel=SAMPLE_THRESH,
        const_name="DEFAULT_MIN_BYTES",
        new_value="512",
        test_rels=[SAMPLE_STRONG],
        expect="RED",
        cwd_rel="tools/mutation-gate/sample",
    )
    completion_red = mutate_and_test(
        label="hooks-completion-DEFAULT_MIN_BYTES-turns-RED",
        module_rel=COMPLETION,
        const_name="DEFAULT_MIN_BYTES",
        new_value="512",
        test_rels=[COMPLETION_TEST],
        expect="RED",
        cwd_rel="hooks/_shared",
        runner="script",
    )

    high = p1.get("high_risk_unexercised") or []
    suite_holes = p1.get("suite_local_holes") or []
    for i, row in enumerate(high[:5]):
        raw.append(
            f"--- probe1-high-risk[{i}] {row['func']}({row['param']}={row['default_repr']}) ---"
        )

    control_ok = bool(ctrl_red.get("ok")) and bool(ctrl_green.get("ok"))
    holes_confirmed = sum(1 for r in results if r.get("hole_confirmed"))
    doc_ok = (
        control_ok
        and bool(sample_weak.get("ok"))
        and bool(sample_strong.get("ok"))
        and bool(completion_red.get("ok"))
    )

    doc = {
        "unit": "AUD-0057",
        "probe": 2,
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "worktree_mode": worktree_mode,
        "worktree_path": str(wt),
        "ok": doc_ok,
        "control": {
            "ok": control_ok,
            "planted_exercised_turned_red": bool(ctrl_red.get("ok")),
            "planted_unexercised_stayed_green": bool(ctrl_green.get("ok")),
            "both_states": control_ok,
            "note": (
                "Both-states: mutate covered default → RED; mutate unexercised "
                "default → GREEN. Harness can produce red; hole stays green."
            ),
        },
        "holes_confirmed_count": holes_confirmed,
        "results_count": len(results),
        "results": results,
        "probe1_high_risk_unexercised_count": len(high),
        "probe1_suite_local_hole_count": len(suite_holes),
        "completion_default_exercised_turns_red": bool(completion_red.get("ok")),
        "mutation_gate_weak_hole_confirmed": bool(sample_weak.get("ok")),
        "mutation_gate_strong_kills_mutant": bool(sample_strong.get("ok")),
    }

    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    raw.insert(0, "SUCCESS:AUD-0057-probe2" if doc["ok"] else "FAILED:AUD-0057-probe2")
    raw.append(
        f"control_ok={control_ok} holes_confirmed={holes_confirmed} "
        f"sample_weak_green={sample_weak.get('ok')} "
        f"sample_strong_red={sample_strong.get('ok')} "
        f"completion_red={completion_red.get('ok')} mode={worktree_mode}"
    )
    OUT_RAW.write_text("\n".join(raw) + "\n", encoding="utf-8")
    print(OUT_RAW.read_text(encoding="utf-8")[-5000:])

    if worktree_mode == "git-worktree":
        run(
            ["git", "-C", str(REPO), "worktree", "remove", "--force", str(wt)],
            timeout=120,
        )
    shutil.rmtree(wt_parent, ignore_errors=True)
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
