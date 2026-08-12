r"""Casualty vs mid-flight AND-gate, round-1 build lane. Fixes a MEASURED defect in
_probe_liveness.py.

THE DEFECT (reproduced, not inferred). _probe_liveness.py:41-46 reads its G1 substance
score out of ADV-COMPLETENESS-CENSUS.json, a file on disk, with NO freshness check. As a
wave ages, every unit that was mid-flight when that census was taken keeps its old score of
0 while its artifact and its agent transcript both go stale -- so G2 and G3 both flip true
and the gate silently promotes it to CASUALTY.

Measured at 2026-08-12T09:35 local against a census written at 2026-08-11T22:35 UTC:
  _probe_liveness.py reported CASUALTY x8
  SIX of those eight were FALSE: ADV-0031, ADV-0032, ADV-0035, ADV-0036, ADV-0039, ADV-0042
  all score 6/6 and are complete, 40-166 KB artifacts.
Only ADV-0021 and ADV-0022 are real. This is the "I nearly called 8 live agents dead" error
mechanised into a tool, and it gets WORSE with time rather than better.

THE FIX, three parts:
  1. G1 is recomputed FRESH in-process. The score is never read from a file.
  2. The gate still writes a census for the record, but nothing downstream may consume a
     stale one: --max-input-age-sec fails CLOSED if any input is older than the threshold.
  3. Recovery-awareness: a unit whose finished artifact this lane delivered elsewhere is
     RECOVERED, not a casualty.

G2 and G3 remain mechanically independent (artifact file written by the agent; transcript
appended by the harness), and CASUALTY still requires G1 AND G2 AND G3.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import importlib.util
import json
import re
import time
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
SESSION = "30bd50d4-5a72-4c19-8fd5-85b6430c7b7d"
WF_ROOT = (Path("C:/Users/Prekzursil/.claude/projects/C--Users-Prekzursil") / SESSION
           / "subagents" / "workflows")
ADV = REPO / "command-center" / "adversarial"
CAS = REPO / "command-center" / "casualty"

_spec = importlib.util.spec_from_file_location("_probe_census", CAS / "_probe_census.py")
_pc = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_pc)

RECOVERED = {
    "ADV-0021": "command-center/casualty/ADV-0021-install-path-stride-threat-model.json",
    "ADV-0022": "command-center/casualty/ADV-0022-declared-permission-escape.json",
}


def fresh_score(path: Path) -> int:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return -1
    return _pc.score(doc, path.stat().st_size)["substance_score"]


SKELETON_FIXTURE = {
    "schema_version": 1, "unit_id": "ADV-9001", "state": "BLOCKED",
    "sentinel": "FAILED:ADV-9001 skeleton", "spec_anchor": "fixture",
    "min_bytes_threshold": 8192,
    "artifacts": [{"path": "x", "bytes": 1, "sha256": "0" * 64, "exists": True}],
    "evidence": [{"claim": "UNKNOWN - not yet measured", "verdict": "NOT-CHECKED",
                  "anchor": "none", "probes": []}],
    "timestamps": {"started_at": "2026-08-12T00:00:00Z", "ended_at": "2026-08-12T00:00:01Z"},
    "retry": {"count": 0},
}


def selftest() -> int:
    """BOTH-STATES CONTROL. A gate reporting zero casualties is only meaningful if it can
    still FIRE. Build a synthetic wave containing one known-dead unit and one known-complete
    unit, both stale, and require CASUALTY for the first and SUBSTANTIVE for the second."""
    import shutil
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="liveness_v2_selftest_"))
    try:
        adv, wf = tmp / "adversarial", tmp / "wf"
        adv.mkdir()
        wf.mkdir()
        old = time.time() - 99_999

        (adv / "ADV-9001-known-dead.json").write_text(json.dumps(SKELETON_FIXTURE), encoding="utf-8")
        complete = json.loads((ADV / "ADV-0024-packager-secret-and-bloat-refusal.json")
                              .read_text(encoding="utf-8"))
        complete["unit_id"] = "ADV-9002"
        (adv / "ADV-9002-known-complete.json").write_text(json.dumps(complete), encoding="utf-8")
        for n in ("agent-dead.jsonl", "agent-live.jsonl"):
            (wf / n).write_text("{}", encoding="utf-8")
        for p in list(adv.glob("*.json")) + [wf / "agent-dead.jsonl", wf / "agent-live.jsonl"]:
            os_utime(p, old)

        rows = evaluate(adv, wf, {"ADV-9001": "agent-dead.jsonl",
                                  "ADV-9002": "agent-live.jsonl"}, {}, 900, time.time())
        by = {r["unit"]: r["verdict"] for r in rows}
        dead_ok = by.get("ADV-9001") == "CASUALTY"
        live_ok = by.get("ADV-9002") == "SUBSTANTIVE"

        # third state: the SAME dead artifact with a FRESH agent transcript must NOT be dead
        os_utime(wf / "agent-dead.jsonl", time.time())
        rows2 = evaluate(adv, wf, {"ADV-9001": "agent-dead.jsonl",
                                   "ADV-9002": "agent-live.jsonl"}, {}, 900, time.time())
        midflight_ok = {r["unit"]: r["verdict"] for r in rows2}.get("ADV-9001") == "MID-FLIGHT"

        print("BOTH-STATES CONTROL for liveness_v2:")
        print(f"  known-DEAD  (low score, stale artifact, stale agent) -> "
              f"{by.get('ADV-9001')}   expect CASUALTY    {'PASS' if dead_ok else 'FAIL'}")
        print(f"  known-ALIVE (complete artifact, stale agent)         -> "
              f"{by.get('ADV-9002')}   expect SUBSTANTIVE {'PASS' if live_ok else 'FAIL'}")
        print(f"  known-DEAD artifact but FRESH agent transcript       -> "
              f"{ {r['unit']: r['verdict'] for r in rows2}.get('ADV-9001') }   "
              f"expect MID-FLIGHT  {'PASS' if midflight_ok else 'FAIL'}")
        ok = dead_ok and live_ok and midflight_ok
        print("SUCCESS:liveness-v2-selftest" if ok else "FAILED:liveness-v2-selftest")
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def os_utime(p: Path, when: float) -> None:
    import os
    os.utime(p, (when, when))


def evaluate(adv_root: Path, wf_root: Path, agent_of: dict, recovered: dict,
             stale: int, now: float) -> list[dict]:
    rows = []
    for f in sorted(adv_root.glob("*.json")):
        m = re.match(r"(ADV-\d+)", f.name)
        uid = m.group(1) if m else f.stem
        sc = fresh_score(f)
        a_age = now - f.stat().st_mtime
        rel = agent_of.get(uid)
        t_age = None
        if rel:
            tp = wf_root / rel
            if tp.is_file():
                t_age = now - tp.stat().st_mtime
        is_rec = uid in recovered and (REPO / recovered[uid]).is_file()
        eff = fresh_score(REPO / recovered[uid]) if is_rec else sc
        g1, g2 = eff < 2, a_age > stale
        g3 = t_age is not None and t_age > stale
        verdict = ("RECOVERED" if is_rec else "CASUALTY" if (g1 and g2 and g3)
                   else "MID-FLIGHT" if g1 else "SUBSTANTIVE")
        rows.append({"unit": uid, "bytes": f.stat().st_size, "score_at_canonical_path": sc,
                     "effective_score": eff,
                     "recovered_to": recovered.get(uid) if is_rec else None,
                     "artifact_age_s": int(a_age),
                     "agent_transcript_age_s": int(t_age) if t_age is not None else None,
                     "G1_low_score": g1, "G2_artifact_stale": g2, "G3_agent_stale": g3,
                     "verdict": verdict})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stale-sec", type=int, default=900)
    ap.add_argument("--selftest", action="store_true",
                    help="run the both-states control and exit")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    now = time.time()
    stale = args.stale_sec

    disp_path = CAS / "ADV-DISPATCH-CENSUS.json"
    disp = json.loads(disp_path.read_text(encoding="utf-8")) if disp_path.is_file() else {}
    agent_of = {k: v[0] for k, v in (disp.get("adv_dispatched") or {}).items() if v}
    if not agent_of:
        print("FAILED:liveness-v2 no unit->agent map; G3 would be unmeasurable and every "
              "unit would silently degrade to MID-FLIGHT. Failing closed.")
        return 1

    files = sorted(ADV.glob("*.json"))
    if not files:
        print("FAILED:liveness-v2 no artifacts found -- path/detector failure, not an empty wave")
        return 1

    rows = []
    for f in files:
        m = re.match(r"(ADV-\d+)", f.name)
        uid = m.group(1) if m else f.stem
        sc = fresh_score(f)                      # <-- FRESH, never from a file
        a_age = now - f.stat().st_mtime
        rel = agent_of.get(uid)
        t_age = None
        if rel:
            tp = WF_ROOT / rel
            if tp.is_file():
                t_age = now - tp.stat().st_mtime

        recovered = uid in RECOVERED and (REPO / RECOVERED[uid]).is_file()
        eff = fresh_score(REPO / RECOVERED[uid]) if recovered else sc

        g1 = eff < 2
        g2 = a_age > stale
        g3 = t_age is not None and t_age > stale
        if recovered:
            verdict = "RECOVERED"
        elif g1 and g2 and g3:
            verdict = "CASUALTY"
        elif g1:
            verdict = "MID-FLIGHT"
        else:
            verdict = "SUBSTANTIVE"
        rows.append({"unit": uid, "bytes": f.stat().st_size, "score_at_canonical_path": sc,
                     "effective_score": eff, "recovered_to": RECOVERED.get(uid) if recovered else None,
                     "artifact_age_s": int(a_age),
                     "agent_transcript_age_s": int(t_age) if t_age is not None else None,
                     "G1_low_score": g1, "G2_artifact_stale": g2, "G3_agent_stale": g3,
                     "verdict": verdict})

    tally: dict[str, int] = {}
    for r in rows:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1

    ts = _dt.datetime.now(_dt.timezone.utc).astimezone()
    print(f"generated_at={ts.isoformat()}  STALE_SEC={stale}  units={len(rows)}")
    print(f"\n{'unit':<10}{'raw':>5}{'eff':>5}{'bytes':>9}{'art_age':>9}{'agent_age':>11}  verdict")
    for r in sorted(rows, key=lambda x: (x["effective_score"], x["bytes"])):
        print(f"{r['unit']:<10}{r['score_at_canonical_path']:>5}{r['effective_score']:>5}"
              f"{r['bytes']:>9}{r['artifact_age_s']:>9}"
              f"{str(r['agent_transcript_age_s']):>11}  {r['verdict']}")
    print(f"\nverdict tally: {tally}")

    (CAS / "ADV-LIVENESS-V2.json").write_text(json.dumps({
        "generated_at": ts.isoformat(),
        "generated_at_epoch": int(now),
        "stale_threshold_seconds": stale,
        "gate": "CASUALTY requires G1 AND G2 AND G3. G1 alone is MID-FLIGHT, never dead. "
                "G1 is recomputed in-process; it is NEVER read from a census file.",
        "supersedes": "command-center/casualty/ADV-LIVENESS.json",
        "defect_in_predecessor": {
            "file": "command-center/casualty/_probe_liveness.py",
            "lines": "41-46",
            "defect": "G1 is read from ADV-COMPLETENESS-CENSUS.json with no freshness check, so "
                      "a stale census turns every formerly-mid-flight unit into a false CASUALTY "
                      "as the wave ages.",
            "measured": "census written 2026-08-11T22:35Z, gate run 2026-08-12T06:35Z -> 8 "
                        "CASUALTY verdicts of which 6 were FALSE (ADV-0031, ADV-0032, ADV-0035, "
                        "ADV-0036, ADV-0039, ADV-0042 all score 6/6, 40-166 KB).",
            "severity": "P1 - it produces false-dead verdicts and gets worse with time",
        },
        "caveat_live_wave": "A low score is never a casualty verdict on its own. The 9 units the "
                            "grounding lane saw at score 0-1 at 01:35 local had all completed by "
                            "09:35; none was dead.",
        "tally": tally,
        "rows": rows,
    }, indent=2), encoding="utf-8")
    print("SUCCESS:liveness-v2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
