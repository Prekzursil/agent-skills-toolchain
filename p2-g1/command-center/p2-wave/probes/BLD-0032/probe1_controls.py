#!/usr/bin/env python3
"""BLD-0032 probe1: tag-inheritance controls over the control-packet fixture.

Rebuilt in the receipt's own grammar: `## ` headings (lines 5/9/13/17 are
cited by the receipt), square-bracket status tags, CLAIM-REGISTRY.json with
verification_status fields. Controls: a heading citing a tagged premise
without carrying the tag is FLAGGED-DROP (REC-DROP at :5, REC-TRANS at :13);
the qualified twin passes (REC-INHERIT at :9); an untagged VERIFIED cite is
CLEAN (REC-CLEAN); a section citing no premise is UNGROUNDED (REC-UNGROUNDED
at :17). The receipt's observation kinds + control ids must all re-appear.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _shard6lib import ProbeFailure, check_receipt_core, require  # noqa: E402

UID = "BLD-0032"
FIX = Path(__file__).resolve().parent / "fixtures" / "control-packet"
CLAIM_RE = re.compile(r"CLM-[A-Z0-9-]+")
TAG_RE = re.compile(r"\[(UNVERIFIED|NOT-CHECKED|VERIFIED)\]")


def build_packet() -> None:
    FIX.mkdir(parents=True, exist_ok=True)
    (FIX / "CLAIM-REGISTRY.json").write_text(json.dumps({"claims": [
        {"id": "CLM-DROP-1", "verification_status": "UNVERIFIED", "line": 14},
        {"id": "CLM-INHERIT-1", "verification_status": "UNVERIFIED", "line": 22},
        {"id": "CLM-B", "verification_status": "NOT-CHECKED", "line": 38},
        {"id": "CLM-C", "verification_status": "NOT-CHECKED", "line": 44},
        {"id": "CLM-CLEAN-1", "verification_status": "VERIFIED", "line": 50},
    ]}, indent=1), encoding="utf-8")
    lines = [
        "## Control packet (BLD-0032)",           # 1
        "",                                        # 2
        "Premise statuses: CLAIM-REGISTRY.json.",  # 3
        "",                                        # 4
        "## Ship the latency SLO as a hard gate",  # 5  (unqualified, tagged premise)
        "Recommendation: gate on the measured latency.",  # 6
        "Premise: CLM-DROP-1.",                    # 7
        "",                                        # 8
        "## Ship the fallback path [UNVERIFIED]",  # 9  (qualified twin)
        "Recommendation: keep the qualifier attached.",  # 10
        "Premise: CLM-INHERIT-1.",                 # 11
        "",                                        # 12
        "## Treat claim A as standing policy",     # 13 (two-hop drop)
        "Recommendation: adopt via the chain, CLM-B.",  # 14
        "",                                        # 15
        "Chain note: CLM-B derives from CLM-C.",   # 16
        "## Paint the bikeshed blue",              # 17 (ungrounded)
        "Recommendation: paint it.",               # 18
        "",                                        # 19
        "## Archive the old ledger [VERIFIED]",    # 20 (clean)
        "Recommendation: keep archived.",          # 21
        "Premise: CLM-CLEAN-1.",                   # 22
    ]
    (FIX / "decision-packet.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_registry() -> dict[str, str]:
    reg = json.loads((FIX / "CLAIM-REGISTRY.json").read_text(encoding="utf-8"))
    return {c["id"]: c["verification_status"] for c in reg["claims"]}


def audit() -> dict[str, str]:
    """Sections citing a tagged premise carry the tag or are FLAGGED-DROP."""
    statuses = parse_registry()
    lines = (FIX / "decision-packet.md").read_text(encoding="utf-8").splitlines()
    secs: list[tuple[str, list[str]]] = []
    cur: tuple[str, list[str]] | None = None
    for ln in lines:
        m = re.match(r"## (.+)", ln)
        if m:
            cur = (ln, [])
            secs.append(cur)
        elif cur is not None:
            cur[1].append(ln)
    out: dict[str, str] = {}
    for heading, body_lines in secs:
        body = "\n".join(body_lines)
        cited = set(CLAIM_RE.findall(body))
        tagged = {c for c in cited if statuses.get(c) != "VERIFIED"}
        if not cited:
            out[heading] = "UNGROUNDED"
        elif tagged and not TAG_RE.search(heading):
            out[heading] = "FLAGGED-DROP"
        else:
            out[heading] = "CLEAN"
    return out


def main() -> int:
    doc = check_receipt_core(UID)
    build_packet()
    v = audit()
    drop = next(k for k in v if k.startswith("## Ship the latency"))
    inherit = next(k for k in v if k.startswith("## Ship the fallback"))
    trans = next(k for k in v if k.startswith("## Treat claim A"))
    ungr = next(k for k in v if k.startswith("## Paint the bikeshed"))
    clean = next(k for k in v if k.startswith("## Archive the old"))
    require(v[drop] == "FLAGGED-DROP", f"unqualified drop -> {v[drop]}")
    require(v[inherit] == "CLEAN", f"qualified twin -> {v[inherit]}")
    require(v[trans] == "FLAGGED-DROP", f"two-hop drop -> {v[trans]}")
    require(v[ungr] == "UNGROUNDED", f"no-premise section -> {v[ungr]}")
    require(v[clean] == "CLEAN", f"verified cite -> {v[clean]}")

    obs = {o["name"] for o in doc["report"]["observations"]}
    require({"unqualified-drop", "inherited-not-flagged", "two-hop",
             "ungrounded"} <= obs, f"observation kinds changed: {sorted(obs)}")
    cids = set(doc["report"]["control_ids"])
    require({"REC-DROP", "REC-INHERIT", "REC-TRANS", "REC-UNGROUNDED",
             "REC-CLEAN"} <= cids, f"control ids changed: {sorted(cids)}")

    print(json.dumps({
        "probe": "probe1-controls", "unit_id": UID,
        "verdicts": {k[:40]: val for k, val in v.items()}, "pass": True,
    }, ensure_ascii=False))
    print(f"SUCCESS:{UID}-probe1 drops+ungrounded flagged; "
          f"qualified twins clean")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProbeFailure as exc:
        print(f"FAILED:{UID}-probe1 {exc}")
        raise SystemExit(1)
