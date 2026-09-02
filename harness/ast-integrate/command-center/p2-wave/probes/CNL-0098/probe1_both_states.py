#!/usr/bin/env python3
"""Probe 1: detector-control first, then planted-bad FIRE, known-good SILENT.

Two mechanisms: in-memory fixture dicts AND the dumped JSON files. They
must agree. Empty graph is NOT-CHECKED. Diamond is not a cycle. False
positive rate is a number. Artifact must record the same statuses.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
import fixtures as F  # noqa: E402

ART = (
    REPO
    / "command-center/design/council"
    / "CNL-0098-weak-synthesis-and-circular-citation-in-the-argument-graph.md"
)
CONTROL_ORPHAN = "syn-KNOWN-ORPHAN"
CONTROL_CYCLE = {"KNOWN-A", "KNOWN-B", "KNOWN-C"}


def _cycle_covers(report: dict, needed: set[str]) -> bool:
    for row in report.get("cycles") or []:
        if needed <= {str(x) for x in (row.get("path") or [])}:
            return True
    return False


def _fail(msg: str) -> int:
    print(f"FAILED:CNL-0098-probe1 {msg}")
    return 1


def _load_json(fid: str) -> dict:
    path = HERE / "fixtures" / f"{fid}.json"
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    F.dump_json()
    mem = {fid: D.analyse(doc) for fid, doc in F.all_fixtures().items()}
    disk = {fid: D.analyse(_load_json(fid)) for fid in mem}

    for fid, a in mem.items():
        b = disk[fid]
        print(D.status_line(a))
        if a["status"] != b["status"]:
            return _fail(f"dict/json disagree on {fid}: {a['status']} vs {b['status']}")
        if a["unsupported_sentence_ids"] != b["unsupported_sentence_ids"]:
            return _fail(f"dict/json unsupported disagree on {fid}")
        if [c["path_str"] for c in a["cycles"]] != [c["path_str"] for c in b["cycles"]]:
            return _fail(f"dict/json cycle paths disagree on {fid}")

    ctrl = mem[F.CONTROL_ID]
    control_found = (
        ctrl["status"] == "FIRE"
        and CONTROL_ORPHAN in ctrl["unsupported_sentence_ids"]
        and _cycle_covers(ctrl, CONTROL_CYCLE)
    )
    print(f"detector_control_found_known_present={control_found}")
    if ctrl["status"] != "FIRE":
        return _fail("detector-control did not FIRE on known-present")
    if CONTROL_ORPHAN not in ctrl["unsupported_sentence_ids"]:
        return _fail("detector-control missed syn-KNOWN-ORPHAN")
    if not _cycle_covers(ctrl, CONTROL_CYCLE):
        return _fail("detector-control missed KNOWN-A/B/C cycle path")

    for fid in F.PLANTED_BAD_IDS:
        if mem[fid]["status"] != "FIRE":
            return _fail(f"planted-bad {fid} status={mem[fid]['status']}")
        print(f"planted_bad_fires[{fid}]=True")

    clean_fire = 0
    for fid in F.CLEAN_IDS:
        fired = mem[fid]["fired"]
        if fired:
            clean_fire += 1
        print(f"clean_silent[{fid}]={not fired} status={mem[fid]['status']}")
        if mem[fid]["status"] != "SILENT":
            return _fail(f"clean {fid} not SILENT")

    empty = mem[F.EMPTY_ID]
    print(f"empty_status={empty['status']} empty_fired={empty['fired']}")
    if empty["status"] != "NOT-CHECKED" or empty["fired"] is not False:
        return _fail("empty graph must be NOT-CHECKED, never a pass")
    if empty["circular_citation"]["status"] != "NOT-CHECKED":
        return _fail("empty cycle check must be NOT-CHECKED")

    diamond = mem["diamond"]
    if diamond["circular_citation"]["status"] != "SILENT":
        return _fail("diamond flagged as cycle")
    print("diamond_not_cycle=True")

    weak = mem["planted-weak"]
    if "syn-orphan" not in weak["unsupported_sentence_ids"]:
        return _fail("planted-weak missed syn-orphan")
    if weak["circular_citation"]["status"] != "SILENT":
        return _fail("planted-weak should be cycle-SILENT")

    ungrounded = mem["planted-circular-ungrounded"]
    if "syn-fake" not in ungrounded["unsupported_sentence_ids"]:
        return _fail("ungrounded cycle did not mark syn-fake unsupported")
    if not ungrounded["circular_citation"]["fired"]:
        return _fail("ungrounded cycle did not FIRE circular-citation")

    url_row = mem["url-launder-cycle"]
    print(
        f"url_launder_url_count={url_row['distinct_url_count']} "
        f"status={url_row['status']}"
    )
    if url_row["distinct_url_count"] < 3:
        return _fail("url-launder fixture must have >=3 distinct URLs")
    if url_row["status"] != "FIRE":
        return _fail("url-launder cycle hidden by URL cardinality")

    total = len(F.CLEAN_IDS)
    rate = clean_fire / total
    print(f"false_positive_rate={rate} fires={clean_fire} clean_fixtures_total={total}")
    if clean_fire != 0:
        return _fail(f"false-positive fires={clean_fire}")

    if not ART.is_file():
        return _fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:CNL-0098" not in text:
        return _fail("sentinel absent")
    bs = doc.get("both_states") or {}
    planted = bs.get("planted") or bs.get("planted_bad") or {}
    clean = bs.get("clean") or bs.get("known_good") or {}
    ctrl_art = bs.get("detector_control") or {}
    if planted.get("status") != "FIRE":
        return _fail("artifact planted not FIRE")
    if clean.get("status") != "SILENT":
        return _fail("artifact clean not SILENT")
    if ctrl_art.get("status") != "FIRE":
        return _fail("artifact detector_control not FIRE")
    dc = doc.get("detector_control") or {}
    if dc.get("known_present_run_first") is not True:
        return _fail("detector_control.known_present_run_first is not true")
    if dc.get("fired_before_absence_reported") is not True:
        return _fail("detector_control.fired_before_absence_reported is not true")
    fp = doc.get("false_positive_rate")
    if isinstance(fp, dict):
        rate_art = fp.get("rate")
    else:
        rate_art = fp
    if not isinstance(rate_art, (int, float)):
        return _fail("false_positive_rate is not a number")
    if float(rate_art) != float(rate):
        return _fail(f"artifact fp rate {rate_art} != live {rate}")
    print("SUCCESS:CNL-0098-probe1 both-states detector-control two-mechanism")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
