#!/usr/bin/env python3
"""Probe 1: reconstruction from the explanation alone.

A subprocess of tools/router/reconstruct.py is given only the explanation JSON
(no labelled gold). The printed selected set must equal the frozen gold labels.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "router"))

import explain as E  # noqa: E402
import scenario as S  # noqa: E402

RECEIPT = REPO / "command-center/receipts/IMP-0395.json"
RECON = REPO / "tools/router/reconstruct.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0395/probe1_reconstruct.py"
)


def parse_blocks(text: str) -> dict[str, list[str]]:
    blocks: dict[str, list[str]] = {}
    qid = None
    ids: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("query_id="):
            if qid is not None:
                blocks[qid] = ids
            qid = line.split("=", 1)[1]
            ids = []
        elif line.startswith("count="):
            continue
        elif line:
            ids.append(line)
    if qid is not None:
        blocks[qid] = ids
    return blocks


def run_reconstruct(path: Path) -> tuple[int, str]:
    p = subprocess.run(
        [sys.executable, "-B", str(RECON), str(path)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    index = S.load_index()
    known = S.index_ids(index)
    if not RECON.is_file():
        print("FAILED:IMP-0395-probe1 reconstruct.py missing")
        return 1

    mismatches = []
    with tempfile.TemporaryDirectory(prefix="imp0395-recon-") as td:
        tdir = Path(td)
        for case in S.cases():
            gold = list(case["gold_selected"])
            expl = E.explain_one(S.case_to_trace(case), index)
            for row in expl["selected"]:
                if not row.get("producing_rule") or not row.get("reason"):
                    print("FAILED:IMP-0395-probe1 selected missing why", row)
                    return 1
                if str(row["capability_id"]) not in known:
                    print("FAILED:IMP-0395-probe1 selected not in index", row["capability_id"])
                    return 1
            for row in expl["near_misses"]:
                if str(row["capability_id"]) not in known:
                    print("FAILED:IMP-0395-probe1 near-miss not in index", row["capability_id"])
                    return 1
            qpath = tdir / f"{expl['query_id']}.json"
            qpath.write_text(json.dumps(expl, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
            rc, out = run_reconstruct(qpath)
            print(f"reconstruct {expl['query_id']} rc={rc}")
            if rc != 0:
                print(out[-1500:])
                print("FAILED:IMP-0395-probe1 reconstruct exit", rc)
                return 1
            blocks = parse_blocks(out)
            got = blocks.get(expl["query_id"])
            if got is None:
                print("FAILED:IMP-0395-probe1 no query_id in reconstruct output")
                print(out)
                return 1
            if got != gold:
                mismatches.append((expl["query_id"], gold, got))
            print(f"  gold={gold} reconstructed={got} match={got == gold}")

    if mismatches:
        print("FAILED:IMP-0395-probe1 reconstruction mismatch", mismatches)
        return 1

    if RECEIPT.is_file():
        rc, out = run_reconstruct(RECEIPT)
        print(f"receipt reconstruct rc={rc}")
        if rc != 0:
            print(out[-1500:])
            print("FAILED:IMP-0395-probe1 receipt reconstruct")
            return 1
        blocks = parse_blocks(out)
        for case in S.cases():
            qid = case["query_id"]
            gold = list(case["gold_selected"])
            got = blocks.get(qid)
            if got != gold:
                print(f"FAILED:IMP-0395-probe1 receipt {qid} gold={gold} got={got}")
                return 1
        text = RECEIPT.read_text(encoding="utf-8")
        if "SENTINEL:IMP-0395:EXPLANATION-RECONSTRUCTIBLE" not in text:
            print("FAILED:IMP-0395-probe1 sentinel absent from receipt")
            return 1

    print("SUCCESS:IMP-0395-probe1 reconstruction from explanation only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
