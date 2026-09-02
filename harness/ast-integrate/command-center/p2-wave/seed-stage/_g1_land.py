#!/usr/bin/env python3
"""Land a writer report in one step (02.09 orchestrator tool).

Reads a writer's compact report (/tmp/writers/<name>.md), extracts (a) every repo-relative path it
claims to have changed or copied back and (b) every unit id it mentions with a verdict, then:
  1. refuses paths that are not under the tree, that carry a stub marker, or that contain `_NS`;
  2. syncs the orchestrator's verification mirror from the record for those paths (+ probes);
  3. measures every mentioned unit STRICT in that mirror with a small parallel wave
     (`w0902-land-<name>`), hermetic env (AST_INTEGRATE_ROOT pinned, `-s`);
  4. prints a per-unit table (writer's claim vs measured), the regression verdict, and the exact
     `git add` command for the paths (never `-A`), or a REFUSE line.

Usage: python3 _g1_land.py /tmp/writers/<name>.md [--mirror ~/p2-dev] [--workers 4] [--expect-ok ID,ID]
Read-only w.r.t. git: it prints the command, the orchestrator runs it.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _g1_paths import WIN  # noqa: E402

UID = re.compile(r"\b([A-Z]{2,5}-\d{4})\b")
PATH_RE = re.compile(r"(?<![\w/])((?:tools|platform|lib|council|marketplace|plugin|router|workflow_foundry|command-center|scripts|hooks|docs|workflows|schema|ci|release|\.github|\.claude-plugin|agent-self)/[\w./+\-]+\.(?:py|json|md|yaml|yml|txt|hook|sh|ps1|toml|cfg|ini|mjs|cjs|js|ts))")
MARKERS = ("# g1-surface: " + "generated", "# g1-mod: " + "real-surface")


def extract(report: str) -> tuple[list[str], dict[str, str]]:
    paths: list[str] = []
    for m in PATH_RE.finditer(report):
        p = m.group(1).rstrip(".,;:)")
        if p not in paths:
            paths.append(p)
    claims: dict[str, str] = {}
    for line in report.splitlines():
        m = re.match(r"^\W*([A-Z]{2,5}-\d{4})\b.*?after=\s*`?(OK|SUCCESS|FAIL(?:ED)?)", line)
        if m:
            claims[m.group(1)] = "OK" if m.group(2) in ("OK", "SUCCESS") else "FAIL"
    return paths, claims


def measure(mirror: Path, uid: str) -> str:
    env = {**os.environ, "AST_INTEGRATE_ROOT": str(mirror), "G1_PLACEHOLDER_MODE": "strict",
           "PYTHONPYCACHEPREFIX": os.environ.get("PYTHONPYCACHEPREFIX", "/dev/shm/g1-pyc")}
    env.pop("G1_MIRROR", None)
    try:
        p = subprocess.run([sys.executable, "-s", "command-center/p2-wave/_measure_one_delivered.py", uid],
                           cwd=str(mirror), capture_output=True, text=True, timeout=600, env=env)
        lines = [ln for ln in (p.stdout + p.stderr).splitlines() if ln.strip()]
        return lines[-1] if lines else f"exit={p.returncode}"
    except subprocess.TimeoutExpired:
        return "TIMEOUT"


def main() -> int:
    args = sys.argv[1:]
    report_path = Path(args[0])
    mirror = Path(os.path.expanduser(args[args.index("--mirror") + 1])) if "--mirror" in args else Path.home() / "p2-dev"
    workers = int(args[args.index("--workers") + 1]) if "--workers" in args else 4
    expect_ok = set(args[args.index("--expect-ok") + 1].split(",")) if "--expect-ok" in args else set()
    report = report_path.read_text(encoding="utf-8", errors="replace")
    paths, claims = extract(report)
    ok_paths, refused = [], []
    for rel in paths:
        f = WIN / rel
        if not f.exists():
            refused.append((rel, "missing in record (deleted? use git add -A on its dir)"))
            continue
        if f.suffix == ".py":
            head = f.read_text(encoding="utf-8", errors="replace")
            if any(m in head[:1500] for m in MARKERS):
                refused.append((rel, "stub marker present"))
                continue
            if "class _NS" in head or re.search(r"^def __getattr__", head, re.M):
                refused.append((rel, "_NS / module __getattr__ present"))
                continue
        ok_paths.append(rel)
    # sync record -> mirror for the paths + probe dirs of the units
    units = sorted(set(claims) | expect_ok)
    sync_paths = ok_paths + [f"command-center/p2-wave/probes/{u}" for u in units] + ["command-center/p2-wave/seed-stage", "command-center/p2-wave/_measure_one_delivered.py", "platform/schema", "platform/registry"]
    env = {**os.environ, "G1_MIRROR": str(mirror)}
    subprocess.run([sys.executable, str(Path(__file__).with_name("_g1_mirror_sync.py")), "--paths", *sync_paths],
                   check=False, env=env, stdout=subprocess.DEVNULL)
    # remove root twins in the mirror that the record no longer has (sync never deletes)
    for rel in paths:
        f = WIN / rel
        m = mirror / rel
        if not f.exists() and m.exists():
            m.unlink()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = dict(zip(units, pool.map(lambda u: measure(mirror, u), units)))
    print(f"LAND {report_path.name}: {len(ok_paths)} paths, {len(units)} units measured STRICT in {mirror}")
    bad = 0
    for u in units:
        meas = "OK" if results[u].startswith("SUCCESS:delivered") else "FAIL"
        claim = claims.get(u, "?")
        flag = "" if claim in ("?", meas) else "  <-- DISAGREES with writer"
        if claim == "?" and meas == "FAIL" and u in expect_ok:
            flag = "  <-- REGRESSION"
        if flag:
            bad += 1
        print(f"  {u} writer={claim:4s} measured={meas:4s} {results[u][:70]}{flag}")
    for rel, why in refused:
        print(f"  REFUSE {rel}: {why}")
    if bad:
        print("VERDICT: mismatches present - inspect before committing")
    else:
        print("VERDICT: consistent")
    if ok_paths:
        print("git -C /workspace add " + " ".join(f"harness/ast-integrate/{p}" for p in ok_paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
