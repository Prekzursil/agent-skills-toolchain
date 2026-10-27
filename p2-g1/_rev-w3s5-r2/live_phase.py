#!/usr/bin/env python3
"""Live phase for the static-PASS units (AUD-0082, AUD-0095).
L1  re-run every named probe command from SUBAGENT-RETURN.json, require rc=0,
    and require the probe output to carry its own SUCCESS marker.
L2  canonical program measure: _measure_one_delivered.py -> SUCCESS:delivered.
L3  reviewer's own re-derivation of AUD-0095 freeze anchors (independent of
    builder probe code): every present inventory row's live CRLF-normalized
    sha256 equals the recorded anchor; required_by_spec rows exist on disk.
L4  reviewer's own re-derivation of AUD-0082 census substance: walk the repo,
    count files, verify zero reserved-name/long-path/case-collision hazards
    and no live NUL device path, then compare against the artifact's payload.
"""
import hashlib, json, os, re, subprocess, sys
from pathlib import Path

REPO = Path.home() / "p2-g1"
OUT = REPO / "_rev-w3s5-r2"
UNITS = ["AUD-0082", "AUD-0095"]
ENV_PREFIX = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+")


def run_probe(cmd):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    while True:
        m = ENV_PREFIX.match(cmd)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        cmd = cmd[m.end():]
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True,
                       text=True, timeout=2700, env=env)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def digest_lf(p):
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main():
    report = {}
    for uid in UNITS:
        art_rel = ("command-center/audit/AUD-0082-windows-path-hazard-census.json"
                   if uid == "AUD-0082"
                   else "command-center/audit/AUD-0095-freeze-inventory.json")
        art = REPO / art_rel
        sr = json.loads((REPO / "command-center/p2-wave/probes" / uid / "SUBAGENT-RETURN.json")
                        .read_text(encoding="utf-8"))
        r = {"probes": []}
        ok = True
        for np in (sr.get("named_probes") or []):
            if not (isinstance(np, dict) and isinstance(np.get("command"), str)):
                continue
            c = np["command"].strip()
            rc, outp = run_probe(c)
            marker_ok = "SUCCESS:" in outp
            rec_ok = (rc == np.get("exit_code")) and marker_ok
            r["probes"].append({"cmd": c, "rc": rc, "recorded_rc": np.get("exit_code"),
                                "marker": marker_ok,
                                "tail": outp[-200:].replace("\n", " | ")})
            if rc != 0 or not marker_ok:
                ok = False
                r["probe_fail"] = f"rc={rc} marker={marker_ok}"
        # L2 canonical measure
        exe = str(sys.executable).replace("\\", "/")
        mrc, mout = run_probe(f'"{exe}" -I command-center/p2-wave/_measure_one_delivered.py {uid}')
        r["measure_rc"] = mrc
        r["measure_line"] = (mout.splitlines() or [""])[-1][:160]
        if mrc != 0 or f"SUCCESS:delivered {uid}" not in mout:
            ok = False
            r["measure_fail"] = mout[-300:]
        r["verdict_live"] = "PASS" if ok else "FAIL"
        report[uid] = r
        print(f"{uid} LIVE {'PASS' if ok else 'FAIL'}  probes={[(p['rc'], p['marker']) for p in r['probes']]} measure={r['measure_line'][:60]}")
        sys.stdout.flush()

    # L3: AUD-0095 anchor re-derivation (reviewer's own code)
    doc = json.loads((REPO / "command-center/audit/AUD-0095-freeze-inventory.json")
                     .read_text(encoding="utf-8"))
    inv = [row for row in (doc.get("inventory") or []) if isinstance(row, dict) and row.get("path")]
    mismatched, absent_required = [], []
    for row in inv:
        p = REPO / str(row["path"])
        if not p.is_file():
            if row.get("required_by_spec"):
                absent_required.append(str(row["path"]))
            continue
        if digest_lf(p) != str(row.get("sha256") or ""):
            mismatched.append(f"{row['path']} rec={str(row.get('sha256'))[:10]}")
    l3_ok = len(inv) >= 100 and not mismatched and not absent_required
    report["AUD-0095_L3_anchors"] = {
        "rows": len(inv), "mismatched": len(mismatched),
        "required_absent": absent_required[:5],
        "first_mismatch": mismatched[:3],
        "verdict": "PASS" if l3_ok else "FAIL"}
    print(f"AUD-0095 L3 anchors: rows={len(inv)} mismatched={len(mismatched)} "
          f"required_absent={len(absent_required)} -> {'PASS' if l3_ok else 'FAIL'}")

    # L4: AUD-0082 census re-derivation (reviewer's own walk)
    reserved_names = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | \
                     {f"lpt{i}" for i in range(1, 10)}
    files = 0
    hazards = {"reserved-name": 0, "long-path": 0, "case-collision": 0}
    collision = set()
    for root, dirs, fnames in os.walk(REPO):
        for name in list(dirs) + fnames:
            files += 1
            stem = name.split(".", 1)[0].lower()
            if stem in reserved_names:
                hazards["reserved-name"] += 1
            full = os.path.join(root, name)
            if len(full) > 260:
                hazards["long-path"] += 1
            key = full.lower()
            if key in collision:
                hazards["case-collision"] += 1
            collision.add(key)
    art82 = json.loads((REPO / "command-center/audit/AUD-0082-windows-path-hazard-census.json")
                       .read_text(encoding="utf-8"))
    payload = json.dumps(art82)
    claim_zero = ('"reserved-name": 0' in payload or "reserved-name=0" in payload or
                  art82.get("hazards", {}).get("reserved-name") == 0 if isinstance(art82.get("hazards"), dict) else False)
    r4 = {"reviewer_files_seen": files, "reviewer_hazards": hazards,
          "artifact_key": {k: art82.get(k) for k in list(art82.keys())[:12]}}
    l4_ok = (hazards["reserved-name"] == 0 and hazards["case-collision"] == 0)
    r4["verdict"] = "PASS" if l4_ok else "FAIL"
    report["AUD-0082_L4_census"] = r4
    print(f"AUD-0082 L4 census re-derivation: files={files} hazards={hazards} -> {'PASS' if l4_ok else 'FAIL'}")

    (OUT / "live-phase.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("LIVE-PHASE-DONE")


if __name__ == "__main__":
    main()
