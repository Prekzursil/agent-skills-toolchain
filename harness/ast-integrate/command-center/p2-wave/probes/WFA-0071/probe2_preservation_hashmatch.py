#!/usr/bin/env python3
"""Probe 2 / Signal B: retrieve+hash-match preservation receipts.

Independent of probe 1: does not use existence_check as preservation proof.
A listed export path is a claim; only a successful retrieval that hash-matches
is a receipt. Does not import engine.retrieve_preservation — hashes files
itself and then compares engine verdicts.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import controls as C  # noqa: E402
import engine as E  # noqa: E402
import locate as L  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0071-retire-readjudication.json"


def sha_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def independent_match(candidate: dict) -> dict:
    claim = candidate.get("preservation_claim") or {}
    kind = str(claim.get("kind") or "none")
    claimed = str(claim.get("sha256") or "").lower()
    rel = str(claim.get("path") or "")
    path = (REPO / rel) if rel and not Path(rel).is_absolute() else Path(rel) if rel else None
    retrieved = sha_file(path) if path is not None else None
    matched = bool(retrieved and claimed and retrieved == claimed)
    return {
        "id": candidate["id"],
        "kind": kind,
        "claimed": claimed or None,
        "retrieved": retrieved,
        "matched": matched,
        "path_exists": bool(path and path.is_file()),
    }


def main() -> int:
    C.ensure_fixtures()
    controls = C.control_corpus()
    live = C.live_cohort()
    located = L.locate_registry()

    indep = [independent_match(c) for c in controls]
    engine_rows = [E.adjudicate(c) for c in controls]
    live_rows = [E.adjudicate(c) for c in live]
    by_id = {r["id"]: r for r in engine_rows}
    indep_by = {r["id"]: r for r in indep}

    preserved = indep_by["ctrl-preserved-export"]
    unpres = indep_by["ctrl-unpreserved"]
    claim = indep_by["ctrl-claim-only"]
    mismatch = indep_by["ctrl-hash-mismatch"]
    nocap = indep_by["ctrl-preserved-no-capability"]

    print(
        json.dumps(
            {
                "probe": "probe2-preservation-hashmatch",
                "independent": indep,
                "engine_verdicts": {r["id"]: r["verdict"] for r in engine_rows},
                "live_completed_retirement": sum(
                    1 for r in live_rows if r["completed_retirement"]
                ),
                "live_p1": sum(1 for r in live_rows if r["p1"]),
                "git_named_commit": located["git"]["named_commit_retrieval"],
            },
            sort_keys=True,
        )
    )

    if not preserved["matched"] or not preserved["path_exists"]:
        print("FAILED:WFA-0071-probe2 known-good export did not hash-match")
        return 1
    if by_id["ctrl-preserved-export"]["verdict"] != "RETAIN-RETIRE":
        print(
            "FAILED:WFA-0071-probe2 preserved+capability should RETAIN-RETIRE "
            f"got {by_id['ctrl-preserved-export']['verdict']}"
        )
        return 1
    if unpres["matched"] or unpres["path_exists"]:
        print("FAILED:WFA-0071-probe2 unpreserved control retrieved a copy")
        return 1
    if by_id["ctrl-unpreserved"]["completed_retirement"]:
        print("FAILED:WFA-0071-probe2 unpreserved marked completed retirement")
        return 1
    if by_id["ctrl-unpreserved"]["verdict"] != "P1-UNPRESERVED":
        print(
            f"FAILED:WFA-0071-probe2 unpreserved verdict="
            f"{by_id['ctrl-unpreserved']['verdict']}"
        )
        return 1
    if claim["matched"] or claim["path_exists"]:
        print("FAILED:WFA-0071-probe2 claim-only export should not retrieve")
        return 1
    if by_id["ctrl-claim-only"]["verdict"] != "P1-CLAIM-NOT-RECEIPT":
        print(
            "FAILED:WFA-0071-probe2 claim-only verdict="
            f"{by_id['ctrl-claim-only']['verdict']}"
        )
        return 1
    if not mismatch["path_exists"] or mismatch["matched"]:
        print("FAILED:WFA-0071-probe2 mismatch control must retrieve AND disagree")
        return 1
    if by_id["ctrl-hash-mismatch"]["verdict"] != "P1-HASH-MISMATCH":
        print(
            "FAILED:WFA-0071-probe2 hash-mismatch verdict="
            f"{by_id['ctrl-hash-mismatch']['verdict']}"
        )
        return 1
    if not nocap["matched"]:
        print("FAILED:WFA-0071-probe2 nocap export should hash-match")
        return 1
    if by_id["ctrl-preserved-no-capability"]["verdict"] != "REFUSE-RETIRE-MISSING-SURVIVAL":
        print(
            "FAILED:WFA-0071-probe2 nocap verdict="
            f"{by_id['ctrl-preserved-no-capability']['verdict']}"
        )
        return 1
    if by_id["ctrl-preserved-no-capability"]["completed_retirement"]:
        print("FAILED:WFA-0071-probe2 unnamed capability became terminal RETIRE")
        return 1

    if any(r["completed_retirement"] for r in live_rows) and not located["hits"]:
        print("FAILED:WFA-0071-probe2 live terminal RETIRE without registry")
        return 1

    if not ART.is_file():
        print("FAILED:WFA-0071-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("terminal_retire_count") != sum(
        1 for c in doc.get("candidates") or [] if c.get("completed_retirement")
    ):
        print("FAILED:WFA-0071-probe2 terminal_retire_count disagrees with candidates")
        return 1
    art_ctrl = (doc.get("controls") or {}).get("verdicts") or {}
    for cid, row in by_id.items():
        if art_ctrl.get(cid) != row["verdict"]:
            print(
                f"FAILED:WFA-0071-probe2 artifact control {cid} "
                f"{art_ctrl.get(cid)} != {row['verdict']}"
            )
            return 1

    print(
        "NEGATIVE CONTROL verbatim: retrieve+sha256 of ctrl-claim-only "
        "(manifest lists an export that is not on disk) does not match; "
        "verdict=P1-CLAIM-NOT-RECEIPT. A manifest entry is a claim, not a "
        "receipt. ctrl-hash-mismatch retrieves bytes that disagree with the "
        "claimed sha256 and is P1-HASH-MISMATCH, not RETAIN-RETIRE."
    )
    print(
        "BOTH-STATES: FIRED on unpreserved/claim-only/hash-mismatch "
        "(completed_retirement=false); SILENT/PASS on preserved-export "
        "hash-match with capability+survival named (RETAIN-RETIRE); "
        "preserved-without-capability refused."
    )
    print("SUCCESS:WFA-0071-probe2 retrieve-hash-match independent of exists()")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
