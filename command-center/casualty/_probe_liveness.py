r"""Separate a CASUALTY from a MID-FLIGHT write-as-you-go skeleton. AND-gate, never mtime alone.

mtime alone cannot distinguish a stalled process from a long-finished one -- it supports exactly
one honest signal: "written in the last T seconds = currently active". So a low score is NOT a
casualty verdict. This requires ALL THREE, and prints each column separately so a disagreement
is visible:

  G1 substance_score < 2                     (the artifact has no populated substance arrays)
  G2 artifact not written in the last T sec  (nobody is currently updating it)
  G3 the DISPATCHING AGENT's transcript is also stale by the same T
                                             (the writer is gone, not merely between writes)

G3 is the one that matters: it is a different file, written by a different mechanism (the harness
appends the transcript; the agent writes the artifact), so G2 and G3 are mechanically independent.
A unit that is G1+G2 but NOT G3 is MID-FLIGHT and must not be called dead.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
SESSION = "30bd50d4-5a72-4c19-8fd5-85b6430c7b7d"
WF_ROOT = (
    Path("C:/Users/Prekzursil/.claude/projects/C--Users-Prekzursil")
    / SESSION
    / "subagents"
    / "workflows"
)
ADV = REPO / "command-center" / "adversarial"
OUT = REPO / "command-center" / "casualty"
STALE_SEC = 900  # 15 min with no write from EITHER the artifact or its agent


SUPERSEDED_BY = "command-center/casualty/liveness_v2.py"
SUPERSEDED_MSG = (
    "FAILED:liveness SUPERSEDED. This script has a P1 defect: it reads G1 (substance_score) out "
    "of ADV-COMPLETENESS-CENSUS.json with NO freshness check (see the read below), so a stale "
    "census turns mid-flight units into false CASUALTY verdicts as the wave ages -- measured "
    "8 CASUALTY of which 6 were FALSE. It ALSO overwrites command-center/casualty/"
    "ADV-LIVENESS.json, the very file that carries the _DO_NOT_CITE banner recording that "
    "defect, so an accidental re-run silently republishes the false verdicts.\n"
    f"  Use: python {SUPERSEDED_BY}\n"
    "  To run it anyway (for a both-states control), pass --i-know-this-is-superseded and an "
    "explicit --out DIR; it will never write the canonical path without both."
)


def main(argv: list[str]) -> int:
    # ROUND-2 D1 (confirmed by the adversarial audit of build round 1). Importing this module
    # for its score()/helpers stays free; only EXECUTION is refused, and only into the
    # canonical output path.
    global OUT
    argv = list(argv)
    forced = "--i-know-this-is-superseded" in argv
    out_override = None
    if "--out" in argv:
        i = argv.index("--out")
        if i + 1 < len(argv):
            out_override = Path(argv[i + 1])
    if not (forced and out_override):
        print(SUPERSEDED_MSG)
        return 2
    OUT = out_override
    OUT.mkdir(parents=True, exist_ok=True)

    now = time.time()
    census_path = OUT / "ADV-COMPLETENESS-CENSUS.json"
    if not census_path.is_file():
        print("FAILED:liveness run _probe_census.py first")
        return 1
    census = json.loads(census_path.read_text(encoding="utf-8"))
    scores = {r.get("file"): r.get("substance_score") for r in census["rows"]}

    disp_path = OUT / "ADV-DISPATCH-CENSUS.json"
    disp = json.loads(disp_path.read_text(encoding="utf-8")) if disp_path.is_file() else {}
    agent_of = {k: v[0] for k, v in (disp.get("adv_dispatched") or {}).items() if v}

    rows = []
    for f in sorted(ADV.glob("*.json")):
        m = re.match(r"(ADV-\d+)", f.name)
        uid = m.group(1) if m else f.stem
        a_age = now - f.stat().st_mtime
        rel = agent_of.get(uid)
        t_age = None
        if rel:
            tp = WF_ROOT / rel
            if tp.is_file():
                t_age = now - tp.stat().st_mtime
        g1 = (scores.get(f.name) if scores.get(f.name) is not None else 9) < 2
        g2 = a_age > STALE_SEC
        g3 = t_age is not None and t_age > STALE_SEC
        rows.append(
            {
                "unit": uid,
                "bytes": f.stat().st_size,
                "score": scores.get(f.name),
                "artifact_age_s": int(a_age),
                "agent_transcript_age_s": int(t_age) if t_age is not None else None,
                "G1_low_score": g1,
                "G2_artifact_stale": g2,
                "G3_agent_stale": g3,
                "verdict": (
                    "CASUALTY" if (g1 and g2 and g3)
                    else "MID-FLIGHT" if g1
                    else "SUBSTANTIVE"
                ),
            }
        )

    print(f"now={time.strftime('%Y-%m-%dT%H:%M:%S')} STALE_SEC={STALE_SEC}")
    print(f"\n{'unit':<10}{'score':>6}{'bytes':>9}{'art_age':>9}{'agent_age':>11}  verdict")
    for r in sorted(rows, key=lambda x: (x["score"] if x["score"] is not None else 9, x["bytes"])):
        print(
            f"{r['unit']:<10}{str(r['score']):>6}{r['bytes']:>9}{r['artifact_age_s']:>9}"
            f"{str(r['agent_transcript_age_s']):>11}  {r['verdict']}"
        )

    tally: dict[str, int] = {}
    for r in rows:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
    print(f"\nverdict tally: {tally}")

    (OUT / "ADV-LIVENESS.json").write_text(
        json.dumps(
            {
                "generated_at_local": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "stale_threshold_seconds": STALE_SEC,
                "gate": "CASUALTY requires G1 AND G2 AND G3; G1 alone is MID-FLIGHT, not dead",
                "tally": tally,
                "rows": rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("SUCCESS:liveness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
