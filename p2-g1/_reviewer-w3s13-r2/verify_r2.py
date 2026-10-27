#!/usr/bin/env python3
"""Wave-3 shard-13 independent reviewer, round 2 (fresh context re-derivation).

Read-only battery over 12 units. Zero trust in prior runs: every check is
recomputed live. Checks per unit:
  A  artifact at catalog output_path exists / non-empty / parses as JSON /
     no self-declared BLOCKED or FAILED state anywhere in the parsed artifact
  C  catalog completion_sentinel appears verbatim in the receipt raw text
  D  UNIT-ARTIFACT-MANIFEST.json: every row's live file exists and its
     sha256 (CRLF normalized to LF) matches the manifest row; primary row
     (the receipt itself) explicitly confirmed
  E  catalog output_schema clause "(required: ...)" fields present & non-empty
  F  output_schema resolved fail-closed via platform/lib/schema_resolver
     .validate_artifact (the program's fail-closed instrument): 0 errors
  G  both per-unit probe scripts re-executed live from repo root:
     rc=0 AND 'SUCCESS:' in stdout AND 'FAILED:' not in stdout
B (closure claim) is recorded, not judged: builder probe-as-reviewer stamps
are the state the independent reviewer exists to replace.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "platform" / "lib"))
import schema_resolver as sr  # noqa: E402

IDS = [
    "IMP-0321", "IMP-0329", "IMP-0355", "IMP-0360", "IMP-0371", "IMP-0374",
    "IMP-0390", "IMP-0402", "IMP-0409", "IMP-0415", "IMP-0421", "IMP-0423",
]
REQUIRED_RE = re.compile(r"\(required:\s*([^)]+)\)")


def lf_sha256(p: Path):
    raw = Path(p).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def scan_selfblocked(obj, path="$"):
    bad = []
    if isinstance(obj, dict):
        st = obj.get("state")
        if isinstance(st, str) and st.strip().upper() in ("BLOCKED", "FAILED"):
            bad.append(path + ".state=" + str(st))
        f = obj.get("failure")
        if isinstance(f, dict):
            cl = f.get("classification")
            if isinstance(cl, list) and any(c == "reviewer-absent" for c in cl):
                bad.append(path + ".failure.classification=reviewer-absent")
        for k, v in obj.items():
            bad += scan_selfblocked(v, path + "." + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            bad += scan_selfblocked(v, path + "/" + str(i))
    return bad


def main() -> int:
    entries = json.loads((REPO / "_shard13-w3-entries.json").read_text(encoding="utf-8"))
    out = {"generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "results": {}}
    for uid in IDS:
        t0 = time.time()
        entry = entries[uid]
        fails, notes = [], []
        out_path = entry["output_path"]
        p = REPO / out_path
        receipt = None
        raw = b""
        man = None
        # ---- A
        if not p.is_file():
            fails.append("A: artifact MISSING at " + out_path)
        else:
            raw = p.read_bytes()
            if len(raw) == 0:
                fails.append("A: artifact EMPTY at " + out_path)
            else:
                try:
                    receipt = json.loads(raw)
                except Exception as exc:
                    fails.append("A: artifact does not parse as JSON: " + repr(exc)[:120])
                else:
                    sb = scan_selfblocked(receipt)
                    if sb:
                        fails.append("A: self-declared BLOCKED/FAILED: " + "; ".join(sb[:3]))
        # ---- C
        sent = entry.get("completion_sentinel") or ""
        if sent and sent not in raw.decode("utf-8", errors="replace"):
            fails.append("C: completion_sentinel not verbatim in receipt text: " + sent)
        # ---- D
        man_p = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        primary_ok = False
        nrows = 0
        if not man_p.is_file():
            fails.append("D: manifest missing: " + str(man_p))
        else:
            try:
                man = json.loads(man_p.read_text(encoding="utf-8"))
            except Exception as exc:
                fails.append("D: manifest does not parse: " + repr(exc)[:120])
            if isinstance(man, dict):
                rows = man.get("artifacts") or []
                nrows = len(rows)
                if not rows:
                    fails.append("D: manifest has zero artifact rows")
                for i, row in enumerate(rows):
                    rp = row.get("path") or ""
                    live = REPO / rp
                    if not live.is_file():
                        fails.append("D: row" + str(i) + " file missing: " + rp)
                        continue
                    sha, nb = lf_sha256(live)
                    if sha != row.get("sha256"):
                        fails.append(
                            "D: row" + str(i) + " sha256 mismatch (manifest="
                            + str(row.get("sha256"))[:16] + ".. live=" + sha[:16] + "..): " + rp
                        )
                    elif nb != row.get("bytes"):
                        notes.append("D: row" + str(i) + " bytes drift manifest="
                                     + str(row.get("bytes")) + " live=" + str(nb) + ": " + rp)
                    if rp.replace("\\", "/") == out_path:
                        primary_ok = (sha == row.get("sha256"))
                if not primary_ok and not any(f.startswith("D:") for f in fails):
                    fails.append("D: primary row (receipt) not found/matching in manifest")
        # ---- E
        m = REQUIRED_RE.search(entry.get("output_schema") or "")
        if m and receipt is not None:
            reqs = [r.strip() for r in m.group(1).split(",")]
            for req in reqs:
                name = req.rstrip("[]").strip()
                v = receipt.get(name)
                if v is None or (isinstance(v, (str, list, dict)) and len(v) == 0):
                    fails.append("E: required catalog clause field empty/missing: " + name)
        # ---- F
        if receipt is not None:
            errs = sr.validate_artifact(receipt, entry["output_schema"])
            if errs:
                fails.append("F: output_schema non-conformance (" + str(len(errs))
                             + " errors): " + " | ".join(errs[:4]))
            notes.append("schema-strict-errors=" + str(len(errs)))
        # ---- G
        probes_dir = REPO / "command-center" / "p2-wave" / "probes" / uid
        scripts = sorted(probes_dir.glob("probe*.py"))
        if not scripts:
            fails.append("G: no probe scripts found in " + str(probes_dir))
        env = {
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "PATH": os.environ.get("PATH", ""),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
        }
        for sc in scripts:
            t1 = time.time()
            rel = sc.relative_to(REPO).as_posix()
            try:
                cp = subprocess.run(
                    ["python3", "-B", rel],
                    cwd=str(REPO), capture_output=True, text=True,
                    timeout=240, env=env,
                )
                dt = time.time() - t1
                blob = (cp.stdout or "") + (cp.stderr or "")
                if cp.returncode != 0:
                    fails.append("G: " + sc.name + " rc=" + str(cp.returncode)
                                 + " (" + format(dt, ".1f") + "s): " + (cp.stderr or cp.stdout)[-200:])
                elif "FAILED:" in blob:
                    marker = [l for l in blob.splitlines() if "FAILED:" in l][0]
                    fails.append("G: " + sc.name + " rc=0 but FAILED: marker in output: " + marker[:160])
                elif "SUCCESS:" not in blob:
                    fails.append("G: " + sc.name + " rc=0 but no SUCCESS: marker")
                else:
                    notes.append("probe " + sc.name + ": rc=0 " + format(dt, ".1f") + "s SUCCESS-marker-ok")
            except subprocess.TimeoutExpired:
                fails.append("G: " + sc.name + " TIMEOUT >240s")
        # ---- B: record closure claim
        rv = (receipt or {}).get("reviewer") or {}
        out["results"][uid] = {
            "fails": fails,
            "notes": notes,
            "closable": not fails,
            "output_path": out_path,
            "claimed_reviewer_id": rv.get("reviewer_id"),
            "claimed_verdict": rv.get("verdict"),
            "claimed_independent": rv.get("independent"),
            "manifest_rows": nrows,
            "probes": [s.name for s in scripts],
            "seconds": round(time.time() - t0, 1),
        }
        print(uid, "FAIL" if fails else "ok", "(" + str(len(fails)) + " fails)", flush=True)
        for f in fails:
            print("   -", f[:230], flush=True)
    (Path(__file__).parent / "verify_r2_out.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("WROTE verify_r2_out.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
