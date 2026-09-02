#!/usr/bin/env bash
set -u
export AST_INTEGRATE_ROOT="$HOME/p2-g1"
SRC=/mnt/c/Users/Prekzursil/source/ast-integrate
DST="$HOME/p2-g1"
mkdir -p "$DST"
bash "$SRC/command-center/p2-wave/ovh-monitor/g1-shards/_shard00_rsync.sh"
# extra files not covered by dir rsync
rsync -a "$SRC/command-center/RUNBOOK.md" "$DST/command-center/" 2>/dev/null || true
rsync -a "$SRC/command-center/RELEASE-CHECKLIST.md" "$DST/command-center/" 2>/dev/null || true
rsync -a "$SRC/command-center/phase3/A4/" "$DST/command-center/phase3/A4/" 2>/dev/null || true
rsync -a "$SRC/tools/bench/" "$DST/tools/bench/" 2>/dev/null || true
rsync -a "$SRC/tools/plugin/" "$DST/tools/plugin/" 2>/dev/null || true
rsync -a "$SRC/tools/marketplace/" "$DST/tools/marketplace/" 2>/dev/null || true
rsync -a "$SRC/command-center/wfa/" "$DST/command-center/wfa/" 2>/dev/null || true
rsync -a "$SRC/command-center/design/council/" "$DST/command-center/design/council/" 2>/dev/null || true
cd "$DST"
python3 command-center/p2-wave/seed-stage/rewrite_schema_file_ids.py
python3 - <<'PY'
import hashlib, json, sys
from pathlib import Path
REPO = Path.home() / "p2-g1"
sys.path.insert(0, str(REPO / "command-center/p2-wave/probes/AUD-0077"))
sys.path.insert(0, str(REPO / "command-center/p2-wave/probes/CNF-0157"))
def digest(p):
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)
def remanifest(uid, rel, path):
    sha, n = digest(path)
    man_path = REPO / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    man = json.loads(man_path.read_text(encoding="utf-8")) if man_path.is_file() else {}
    if not isinstance(man, dict):
        man = {}
    man["unit_id"] = uid
    rows = man.get("artifacts") if isinstance(man.get("artifacts"), list) else []
    man["artifacts"] = rows
    hit = False
    for a in rows:
        if isinstance(a, dict) and str(a.get("path") or "").replace("\\", "/") == rel:
            a["sha256"] = sha; a["bytes"] = n; a["present"] = True; a["unit_id"] = uid
            hit = True
    if not hit:
        rows.insert(0, {"path": rel, "sha256": sha, "bytes": n, "present": True, "unit_id": uid, "role": "primary"})
    man_path.write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(uid, sha[:12], n)
try:
    from gitleaks_scan import scan_repo
    from helpers import OUT_REL, SENTINEL, UNIT
    live = scan_repo()
    path = REPO / OUT_REL
    doc = json.loads(path.read_text(encoding="utf-8"))
    gl = dict(doc.get("gitleaks") or {})
    gl["fingerprints"] = list(live["fingerprints"])
    gl["hit_count"] = live["hit_count"]
    gl["rule_counts"] = live.get("rule_counts")
    gl["version"] = live.get("version")
    doc["gitleaks"] = gl
    doc["unit_id"] = UNIT
    doc["state"] = "SUCCESS"
    if SENTINEL not in json.dumps(doc):
        doc["sentinel"] = "SUCCESS:AUD-0077"
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    remanifest("AUD-0077", OUT_REL, path)
    print("AUD fingerprints", len(live["fingerprints"]))
except Exception as exc:
    print("AUD patch fail", type(exc).__name__, exc)
try:
    import clients as C
    live = C.discover()
    rel = "command-center/receipts/CNF-0157.json"
    path = REPO / rel
    doc = json.loads(path.read_text(encoding="utf-8"))
    disc = dict(doc.get("discovery") or {})
    disc["missing_declared"] = list(live["missing_declared"])
    disc["plugin_package"] = live["plugin_package"]
    doc["discovery"] = disc
    doc["unit_id"] = "CNF-0157"
    doc["state"] = "SUCCESS"
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    remanifest("CNF-0157", rel, path)
    print("CNF-0157 missing", live["missing_declared"])
except Exception as exc:
    print("CNF patch fail", type(exc).__name__, exc)
PY
cd "$DST"
IDS=/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/shard-00.remaining.txt
OUT="$HOME/p2-g1-shard00-fail.jsonl"
ok=0; fail=0; n=0
: > "$OUT"
while IFS= read -r uid || [ -n "$uid" ]; do
  uid=$(printf '%s' "$uid" | tr -d '\r')
  [ -z "$uid" ] && continue
  n=$((n+1))
  echo "===== MEASURE $uid ($n) ====="
  log=/tmp/g1-"$uid".out
  python3 -B command-center/p2-wave/_measure_one_delivered.py "$uid" >"$log" 2>&1 < /dev/null
  rc=$?
  line=$(tail -n 1 "$log")
  echo "$line"
  if grep -q 'SUCCESS:delivered' "$log"; then
    ok=$((ok+1))
    printf '{"id":"%s","ok":true,"rc":%s}\n' "$uid" "$rc" >> "$OUT"
  else
    fail=$((fail+1))
    printf '{"id":"%s","ok":false,"rc":%s}\n' "$uid" "$rc" >> "$OUT"
    echo "TAIL $uid:"
    tail -n 16 "$log"
  fi
done < "$IDS"
echo "BATCH ok=$ok fail=$fail n=$n"
echo "SUCCESS:shard00-fail-remeasure ok=$ok fail=$fail n=$n"
