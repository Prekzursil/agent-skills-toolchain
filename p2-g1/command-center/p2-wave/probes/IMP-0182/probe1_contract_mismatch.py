"""IMP-0182 probe 1 (source, both-states): a contract-mismatch fixture is
refused BEFORE a fusion workflow exists (fusion is None; trace is
contract-check then refuse); the matching-neighbour twin is emitted; the
emit-first mutant still carries a fusion object on mismatch, keeping the
detector live.

Exit 0 iff all three states hold.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stage_splice as SS  # noqa: E402

RAW = HERE / "probe1-contract-mismatch.raw.txt"

host = SS.host_workflow()
bad = SS.splice(host, SS.donor_mismatch())
lines = [json.dumps({"fusion_is_none": bad["fusion"] is None,
                     "reason": bad["reason"], "status": bad["status"],
                     "trace": bad["trace"]})]
assert bad["status"] == "refused" and bad["reason"] == "contract-mismatch"
assert bad["fusion"] is None, "mismatch carried a fusion object"
assert bad["trace"] == ["contract-check", "refuse"], bad["trace"]

good = SS.splice(host, SS.donor_matching())
lines.append(json.dumps({"status": good["status"], "fusion_id": good["fusion_id"]}))
assert good["status"] == "emitted", "matching contract refused"
assert good["fusion_id"] == "wf.host.extract-v1++wf.donor.extract-v2::stage-splice"
assert good["trace"] == ["contract-check", "emit"], good["trace"]

mut = SS.splice_emit_first_mutant(host, SS.donor_mismatch())
lines.append(json.dumps({"mutant_fusion_present": mut["fusion"] is not None,
                         "trace": mut["trace"]}))
assert mut["fusion"] is not None, "emit-first mutant no longer carries the counterexample"
assert mut["trace"] == ["emit", "contract-check", "refuse"], mut["trace"]

RAW.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("RESULT:" + json.dumps({"mismatch_refused": True, "fusion_is_none": True,
                              "matching_emitted": True, "mutant_fusion_present": True}))
print("SUCCESS:IMP-0182-probe1 contract mismatch refused before fusion exists")
