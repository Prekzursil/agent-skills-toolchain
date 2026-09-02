#!/usr/bin/env python3
"""Probe 2: resume case measured, stage order vs documented LangGraph order."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import experiment  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0049-adapter-langgraph.json"


def main() -> int:
    urgent = experiment.run_case("urgent")
    normal = experiment.run_case("normal")
    print(f"urgent_ok={urgent['ok']} order={urgent.get('estate_full')}")
    print(f"normal_ok={normal['ok']} order={normal.get('estate_full')}")
    if not urgent["ok"] or not normal["ok"]:
        print("FAILED:WFA-0049-probe2 live resume/order")
        return 1
    if urgent["estate_full"] != ["ingest", "route", "escalate", "human_review", "finalize"]:
        print(f"FAILED:WFA-0049-probe2 unexpected urgent order {urgent['estate_full']}")
        return 1
    if normal["estate_full"] != ["ingest", "route", "draft", "human_review", "finalize"]:
        print(f"FAILED:WFA-0049-probe2 unexpected normal order {normal['estate_full']}")
        return 1
    if urgent["estate_first"] != ["ingest", "route", "escalate"]:
        print("FAILED:WFA-0049-probe2 first invoke did not pause before human_review")
        return 1
    if urgent["estate_resume"] != ["human_review", "finalize"]:
        print("FAILED:WFA-0049-probe2 resume did not continue from human_review")
        return 1
    if not urgent["wrong_thread_restarts"]:
        print("FAILED:WFA-0049-probe2 wrong thread_id did not restart (both-states)")
        return 1
    if not urgent["checkpoint_present"]:
        print("FAILED:WFA-0049-probe2 checkpoint missing")
        return 1

    if not ART.is_file():
        print("FAILED:WFA-0049-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    exe = doc.get("control_plane_execution") or {}
    art_u = (exe.get("urgent") or {}).get("estate_order")
    art_n = (exe.get("normal") or {}).get("estate_order")
    if art_u != urgent["estate_full"] or art_n != normal["estate_full"]:
        print("FAILED:WFA-0049-probe2 artifact order drift vs live")
        return 1
    if (doc.get("resume_case") or {}).get("tested") is not True:
        print("FAILED:WFA-0049-probe2 resume not recorded as tested")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:WFA-0049-probe2 self-declared {doc.get('state')}")
        return 1
    print("SUCCESS:WFA-0049-probe2 resume and documented-order")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
