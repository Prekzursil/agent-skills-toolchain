"""shard3-w4 resume 2026-10-26: refresh AUD-0072 receipt after corpus-drift re-emit.

Downgrades state SUCCESS -> BLOCKED (reviewer-absent): the prior independent closure
verified sha 05e5d23d... which no longer exists on disk; the closure does not still
verify live, and a builder may not self-close. Prior closure preserved verbatim in notes.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent
rp = REPO / "command-center/receipts/AUD-0072.json"
r = json.loads(rp.read_text(encoding="utf-8"))
art = json.loads(
    (REPO / "command-center/audit/AUD-0072-confidence-status-normalization.json").read_text(
        encoding="utf-8"
    )
)

rev = r.get("reviewer")
assert isinstance(rev, dict) and rev.get("verdict") == "PASS" and rev.get("independent") is True, (
    "expected a prior independent PASS closure to preserve"
)
prior_closure = json.dumps(rev, sort_keys=True)

new_sha = "adcf9aea9d5e2366a9f30ef81d4bf95c5876095338430db8d8acd29a2dee7871"
new_bytes = 266712

a0 = r["artifacts"][0]
assert a0["path"] == "command-center/audit/AUD-0072-confidence-status-normalization.json"
a0["sha256"] = new_sha
a0["bytes"] = new_bytes
a0["exists"] = True
a0["eol"] = "LF"

nps = {np["role"]: np for np in art.get("named_probes", [])}


def fp(uid, i, role, tail):
    return f"{uid}:probe{i}:{role}:{hashlib.md5(tail.encode('utf-8')).hexdigest()[:12]}"


for ev in r.get("evidence", []):
    for i, p in enumerate(ev.get("probes", []), 1):
        role = p.get("role")
        np = nps.get(role)
        if np is None:
            continue
        tail = str(np.get("raw_output") or "")[-4000:]
        p["raw_output"] = tail
        p["exit_code"] = np.get("exit_code", 0)
        p["fingerprint"] = fp("AUD-0072", i, role, tail)

tails = {role: str(np.get("raw_output") or "").strip().splitlines()[-1] for role, np in nps.items()}
for t in r.get("tests", []):
    tid = str(t.get("id", ""))
    if "probe1" in tid and "probe1" in tails:
        t["result"] = "PASS"
        t["output_tail"] = tails["probe1"]
    if "probe2" in tid and "probe2" in tails:
        t["result"] = "PASS"
        t["output_tail"] = tails["probe2"]

ru = r.get("residual_unknowns") or []
if ru:
    ru[0]["claim"] = (
        "Live-corpus drift, second instance: the census is a build-time snapshot. The "
        "2026-10-25T18:43Z snapshot broke probe2 on 2026-10-26 after sibling-wave receipt "
        "edits (IMP-0037.json verdict RECORDED removed at 19:29Z, after the reviewer closure "
        "at ~18:07Z): artifact residue carried a phrase the live corpus no longer contains. "
        "Remediated by the unit's own emit lane (re-emit from current corpus, both probes "
        "exit 0 live, new sha adcf9aea...). Receipt downgraded SUCCESS->BLOCKED(reviewer-absent) "
        "because the prior closure's sha anchor died with the old artifact; the closure text is "
        "preserved verbatim in notes. Corpus growth will break probe2 again on any receipt-file "
        "edit; re-emit is the designed refresh."
    )
    ru[0]["verdict"] = "NOT-CHECKED"
    ru[0]["settling_experiment"] = (
        "Re-run probe1/probe2 at a quiesced corpus; any future sibling receipt edit re-triggers re-emit."
    )

r["state"] = "BLOCKED"
r["failure"] = {
    "classification": ["reviewer-absent"],
    "reason": (
        "Builder-shard3-w4 resume 2026-10-26: artifact re-emitted (corpus drift: IMP-0037.json "
        "verdict edit removed the RECORDED residue row probe2 verified against; emit lane re-ran "
        "both probes live, exit 0). New artifact sha "
        "adcf9aea9d5e2366a9f30ef81d4bf95c5876095338430db8d8acd29a2dee7871 registered in "
        "UNIT-ARTIFACT-MANIFEST.json; _measure_one_delivered.py AUD-0072 exits SUCCESS:delivered. "
        "The prior independent closure (2026-10-26) verified the OLD sha 05e5d23d..., which no "
        "longer exists on disk, so per contract the closure does not still verify live and state "
        "must not stay SUCCESS. This builder cannot self-close; independent reviewer closure "
        "pending on the new artifact revision."
    ),
}
r["reviewer"] = None

disclosure = (
    "shard3-w4 resume 2026-10-26: probe2 artifact-residue-drift (art_only=[RECORDED from "
    "command-center/receipts/IMP-0037.json, edited by a sibling wave after the 2026-10-25 emit]). "
    "Fix cycle 1: re-emitted via probes/AUD-0072/emit_artifact.py (the unit's designed refresh "
    "lane); both named probes re-ran exit 0; manifest primary row re-registered; measure "
    "SUCCESS:delivered. Prior SUCCESS receipt downgraded to BLOCKED(reviewer-absent): the "
    "independent reviewer closure verified sha 05e5d23d..., invalidated by the re-emit. "
    "PRIOR INDEPENDENT CLOSURE PRESERVED VERBATIM (now stale, sha-dead): " + prior_closure
)
notes = str(r.get("notes") or "")
r["notes"] = (notes + " | " + disclosure) if notes else disclosure

r.setdefault("timestamps", {})["ended_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

rp.write_text(json.dumps(r, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
print("receipt updated: state=", r["state"], "failure=", r["failure"]["classification"], "reviewer=", r["reviewer"])
