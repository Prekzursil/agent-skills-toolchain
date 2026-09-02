#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ids = [ln.strip() for ln in (HERE / "shard-11.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
rem = [ln.strip() for ln in (HERE / "shard-11.remaining.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
raw = (HERE / "shard-11.remaining.txt").read_bytes().replace(b"\r\n", b"\n")
fp = hashlib.sha256(raw).hexdigest()

delivered = []
for ln in (HERE / "_shard11_measure.jsonl").read_text(encoding="utf-8").splitlines():
    if not ln.strip():
        continue
    r = json.loads(ln)
    art = None
    for x in (r.get("tail") or "").splitlines():
        if x.startswith("artifact "):
            art = x
    delivered.append(
        {
            "id": r["id"],
            "rc": r.get("rc"),
            "last": r.get("last"),
            "ok": r.get("ok") is True and r.get("last") == f"SUCCESS:delivered {r['id']}",
            "artifact_line": art,
        }
    )

fails = {
    "ARC-0001": "FAILED:ARC-0001-probe1 baseline count 0 != 11",
    "ARC-0055": "FAILED:ARC-0055-probe2 fatigue session_count artifact=47 live=49",
    "ARC-0102": "FileNotFoundError: schema/common/identity.json ($ref)",
    "AUD-0002": "FAILED:AUD-0002-probe2 artifact did not record unpreserved_before_copy",
    "AUD-0050": "FAILED:AUD-0050-probe1 artifact orphan_list drifted from live selector model",
    "AUD-0091": "FAILED:AUD-0091-probe2 schema accepted garbage counts=[0, 0, 0]",
    "BLD-0035": "FAILED:BLD-0035-probe2 reviewer sampled_paths []",
    "BLD-0056": "FAILED:BLD-0056-probe1 receipt parse source mismatch",
    "CNF-0024": "FAILED:CNF-0024-probe2 image identifier missing ubuntu-latest",
    "CNF-0070": "FAILED:CNF-0070-probe2 schema accepted merged-verdict mutant",
    "CNL-0019": "FAILED:CNL-0019-probe2 dependency honesty CNL-0005 claimed=False live=True",
    "IMP-0175": "TypeError: inject_illegal_reason() takes 1 positional argument but 2 were given",
    "IMP-0213": "KeyError: 'paths'",
    "IMP-0314": "FAILED:IMP-0314-probe2 did not stat fixtures/anchors/fact-a.txt",
    "IMP-0339": "promoted-id mismatch (log truncated at IDEA-M08)",
    "IMP-0362": "FAILED:IMP-0362-probe2 URL assertion without WebFetch did not fire",
    "IMP-0391": "ImportError: CALIBRATION_TOLERANCE from tools/fusion/__init__.py (package shadows fusion.py)",
    "IMP-0426": "FAILED:IMP-0426-probe1 valid-must-pass-and-reach-consumer; schema-invalid-must-not-retry",
    "IMP-0459": "FAILED:IMP-0459-probe1 live matrix disagrees with receipt answer",
    "REL-0012": "FAILED:REL-0012-probe1 receipt untampered not recorded as pass",
    "RES-0044": "FAILED:RES-0044-probe1 T1-hop-trace not PASS in artifact",
    "RES-0111": "FAILED:RES-0111-probe2 reviewer not independent",
    "RES-0158": "AttributeError: tuple has no attribute get",
    "RES-0185": "FAILED:RES-0185-probe1 plant RES-0185-PLANT-SINGLE omitted from map",
    "SYN-0029": "FAILED:SYN-0029-probe1 empty rows",
    "TST-0020": "FAILED:TST-0020-probe2 receipt reviewer missing executed_both_states",
    "TST-0058": "AttributeError: Result has no attribute decision",
    "TST-0101": "AttributeError: list has no attribute get (evidence)",
    "TST-0140": "FAILED:TST-0140-probe2 batch_ceiling does not subtract interactive_reserved",
    "TST-0167": "FAILED:TST-0167-probe1 pre-suspend minority report is empty",
    "TST-0207": "FAILED:TST-0207-probe1 denylist mode was not refused",
    "TST-0265": "AttributeError: tst0265_unique_ideas has _jaccard not jaccard",
    "TST-0296": "StopIteration (missing cmp-h2h-sufficient)",
    "TST-0320": "TypeError: Cell.__init__ takes 2-3 args but 5 were given",
    "WFA-0030": "AttributeError: list has no attribute get (evidence)",
    "WFA-0083": "FAILED:WFA-0083-probe1 live AuditReport blob/worktree diverge before dirtying",
    "WFA-0132": "ImportError: planted_superior_ok from tools.foundry.tournament",
}

ok_ids = [r["id"] for r in delivered if r["ok"]]
payload = {
    "shard": 11,
    "attempted": len(ids),
    "ok": len(ok_ids),
    "fail": len(rem),
    "verified": len(ok_ids),
    "unmeasured": len(set(ids) - set(ok_ids) - set(rem)),
    "ok_ids": ok_ids,
    "delivered": delivered,
    "remaining": [{"id": u, "last_log": fails.get(u, "see _shard11_measure.log")} for u in rem],
    "remaining_fp": fp,
    "remaining_path": str(HERE / "shard-11.remaining.txt"),
    "result_path": str(HERE / "shard-11.txt.result.json"),
    "jsonl_path": str(HERE / "_shard11_measure.jsonl"),
    "log_path": str(HERE / "_shard11_measure.log"),
    "measure_cmd": "wsl.exe bash -lc 'export AST_INTEGRATE_ROOT=$HOME/p2-g1; cd $HOME/p2-g1; python3 command-center/p2-wave/_measure_one_delivered.py <ID>'",
    "pass1_ok": 7,
    "notes": [
        "G-1 SUCCESS is only jsonl last == SUCCESS:delivered <ID>. No invented SUCCESS.",
        "_keep_ok.py stripped fail rows from jsonl; fail reasons from _shard11_measure.log.",
        "jsonl ok last-lines are mechanically SUCCESS:delivered. remaining_fp matches result JSON.",
        "Windows python cannot run G-1. Rsync before remesure.",
    ],
    "next": [
        "IMP-0391: CALIBRATION_TOLERANCE on tools/fusion/__init__.py (package shadows fusion.py)",
        "WFA-0132: planted_superior_ok on tools/foundry/tournament.py",
        "IMP-0175: inject_illegal_reason two-arg",
        "TST-0320: Cell extra fields; TST-0265: jaccard=_jaccard",
        "ARC-0102: seed schema/common/identity.json into p2-g1 retrieve path",
        "Receipt units: patch artifact then per-unit UNIT-ARTIFACT-MANIFEST.json sha; never global unit_manifest.py --write",
    ],
}
dest = HERE / "shard-11.txt.handoff.json"
dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print("wrote", dest, "ok", payload["ok"], "fail", payload["fail"], "unmeasured", payload["unmeasured"])


if __name__ == "__main__":
    pass
