#!/usr/bin/env python3
"""INDEPENDENT REVIEWER, wave-2 shard-13 — fresh second implementation.

Written by the shard-13 reviewer agent (not imported from any builder module).
For each of the 12 units, mechanically verify DELIVERED per the unit contract:
  A. receipt at catalog output_path: exists, non-empty, parses as JSON,
     not self-declared BLOCKED/FAILED/SEVERED/TIMEOUT, state == SUCCESS
  B. receipt_core rule: reviewer.verdict == PASS and reviewer.independent is True
  C. output_schema: profile + required-fields clause from the catalog string
  D. probes/<id>/UNIT-ARTIFACT-MANIFEST.json: parses; primary row
     (path == output_path) present=true AND sha256 == live recomputed
     sha256 over CRLF-normalized bytes AND bytes == live normalized length
  D2. every other manifest row: file present AND digest matches (integrity)
  E. live probes re-run HERE (python -B, cwd=repo): rc == 0, no FAILED marker,
     at least one probe per unit
Exit 0 only if ALL units hold ALL checks. Nothing in the repo is mutated
except the probes' own raw-output JSON side effects (their designed behavior).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
REPO = Path(r"C:/Users/Prekzursil/p2-g1")
UNITS = [
    "IMP-0229", "IMP-0261", "IMP-0264", "IMP-0269", "IMP-0270", "IMP-0271",
    "IMP-0272", "IMP-0273", "IMP-0274", "IMP-0275", "IMP-0279", "IMP-0303",
]
SELF_BAD_STATES = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
PROBE_TIMEOUT_S = 300


def digest(p: Path) -> tuple[str, int]:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def parse_profile(schema_str: str) -> tuple[bool, list[str]]:
    """Return (profiled, required_fields) parsed from the catalog clause."""
    m = re.search(r"profile=([\w.-]+)", schema_str or "")
    if not m:
        return False, []
    req: list[str] = []
    rm = re.search(r"required:\s*([^)]+)\)", schema_str or "")
    if rm:
        req = [t.strip() for t in rm.group(1).split(",") if t.strip()]
    return True, req


def check_required(receipt: dict, req: list[str]) -> list[str]:
    miss = []
    for field in req:
        is_list = field.endswith("[]")
        name = field[:-2] if is_list else field
        if name not in receipt:
            miss.append(f"{name}:absent")
            continue
        v = receipt[name]
        if v is None or v == "" or v == []:
            miss.append(f"{name}:empty")
            continue
        if is_list and not isinstance(v, list):
            miss.append(f"{name}:not-list")
        if name == "artifact_paths" and isinstance(v, list) and not v:
            miss.append(f"{name}:empty-list")
    return miss


failures: dict[str, list[str]] = {}
notes: dict[str, list[str]] = {}

for uid in UNITS:
    bad: list[str] = []
    info: list[str] = []

    # --- catalog entry
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    cu = next((u for u in cat["work_units"] if u.get("id") == uid), None)
    if cu is None:
        failures[uid] = ["catalog-entry-absent"]
        print(f"{uid} FAIL catalog-entry-absent")
        continue
    out_rel = str(cu.get("output_path") or "").replace("\\", "/")
    if not out_rel:
        failures[uid] = ["catalog-output-path-empty"]
        print(f"{uid} FAIL catalog-output-path-empty")
        continue

    # --- A. artifact presence / parse / self-state
    out = REPO / out_rel
    if not out.is_file() or out.stat().st_size == 0:
        failures[uid] = ["artifact-absent-or-empty"]
        print(f"{uid} FAIL artifact-absent-or-empty path={out_rel}")
        continue
    try:
        receipt = json.loads(out.read_text(encoding="utf-8"))
        if not isinstance(receipt, dict):
            raise ValueError("receipt is not a JSON object")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        failures[uid] = [f"unparseable:{exc.__class__.__name__}"]
        print(f"{uid} FAIL unparseable:{exc}")
        continue
    state = str(receipt.get("state") or "").upper()
    if state in SELF_BAD_STATES:
        bad.append(f"self-declared:{state}")
    if state != "SUCCESS":
        bad.append(f"state!=SUCCESS:{state!r}")

    # --- B. receipt_core closure rule
    rev = receipt.get("reviewer") if isinstance(receipt.get("reviewer"), dict) else {}
    if rev.get("verdict") != "PASS":
        bad.append(f"reviewer.verdict={rev.get('verdict')!r}")
    if rev.get("independent") is not True:
        bad.append("reviewer.independent!=true")

    # --- C. output_schema profile contract
    profiled, req = parse_profile(str(cu.get("output_schema") or ""))
    if profiled:
        miss = check_required(receipt, req)
        if miss:
            bad.append("schema-required-missing:" + ";".join(miss))
    else:
        info.append("no-profile-clause(receipt.core-only)")

    # --- D. manifest primary row vs live digest
    man_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    named_probe_rows: list[str] = []
    if not man_path.is_file():
        bad.append("manifest-absent")
    else:
        try:
            man = json.loads(man_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            bad.append(f"manifest-unparseable:{exc.__class__.__name__}")
            man = None
        if isinstance(man, dict):
            rows = man.get("artifacts") if isinstance(man.get("artifacts"), list) else []
            prim = [a for a in rows if isinstance(a, dict)
                    and str(a.get("path") or "").replace("\\", "/") == out_rel]
            if not prim:
                bad.append("manifest-primary-row-absent")
            else:
                live_sha, live_n = digest(out)
                p = prim[0]
                if p.get("present") is not True:
                    bad.append("manifest-primary-present!=true")
                if str(p.get("sha256") or "") != live_sha:
                    bad.append(f"manifest-primary-sha-mismatch man={str(p.get('sha256'))[:12]} live={live_sha[:12]}")
                if p.get("bytes") != live_n:
                    bad.append(f"manifest-primary-bytes-mismatch man={p.get('bytes')} live={live_n}")
            # --- D2. other rows (integrity of the whole manifest)
            for a in rows:
                if not isinstance(a, dict):
                    continue
                rel = str(a.get("path") or "").replace("\\", "/")
                if rel == out_rel:
                    continue
                if a.get("role") == "named-probe" and rel.endswith(".py"):
                    named_probe_rows.append(rel)
                fp = REPO / rel
                if not fp.is_file():
                    bad.append(f"manifest-row-file-absent:{rel}")
                    continue
                s2, n2 = digest(fp)
                if s2 != str(a.get("sha256") or "") or n2 != a.get("bytes"):
                    bad.append(f"manifest-row-digest-mismatch:{rel} man={str(a.get('sha256'))[:12]}/{a.get('bytes')} live={s2[:12]}/{n2}")

    # --- E. re-run live probes myself
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
    glob_probes = sorted(p.name for p in pdir.glob("probe[0-9]*.py")) if pdir.is_dir() else []
    to_run = sorted(set(glob_probes) | {Path(r).name for r in named_probe_rows})
    if not to_run:
        bad.append("no-live-probes-found")
    else:
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        for pname in to_run:
            cmd = [sys.executable, "-B", str(pdir / pname)]
            try:
                cp = subprocess.run(cmd, cwd=str(REPO), env=env,
                                    capture_output=True, text=True,
                                    timeout=PROBE_TIMEOUT_S, encoding="utf-8",
                                    errors="replace")
                rc, so, se = cp.returncode, cp.stdout or "", cp.stderr or ""
            except subprocess.TimeoutExpired:
                bad.append(f"probe-timeout:{pname}>{PROBE_TIMEOUT_S}s")
                continue
            marker_ok = ("SUCCESS:" in so) and ("FAILED:" not in so)
            if rc != 0 or not marker_ok:
                tail = (so.strip().splitlines() or [""])[-1][:200]
                etail = (se.strip().splitlines() or [""])[-1][:200]
                bad.append(f"probe-failed:{pname} rc={rc} out={tail!r} err={etail!r}")
            else:
                info.append(f"{pname}:rc0")
    if not profiled:
        pass

    if bad:
        failures[uid] = bad
        print(f"{uid} FAIL {'; '.join(bad)}")
    else:
        notes[uid] = info
        print(f"{uid} PASS ({len(info)} probe runs ok{'; ' + '; '.join(info[:2]) + '...' if len(info) > 2 else ''})")

print("---")
if failures:
    print(f"FAILED:shard13-w2-review {len(failures)}/{len(UNITS)} units failing")
    for u, why in failures.items():
        print(f"  {u}:")
        for w in why:
            print(f"    - {w}")
    sys.exit(1)
print(f"SUCCESS:shard13-w2-review all {len(UNITS)} units hold every independent check "
      f"(receipt+reviewer+schema+manifest-digest+live-probes)")
sys.exit(0)
