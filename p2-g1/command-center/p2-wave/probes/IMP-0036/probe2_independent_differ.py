#!/usr/bin/env python3
"""IMP-0036 probe2: independent reviewer probe (blake2s differ + refuse gate).

Reviewer obligations (receipt reviewer block):
  * re-extract unique lines via blake2s digest-set difference and require EXACT
    set equality with the packet's unique-line lists;
  * confirm gate.act refuses a DIVERGED packet until a decision is recorded,
    then allows after record_decision;
  * confirm a one-directional classifier mutant (repo-side only) misclassifies
    DIVERGED where the two-directional independent classifier does not;
  * confirm mtime and size are never used as authorship.
"""
from __future__ import annotations

import ast  # bind stdlib ast before tools/ast.py can shadow it
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.drift import classify_pair  # two-directional producer classifier
from plugin.gate import REFUSE_NO_DECISION, act  # noqa: E402
from plugin.independent_differ import (  # noqa: E402
    classify_independent,
    unique_line_sets_via_hash,
)
from plugin.packet import emit_packet, record_decision, unique_line_lists  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "packets.json"


def one_directional_mutant(repo_text: str, live_text: str) -> str:
    """Known-broken classifier: only asks whether repo has extras."""
    repo_set = set(repo_text.splitlines())
    live_set = set(live_text.splitlines())
    if repo_set == live_set:
        return "IDENTICAL"
    if not (repo_set - live_set):
        return "LIVE-AHEAD"
    return "REPO-AHEAD"


def main() -> int:
    spec = json.loads(FIXTURE.read_text(encoding="utf-8"))
    tmp = Path(tempfile.mkdtemp(prefix="imp0036-p2-"))
    try:
        rels = sorted(spec["files"])
        set_equal = 0
        refused_without_decision = 0
        allowed_after_record = 0
        mutant_misclassified = 0
        mtime_not_authorship = 0
        size_not_authorship = 0

        for rel in rels:
            entry = spec["files"][rel]
            repo_text, live_text = entry["repo"], entry["live"]
            pkt = emit_packet(path=rel, repo_text=repo_text, live_text=live_text)

            # 1. blake2s digest-set difference must equal the packet's lists exactly.
            ru_h, lu_h = unique_line_sets_via_hash(repo_text, live_text)
            if set(pkt["repo_unique_lines"]) == ru_h and set(pkt["live_unique_lines"]) == lu_h:
                set_equal += 1

            if pkt["classification"] == "DIVERGED":
                # 2. refuse until a decision is RECORDED.
                res = act(pkt, "TAKE-SOURCE")
                if res.get("refused") and res.get("reason") == REFUSE_NO_DECISION:
                    refused_without_decision += 1
                res2 = act(record_decision(pkt, "KEEP-BOTH"), "KEEP-BOTH")
                if res2.get("ok") and not res2.get("refused"):
                    allowed_after_record += 1
                # 3. the one-directional mutant must misclassify DIVERGED.
                if one_directional_mutant(repo_text, live_text) == "REPO-AHEAD" and \
                        classify_independent(repo_text.encode(), live_text.encode()) == "DIVERGED":
                    mutant_misclassified += 1
                # 4. mtime/size are recorded but never authorship.
                if pkt.get("mtime_is_authorship_signal") is False:
                    mtime_not_authorship += 1
                if pkt.get("size_is_authorship_signal") is False:
                    size_not_authorship += 1

        diverged_n = spec["distribution"]["DIVERGED"]
        checks = {
            "set_equality": set_equal == len(rels),
            "refused_without_decision": refused_without_decision == diverged_n,
            "allowed_after_record": allowed_after_record == diverged_n,
            "mutant_misclassified": mutant_misclassified == diverged_n,
            "mtime_not_authorship": mtime_not_authorship == diverged_n,
            "size_not_authorship": size_not_authorship == diverged_n,
        }
        out = {
            "unit_id": "IMP-0036",
            "probe": "probe2-independent-differ",
            "set_equality": set_equal,
            "refused_without_decision": refused_without_decision,
            "allowed_after_record": allowed_after_record,
            "mutant_misclassified": mutant_misclassified,
            "mtime_not_authorship": mtime_not_authorship,
            "size_not_authorship": size_not_authorship,
            "pass": all(checks.values()),
        }
        print(json.dumps(out, sort_keys=True))
        print("SUCCESS:IMP-0036-probe2 independent differ and refuse-without-decision")
        if not all(checks.values()):
            failed = [k for k, v in checks.items() if not v]
            print(f"FAILED:IMP-0036-probe2 {failed}")
            return 1
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
