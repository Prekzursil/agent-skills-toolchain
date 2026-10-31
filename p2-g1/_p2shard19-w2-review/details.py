import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
v = json.loads((REPO / "_p2shard19-w2-review" / "verify_out.json").read_text(encoding="utf-8"))

# 1) probe JSON shape: are checks real (non-empty, all true)?
for uid in ("RES-0151", "RES-0179", "RES-0182"):
    u = v[uid]
    print("===", uid)
    for p in u["probes"]:
        js = p.get("json") or {}
        checks = js.get("checks")
        if isinstance(checks, dict):
            n = len(checks)
            alltrue = all(x is True for x in checks.values())
            print("  ", p["script"], "exit=", p["exit"], "checks:", n, "all_true:", alltrue)
        elif isinstance(checks, list):
            print("  ", p["script"], "exit=", p["exit"], "checks(list):", len(checks),
                  "all_true:", all((c.get("pass") is True) for c in checks if isinstance(c, dict)))
        else:
            print("  ", p["script"], "exit=", p["exit"], "marker:", p.get("ok_marker"),
                  "pass:", js.get("pass"), "keys:", list(js.keys())[:8])

# 2) sha-mismatch detail for 0168/0182
print()
for uid in ("RES-0168", "RES-0182"):
    u = v[uid]
    mr = u["manifest_row"]
    ap = REPO / u["output_path"]
    mt = datetime.fromtimestamp(ap.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mmt = datetime.fromtimestamp(
        (REPO / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json")
        .stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(uid, "live_norm_sha=", u["artifact_norm_sha"][:16], "live_bytes=", u["artifact_bytes"],
          "manifest_sha=", str(mr.get("sha256"))[:16], "manifest_bytes=", mr.get("bytes"),
          "artifact_mtime=", mt, "manifest_mtime=", mmt)

# 3) per-unit failing-check inventory (the verdict lines)
print()
fails = {}
for uid, u in v.items():
    whys = []
    if u.get("self_decl_top"):
        whys.append("self-declared-not-delivering: " + "; ".join(
            f"{k}={val}" for k, val in u["self_decl_top"]))
    if not u.get("schema_ok"):
        whys.append(f"output_schema {len(u.get('schema_errors') or [])}+ validation errors")
    if not u.get("sha_ok_manifest"):
        whys.append("manifest sha256/bytes != live artifact (stale provenance registration)")
    if not u.get("sha_ok_receipt"):
        whys.append("receipt artifacts[] rows disagree with disk")
    if u.get("admission_errors"):
        whys.append(f"receipt admission incomplete ({len(u['admission_errors'])} schema gaps)")
    fails[uid] = whys
    print(uid, "->", " | ".join(whys) if whys else "NONE (would close)")

(REPO / "_p2shard19-w2-review" / "fail_inventory.json").write_text(
    json.dumps(fails, indent=1), encoding="utf-8")
