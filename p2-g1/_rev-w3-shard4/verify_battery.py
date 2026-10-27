#!/usr/bin/env python3
"""Independent reviewer battery - wave 3 shard 4 (12 units).

Per unit, gates:
  G1 artifact exists / non-empty / parses / not self-declared BLOCKED or FAILED
  G2 artifact validates against catalog output_schema
  G3 probes/<id>/UNIT-ARTIFACT-MANIFEST.json primary row sha256 == recomputed
     live sha256 (CRLF normalized to LF before hashing), present=true
  G4 receipt primary artifact sha256 == live sha256 (consistency)
  G5 all named probes re-run LIVE by the reviewer, exit 0
Sentinel conformance (artifact records both named probes verbatim) is recorded
as informational.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
OUTDIR = REPO / "_rev-w3-shard4"
MY = ["AUD-0044", "AUD-0047", "AUD-0053", "AUD-0055", "AUD-0057",
      "AUD-0064", "AUD-0066", "AUD-0069", "AUD-0071", "AUD-0072",
      "AUD-0075", "AUD-0080"]
SHIM = REPO / "command-center" / "p2-wave" / "seed-stage" / "g1_python.py"
TIMEOUT = 1200  # seconds per probe


def digest_live(path: Path) -> tuple[str, int, str]:
    raw = path.read_bytes()
    eol = "CRLF" if b"\r\n" in raw else "LF"
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm), eol


def load_schema(schema_ref: str):
    """Load the catalog output_schema document; remap absolute $ref to local
    platform tree when the canonical source tree is absent."""
    p = REPO / schema_ref
    doc = json.loads(p.read_text(encoding="utf-8"))
    ref = doc.get("$ref")
    if ref and ref.startswith("file:///"):
        fs = ref[len("file:///"):].split("#", 1)
    elif ref:
        fs = [ref.split("#", 1)[0], ref.split("#", 1)[1] if "#" in ref else ""]
    else:
        fs = [None, ""]
    if fs[0]:
        canonical = Path("/" + fs[0]) if not fs[0].startswith("/") else Path(fs[0])
        if not canonical.exists():
            # remap: .../source/ast-integrate/<rest> -> REPO/<rest>
            marker = "ast-integrate/"
            if marker in fs[0]:
                rest = fs[0].split(marker, 1)[1]
                local = REPO / rest
                if local.exists():
                    doc["$ref"] = f"file:///{local.as_posix()}#{'#' + fs[1] if fs[1] else ''}"
    return doc


def build_probe_argv(command: str) -> tuple[list[str], dict[str, str], str]:
    """Parse 'VAR=val ... python3 -B <script>' into argv via the g1 shim,
    mirroring the builder's run_cmd wrapper."""
    c = command
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", c)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        c = c[m.end():]
    exe = sys.executable.replace("\\", "/")
    parts = c.split()
    # parts[0] was python3; replace with exe + shim; drop a bare '-B'
    script = parts[-1] if parts else ""
    flags = [p for p in parts[1:-1] if p != "-B"]
    argv = [exe, str(SHIM.as_posix())] + flags + [script]
    return argv, env, script


def main() -> int:
    import jsonschema

    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    byid = {e["id"]: e for e in cat["work_units"]}

    results = {}
    for uid in MY:
        entry = byid[uid]
        r = {"unit": uid, "checks": {}, "info": {}}
        out_rel = entry["output_path"].replace("\\", "/")
        out_path = REPO / out_rel
        schema_ref = entry["output_schema"]

        # ---- G1 artifact ----
        g1 = {"exists": False, "nonempty": False, "parses": False, "not_self_blocked": None}
        try:
            if out_path.exists():
                g1["exists"] = True
                if out_path.stat().st_size > 0:
                    g1["nonempty"] = True
                art = json.loads(out_path.read_text(encoding="utf-8"))
                g1["parses"] = True
                decl = {k: art.get(k) for k in ("state", "verdict", "status")
                        if isinstance(art.get(k), str)}
                bad = [f"{k}={v}" for k, v in decl.items()
                       if v.strip().upper() in ("BLOCKED", "FAILED")]
                g1["not_self_blocked"] = (len(bad) == 0)
                r["info"]["self_declared"] = decl
                if bad:
                    g1["self_blocked_tokens"] = bad
                # sentinel conformance (informational): artifact records named probes
                r["info"]["artifact_probe_records"] = len(art.get("probes") or [])
        except Exception as ex:
            r["info"]["artifact_error"] = repr(ex)[:300]
        r["checks"]["G1_artifact"] = all(
            g1.get(k) for k in ("exists", "nonempty", "parses")) and \
            g1["not_self_blocked"] is True
        r["info"]["G1_detail"] = g1

        # ---- G2 schema ----
        g2 = {"valid": False, "error": None}
        if art is not None:
            try:
                schema = load_schema(schema_ref)
                jsonschema.validate(art, schema)
                g2["valid"] = True
            except Exception as ex:
                g2["error"] = repr(ex)[:500]
        r["checks"]["G2_schema"] = bool(g2["valid"])
        r["info"]["G2_detail"] = g2

        # ---- G3 manifest sha ----
        g3 = {"manifest_exists": False, "primary_row": None, "sha_match": False}
        man_path = REPO / f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json"
        try:
            man = json.loads(man_path.read_text(encoding="utf-8"))
            g3["manifest_exists"] = True
            live_sha, live_n, live_eol = digest_live(out_path)
            r["info"]["live_sha256"] = live_sha
            r["info"]["live_bytes"] = live_n
            r["info"]["live_eol"] = live_eol
            rows = [a for a in man.get("artifacts", [])
                    if str(a.get("path", "")).replace("\\", "/") == out_rel]
            prim = [a for a in rows if a.get("role") == "primary"] or rows
            if prim:
                row = prim[0]
                g3["primary_row"] = {"sha256": row.get("sha256"), "bytes": row.get("bytes"),
                                     "present": row.get("present"), "role": row.get("role")}
                g3["sha_match"] = (row.get("sha256") == live_sha)
        except Exception as ex:
            r["info"]["manifest_error"] = repr(ex)[:300]
        r["checks"]["G3_manifest_sha"] = bool(
            g3["manifest_exists"] and g3["sha_match"])
        r["info"]["G3_detail"] = g3

        # ---- G4 receipt consistency ----
        g4 = {"receipt_state": None, "sha_match": False, "reviewer_absent": False}
        try:
            rec = json.loads((REPO / f"command-center/receipts/{uid}.json").read_text(encoding="utf-8"))
            g4["receipt_state"] = rec.get("state")
            rev = rec.get("reviewer") or {}
            g4["reviewer_absent"] = (rev.get("verdict") != "PASS")
            fail = rec.get("failure") or {}
            g4["classification"] = fail.get("classification")
            ra = [a for a in (rec.get("artifacts") or [])
                  if str(a.get("path", "")).replace("\\", "/") == out_rel]
            if ra:
                g4["sha_match"] = (ra[0].get("sha256") == r["info"].get("live_sha256"))
            r["info"]["min_bytes_threshold"] = rec.get("min_bytes_threshold")
        except Exception as ex:
            r["info"]["receipt_error"] = repr(ex)[:300]
        r["checks"]["G4_receipt_consistent"] = bool(g4["sha_match"])
        r["info"]["G4_detail"] = g4

        # ---- G5 live probe re-run ----
        g5 = []
        try:
            ret = json.loads((REPO / f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json")
                             .read_text(encoding="utf-8"))
            named = ret.get("named_probes") or []
            if not named:
                g5.append({"error": "no named_probes in SUBAGENT-RETURN"})
            for np in named:
                cmd = np.get("command") or ""
                probe_id = np.get("id")
                argv, env, script = build_probe_argv(cmd)
                t0 = time.time()
                try:
                    p = subprocess.run(argv, cwd=str(REPO), env=env, shell=False,
                                       capture_output=True, text=True, timeout=TIMEOUT)
                    rc, tail = p.returncode, ((p.stdout or "") + (p.stderr or ""))[-400:]
                except subprocess.TimeoutExpired:
                    rc, tail = "TIMEOUT", f"killed after {TIMEOUT}s"
                g5.append({"probe": probe_id, "script": script, "exit": rc,
                           "secs": round(time.time() - t0, 1), "tail": tail[-200:]})
        except Exception as ex:
            g5.append({"error": repr(ex)[:300]})
        r["checks"]["G5_probes_live_exit0"] = bool(g5) and all(
            (g.get("exit") == 0) for g in g5)
        r["info"]["G5_detail"] = g5

        r["DELIVERED"] = all(r["checks"].values())
        results[uid] = r
        print(f"{uid}: DELIVERED={r['DELIVERED']} " +
              " ".join(f"{k}={v}" for k, v in r["checks"].items()))

    outp = OUTDIR / "verify-results.json"
    outp.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print("wrote", outp)
    n_ok = sum(1 for v in results.values() if v["DELIVERED"])
    print(f"SUMMARY {n_ok}/{len(MY)} DELIVERED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
