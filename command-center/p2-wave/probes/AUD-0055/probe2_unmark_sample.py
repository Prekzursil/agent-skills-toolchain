#!/usr/bin/env python3
"""AUD-0055 Probe 2: stratified unmark sample in a scratch worktree.

Catalog evidence_requirement Probe 2:
  for a stratified sample, REMOVE the marker in a scratch worktree and run the
  test — the only way to know whether the stated reason still holds is to try it.

Control (tests_required):
  an xfail whose underlying bug is fixed must show as XPASS when marked, and
  PASS when unmarked; assert the sample is executed rather than reasoned about.
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
OUT_JSON = PROBE / "probe2-unmark-sample.json"
OUT_RAW = PROBE / "probe2-unmark-sample.raw.txt"

CONTROL_XFAIL = (
    "command-center/p2-wave/probes/AUD-0055/fixtures/test_control_xfail_fixed.py"
)
CONTROL_SKIP = (
    "command-center/p2-wave/probes/AUD-0055/fixtures/test_control_skip_still_fails.py"
)


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


def load_probe1() -> dict:
    p = PROBE / "probe1-marker-census.json"
    return json.loads(p.read_text(encoding="utf-8"))


def stratified_sample(markers: list[dict], limit_per_stratum: int = 2) -> list[dict]:
    """Pick production markers across skip / skipif / xfail strata + always controls."""
    strata = {"skip": [], "skipif": [], "xfail": [], "other": []}
    for m in markers:
        if not m.get("production_scope"):
            continue
        # Prefer markers that decorate a test_* target so pytest can run them
        target = str(m.get("target") or "")
        if not (target.startswith("test_") or target == "pytestmark"):
            # assignment aliases like requires_sa still usable if we can find tests
            if m.get("form") != "decorator":
                continue
        k = m["kind"]
        if k in strata:
            strata[k].append(m)
        elif k in {"skipIf", "skipUnless"}:
            strata["skipif"].append(m)
        elif k == "expectedFailure":
            strata["xfail"].append(m)
        else:
            strata["other"].append(m)

    sample: list[dict] = []
    seen: set[tuple[str, int]] = set()
    for key in ("xfail", "skip", "skipif"):
        for m in strata[key][:limit_per_stratum]:
            sig = (m["path"], m["lineno"])
            if sig in seen:
                continue
            seen.add(sig)
            sample.append(m)
    return sample


def strip_marker_line(text: str, lineno: int, kind: str) -> tuple[str, bool]:
    """Remove a decorator / assignment marker line (1-indexed). Returns (new, changed)."""
    lines = text.splitlines(keepends=True)
    if lineno < 1 or lineno > len(lines):
        return text, False
    idx = lineno - 1
    original = lines[idx]
    # Multi-line decorator: remove from @... through closing paren if balanced on following lines
    if "@" in original or "pytest.mark" in original or "unittest." in original:
        block = original
        j = idx
        # If this line starts a call that isn't closed, consume until balanced
        open_p = block.count("(") - block.count(")")
        while open_p > 0 and j + 1 < len(lines):
            j += 1
            block += lines[j]
            open_p = block.count("(") - block.count(")")
        # Delete idx..j
        del lines[idx : j + 1]
        # If we removed a decorator, ensure no orphan blank issues
        return "".join(lines), True
    return text, False


def pytest_summary(output: str) -> dict:
    """Parse pytest -q progress + duration line for outcomes."""
    summary = {
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "xfailed": 0,
        "xpassed": 0,
        "error": 0,
        "raw_summary": "",
    }
    # Quiet mode: "1 xpassed in 0.03s" / "1 failed, 33 deselected in 0.04s"
    # Banner mode: "===== 1 passed in 0.1s ====="
    candidates: list[str] = []
    for line in output.splitlines():
        s = line.strip()
        if re.search(
            r"\d+\s+(passed|failed|skipped|xfailed|xpassed|error)",
            s,
            re.IGNORECASE,
        ):
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
            ("xfailed", r"(\d+)\s+xfailed"),
            ("xpassed", r"(\d+)\s+xpassed"),
            ("error", r"(\d+)\s+errors?"),
        ):
            mm = re.search(pat, line, re.IGNORECASE)
            if mm:
                summary[key] = int(mm.group(1))
    executed = (
        summary["passed"]
        + summary["failed"]
        + summary["xfailed"]
        + summary["xpassed"]
        + summary["error"]
    )
    summary["executed"] = executed
    summary["collected_nonzero"] = executed + summary["skipped"] > 0
    return summary


def run_pytest(
    paths: list[str], cwd: Path, nodeid_filter: str | None = None
) -> tuple[int, str, dict]:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--tb=no",
        *paths,
    ]
    if nodeid_filter:
        cmd.extend(["-k", nodeid_filter])
    rc, out = run(cmd, cwd=cwd, timeout=300)
    return rc, out, pytest_summary(out)


def reason_holds_verdict(kind: str, summary: dict, rc: int) -> str:
    """After unmarking: does the stated reason still appear to hold?"""
    if kind in {"xfail", "expectedFailure"}:
        # If unmarked and PASSes, reason was stale (bug fixed).
        if summary["passed"] > 0 and summary["failed"] == 0:
            return "STALE-reason-bug-appears-fixed"
        if summary["failed"] > 0:
            return "HOLDS-still-fails"
        return "INCONCLUSIVE"
    # skip / skipif
    if summary["failed"] > 0:
        return "HOLDS-unmarked-fails"
    if summary["passed"] > 0:
        return "STALE-unmarked-passes"
    if summary["skipped"] > 0:
        return "INCONCLUSIVE-still-skipped"
    return "INCONCLUSIVE"


def main() -> int:
    p1 = load_probe1()
    markers = p1["markers"]
    sample = stratified_sample(markers)
    raw: list[str] = ["unit=AUD-0055 probe=2 unmark-in-scratch-worktree"]

    # --- Control: marked run must XPASS ---
    ctrl_path = REPO / CONTROL_XFAIL
    rc_m, out_m, sum_m = run_pytest([str(ctrl_path)], REPO)
    raw.append("--- control marked xfail (expect XPASS) ---")
    raw.append(f"rc={rc_m}")
    raw.append(out_m[-1500:])
    control_xpass = sum_m["xpassed"] >= 1
    raw.append(f"control_marked_xpassed={control_xpass} summary={sum_m}")

    # --- Scratch worktree ---
    wt_parent = Path(tempfile.mkdtemp(prefix="aud0055-wt-"))
    wt = wt_parent / "tree"
    # Prefer worktree; fall back to archive checkout if worktree fails
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
        worktree_mode = "fixture-copy-fallback"
    else:
        worktree_mode = "git-worktree"

    # Uncommitted fixtures are absent from a detached HEAD worktree — sync them in.
    src_fix = PROBE / "fixtures"
    dest_fix = wt / "command-center/p2-wave/probes/AUD-0055/fixtures"
    dest_fix.mkdir(parents=True, exist_ok=True)
    for f in src_fix.glob("*.py"):
        shutil.copy2(f, dest_fix / f.name)
    raw.append(f"synced_fixtures_into_scratch={dest_fix}")

    results: list[dict] = []

    def unmark_and_run(row: dict, label: str) -> dict:
        rel_path = row["path"]
        target_file = wt / rel_path
        if not target_file.is_file():
            # For production samples in fallback mode, may be missing
            return {
                "label": label,
                "path": rel_path,
                "lineno": row["lineno"],
                "kind": row["kind"],
                "reason": row.get("reason"),
                "ok": False,
                "error": "file-missing-in-scratch",
                "executed": False,
            }
        text = target_file.read_text(encoding="utf-8")
        new_text, changed = strip_marker_line(text, row["lineno"], row["kind"])
        if not changed:
            # Try regex remove of decorator containing kind
            lines = text.splitlines(keepends=True)
            idx = row["lineno"] - 1
            if 0 <= idx < len(lines):
                # nuke line and continuation
                j = idx
                open_p = lines[idx].count("(") - lines[idx].count(")")
                while open_p > 0 and j + 1 < len(lines):
                    j += 1
                    open_p += lines[j].count("(") - lines[j].count(")")
                del lines[idx : j + 1]
                new_text = "".join(lines)
                changed = True
        if not changed:
            return {
                "label": label,
                "path": rel_path,
                "ok": False,
                "error": "marker-not-removed",
                "executed": False,
            }
        target_file.write_text(new_text, encoding="utf-8")
        node = row.get("target")
        kfilter = node if isinstance(node, str) and node.startswith("test_") else None
        rc, out, summary = run_pytest([str(target_file)], wt, nodeid_filter=kfilter)
        verdict = reason_holds_verdict(row["kind"], summary, rc)
        raw.append(
            f"--- {label} unmarked {rel_path}:{row['lineno']} ({row['kind']}) ---"
        )
        raw.append(f"changed={changed} rc={rc} verdict={verdict} summary={summary}")
        raw.append(out[-1200:])
        return {
            "label": label,
            "path": rel_path,
            "lineno": row["lineno"],
            "kind": row["kind"],
            "reason": row.get("reason"),
            "reason_class": row.get("reason_class"),
            "marker_removed": changed,
            "pytest_rc": rc,
            "summary": summary,
            "verdict": verdict,
            "executed": bool(
                summary.get("executed", 0) > 0 or summary.get("failed", 0) > 0
            ),
            "output_tail": out[-2000:],
            "ok": True,
        }

    # Control unmark: xfail fixed → must PASS (and must have been XPASS when marked)
    xfail_ctrl_row = {
        "path": CONTROL_XFAIL,
        "lineno": 0,
        "kind": "xfail",
        "reason": "AUD-0055-CONTROL: historic off-by-one in 1+1; still broken",
        "reason_class": "control-planted",
        "target": "test_aud0055_control_xfail_fixed",
    }
    # Find actual lineno from probe1
    for m in markers:
        if m["path"] == CONTROL_XFAIL and m["kind"] == "xfail":
            xfail_ctrl_row = m
            break

    ctrl_unmark = unmark_and_run(xfail_ctrl_row, "control-xfail-fixed")
    control_unmark_pass = (
        ctrl_unmark.get("summary", {}).get("passed", 0) >= 1
        and ctrl_unmark.get("summary", {}).get("failed", 0) == 0
        and ctrl_unmark.get("executed") is True
    )

    # Control skip: unmark → must FAIL
    skip_ctrl_row = {
        "path": CONTROL_SKIP,
        "lineno": 0,
        "kind": "skip",
        "reason": "AUD-0055-CONTROL: deliberately broken assertion; skip still required",
        "target": "test_aud0055_control_skip_still_fails",
    }
    for m in markers:
        if m["path"] == CONTROL_SKIP and m["kind"] == "skip":
            skip_ctrl_row = m
            break
    skip_unmark = unmark_and_run(skip_ctrl_row, "control-skip-still-fails")
    control_skip_fails = skip_unmark.get("summary", {}).get("failed", 0) >= 1

    results.append(ctrl_unmark)
    results.append(skip_unmark)

    # Stratified production sample (best-effort; may be INCONCLUSIVE if deps missing)
    for i, row in enumerate(sample):
        results.append(unmark_and_run(row, f"sample-{i}-{row['kind']}"))

    sample_executed = sum(1 for r in results if r.get("executed"))
    control_ok = control_xpass and control_unmark_pass and control_skip_fails

    doc = {
        "unit": "AUD-0055",
        "probe": 2,
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "worktree_mode": worktree_mode,
        "worktree_path": str(wt),
        "control": {
            "ok": control_ok,
            "marked_xpass": control_xpass,
            "unmarked_xfail_passes": control_unmark_pass,
            "unmarked_skip_fails": control_skip_fails,
            "marked_summary": sum_m,
            "note": (
                "Control xfail (bug fixed) shows XPASS while marked; after marker "
                "removal in scratch worktree the same test PASSes. Control skip "
                "FAILs when unmarked — sample executed, not reasoned about."
            ),
        },
        "sample_size": len(sample),
        "results_count": len(results),
        "sample_executed_count": sample_executed,
        "results": results,
        "ok": control_ok and sample_executed >= 2,
    }

    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    raw.insert(
        0,
        "SUCCESS:AUD-0055-probe2" if doc["ok"] else "FAILED:AUD-0055-probe2",
    )
    raw.append(
        f"control_ok={control_ok} marked_xpass={control_xpass} "
        f"unmark_pass={control_unmark_pass} skip_fails={control_skip_fails} "
        f"sample_executed={sample_executed}/{len(results)} mode={worktree_mode}"
    )
    OUT_RAW.write_text("\n".join(raw) + "\n", encoding="utf-8")
    print(OUT_RAW.read_text(encoding="utf-8")[-4000:])

    # Cleanup worktree
    if worktree_mode == "git-worktree":
        run(
            ["git", "-C", str(REPO), "worktree", "remove", "--force", str(wt)],
            timeout=120,
        )
    try:
        shutil.rmtree(wt_parent, ignore_errors=True)
    except OSError:
        pass

    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
