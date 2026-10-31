#!/usr/bin/env python3
"""Builder shard 1 wave 1: write per-unit receipts (state=BLOCKED, reviewer-absent)."""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/p2-g1")
OUTDIR = REPO / "command-center" / "receipts"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

GREEN = [
    "ADV-0132","ARC-0001","ARC-0013","ARC-0019","ARC-0020","ARC-0047",
    "ARC-0048","ARC-0054","ARC-0068","AUD-0003","AUD-0010",
]
STALE = "ARC-0055"

def digest(path: Path):
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)

def eol_form(raw: bytes) -> str:
    if b"\x00" in raw:
        return "BINARY"
    crlf, lf = raw.count(b"\r\n"), raw.count(b"\n")
    if crlf == 0: return "LF"
    return "CRLF" if crlf == lf else "MIXED"

def main() -> int:
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = {u["id"]: u for u in cat["work_units"]}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    written = []
    for uid in GREEN + [STALE]:
        u = units[uid]
        out_rel = u["output_path"].replace("\\", "/")
        out = REPO / out_rel
        sha, size = digest(out)
        raw = out.read_bytes()
        ret_path = REPO / "command-center/p2-wave/probes" / uid / "SUBAGENT-RETURN.json"
        ret = json.loads(ret_path.read_text(encoding="utf-8")) if ret_path.is_file() else None
        probes = []
        if ret:
            for np in ret.get("named_probes") or []:
                probes.append({"id": np.get("id"), "command": np.get("command"), "exit_code": np.get("exit_code")})
        rr = u.get("reviewer_requirement") or ""
        common = {
            "schema_version": 1,
            "unit_id": uid,
            "id": uid,
            "state": "BLOCKED",
            "status": "BUILT-AWAITING-REVIEW",
            "completion_sentinel": (u.get("completion_sentinel") or "").split(" emitted")[0],
            "output_path": out_rel,
            "output_schema": u.get("output_schema"),
            "spec_anchor": u.get("spec_anchor"),
            "manifest_path": f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json",
            "owner_approval_required": u.get("owner_approval_required"),
            "gate_note": "not owner-gated (catalog owner_approval_required=false); blanket build directive 2026-10-24 not needed for this unit",
            "artifacts": [{
                "path": out_rel, "bytes": size, "sha256": sha, "exists": True,
                "eol": eol_form(raw), "role": "primary",
            }],
            "named_probes": probes,
            "produced_by": {"vendor": "anthropic", "model": "opus", "role": "builder-shard-1-w1"},
            "timestamps": {"started_at": "2026-10-24T19:28:00Z", "ended_at": now},
            "retry": {"count": 0, "policy": "two-strikes pivot; skip is a verdict, not a retry"},
            "reviewer": {
                "reviewer_id": None, "verdict": "PENDING", "independent": False,
                "catalog_reviewer_requirement": rr,
            },
            "ts": now,
        }
        if uid in GREEN:
            prior_note = ""
            if ret:
                rev = ret.get("reviewer") or {}
                if rev.get("verdict") == "PASS" and rev.get("independent") is True:
                    prior_note = (
                        "PRIOR-ATTEMPT FLAG: the inherited SUBAGENT-RETURN.json carries "
                        "reviewer.verdict=PASS independent=true naming reviewer_id "
                        f"'{rev.get('reviewer_id')}' - a probe-suite script run by the builder, "
                        "not the catalog-required independent reviewer. It does NOT satisfy "
                        "reviewer_requirement and is recorded here as a builder-side probe "
                        "verdict only; it does not close the unit. "
                    )
            common["failure"] = {
                "classification": ["reviewer-absent"],
                "reason": (
                    "Builder-side construction complete and live-verified "
                    "(_measure_one_delivered.py -> SUCCESS:delivered): artifact at "
                    "output_path parses, carries the completion sentinel, both named "
                    "probes re-run exit 0, per-unit manifest row matches the "
                    "CRLF-normalized sha256. state stays BLOCKED because receipt_core "
                    "forbids state=SUCCESS without reviewer.verdict=PASS with "
                    "independent=true, and the catalog reviewer_requirement names a "
                    "fresh-context / cross-vendor / two-reviewer panel that has not run. "
                    "Only the independent reviewer closes. " + prior_note + rr
                ),
                "blocked_on": "independent reviewer per catalog reviewer_requirement",
            }
        else:
            common["status"] = "BUILD-INCOMPLETE-FATIGUE-SUBSTRATE-LOST"
            common["failure"] = {
                "classification": ["reviewer-absent", "fatigue-census-substrate-lost"],
                "reason": (
                    "probe2_fatigue_overclaim.py exits 1: 'fatigue session_count "
                    "artifact=47 live=0'. The artifact's approval-fatigue block was "
                    "measured on the original wave-0 substrate "
                    "(/root/.cursor/projects/opt-p2-ast-integrate/agent-transcripts, 47 "
                    "real sessions); that substrate does not exist on this host and the "
                    "session-census.json fixture holding its rows was overwritten by a "
                    "later snapshot() run with an MSYS-mangled path (source_dir "
                    "'\\root\\.cursor\\...', source_exists=false, rows=[]) - evidence "
                    "loss, not re-measurement. No git history exists to recover it (the "
                    ".git in this tree is an empty placeholder). Real local replacement "
                    "corpora were measured and REJECTED as non-equivalent: "
                    "c-Users-Prekzursil-agents (13 sessions, 3702 tool_use) carries 47 "
                    "AskQuestion owner prompts and c-Users-Prekzursil (481 sessions, "
                    "33974 tool_use) carries 123, while probe2 asserts "
                    "summary.owner_prompts == 0; probe assertions were NOT modified to "
                    "fit available data (rigged-instrument class). Blast-radius "
                    "classification (probe1) passes live on the current artifact; the "
                    "fatigue re-derivation lane is the sole blocker. Precise unblock: "
                    "recover the 47-row census from the original substrate, or author a "
                    "substrate-retarget (seed-stage/_g1_env_retarget.py class) that the "
                    "catalog owner approves as a claim-scope change, then re-run probes. "
                    "Reviewer also absent per catalog reviewer_requirement. " + rr
                ),
                "blocked_on": "fatigue census substrate unrecoverable on this host; then independent reviewer",
            }
        (OUTDIR / f"{uid}.json").write_text(
            json.dumps(common, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        written.append(uid)
    print(f"SUCCESS:shard1-receipts wrote {len(written)}: {', '.join(written)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
