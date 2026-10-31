#!/usr/bin/env python3
"""ADV-0127 re-anchor (shard1-w4 resume 2026-10-26): production census drifted
under the stale artifact -> re-emit against live, refresh sha in manifest /
SUBAGENT-RETURN / formal receipt. Builder state stays BLOCKED + reviewer-absent;
only the independent reviewer closes."""
from __future__ import annotations
import hashlib, json, os, tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(".").resolve()
ART = "command-center/adversarial/ADV-0127-clock-skew-timezone-dst-effects.json"
MAN = REPO / "command-center/p2-wave/probes/ADV-0127/UNIT-ARTIFACT-MANIFEST.json"
RET = REPO / "command-center/p2-wave/probes/ADV-0127/SUBAGENT-RETURN.json"
REC = REPO / "command-center/receipts/ADV-0127.json"
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

raw = (REPO / ART).read_bytes()
sha = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
size = len(raw.replace(b"\r\n", b"\n"))
assert sha == "37fb1e5f1f6fc5bcd2cc0f43781174eba28bd23cf9e55eff0db746087468595a", sha

def atomic_json(path: Path, doc) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)

# 1. manifest
man = json.loads(MAN.read_text(encoding="utf-8"))
hit = 0
for a in man.get("artifacts", []):
    if a.get("unit_id") == "ADV-0127" and str(a.get("path","")).replace("\\","/") == ART:
        a["sha256"], a["bytes"], a["present"] = sha, size, True
        hit += 1
assert hit == 1, f"manifest rows hit={hit}"
man.setdefault("extensions", {})["reanchor"] = {
    "date": NOW, "cause": "production-census drift (live platform tree changed under stale artifact)",
    "action": "re-emitted artifact against live census; sha refreshed in manifest/return/receipt",
}
atomic_json(MAN, man)

# 2. SUBAGENT-RETURN (builder receipt in probe dir)
ret = json.loads(RET.read_text(encoding="utf-8"))
for a in ret.get("artifacts", []):
    if str(a.get("path","")).replace("\\","/") == ART:
        a["sha256"], a["bytes"], a["present"] = sha, size, True
ret.setdefault("extensions", {})["reanchor_2026_10_26"] = (
    "shard1-w4 resume: artifact re-emitted against live production census "
    "(fingerprint drift live=0304bc2a... vs stale art); probes re-run green after re-emit")
atomic_json(RET, ret)

# 3. formal receipt - state stays BLOCKED, classification reviewer-absent
rec = json.loads(REC.read_text(encoding="utf-8"))
for a in rec.get("artifacts", []):
    if str(a.get("path","")).replace("\\","/") == ART:
        a["sha256"], a["bytes"], a["exists"] = sha, size, True
fail = rec.get("failure") or {}
fail["classification"] = ["reviewer-absent"]
fail["reason"] = (
    "Builder-side construction complete and live-verified after 2026-10-26 re-anchor "
    "(_measure_one_delivered.py -> SUCCESS:delivered): artifact re-emitted against the live "
    "production clock-class census (prior copy went stale when the platform tree drifted), "
    "parses against output_schema, carries the completion sentinel, both named probes re-run "
    "exit 0, per-unit manifest row matches the CRLF-normalized sha256. state stays BLOCKED "
    "because receipt_core forbids state=SUCCESS without reviewer.verdict=PASS with "
    "independent=true. Only the independent reviewer closes."
)
rec["failure"] = fail
ts = rec.get("timestamps") or {}
ts["reanchored_at"] = NOW
rec["timestamps"] = ts
atomic_json(REC, rec)
print(f"SUCCESS:adv0127-reanchor sha={sha} bytes={size}")
