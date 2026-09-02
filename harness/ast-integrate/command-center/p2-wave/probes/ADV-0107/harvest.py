"""Load fixture + live digest boundaries and measure survival."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from counter import count_text, survival
from semantic import compare_pair

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"
ORACLE = json.loads((FIX / "oracle.json").read_text(encoding="utf-8"))

PAIR_FILES = (
    {
        "id": "raw-to-digest",
        "src": "raw_round.md",
        "dst": "digest_round.md",
        "oracle_key": "raw_to_digest",
    },
    {
        "id": "digest-to-digest-of-digest",
        "src": "digest_round.md",
        "dst": "digest_of_digest.md",
        "oracle_key": "digest_to_dod",
    },
)
LIVE_NAME_MARKERS = ("digest", "DIGEST", "summary", "SUMMARY")


def _read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def mention_control() -> dict[str, Any]:
    text = _read("mention_vocab.md")
    counted = count_text(text)
    exp = ORACLE["mention"]
    naive_ok = all(counted["naive"][k] >= exp["naive_min"][k] for k in exp["naive_min"])
    use_ok = counted["use"] == exp["use"]
    naive_inflates = all(
        counted["naive"][k] > counted["use"][k]
        for k in ("unverified", "band", "file_line", "url")
    )
    return {
        "id": "use-vs-mention",
        "naive": counted["naive"],
        "use": counted["use"],
        "mention": counted["mention"],
        "oracle_use": exp["use"],
        "oracle_naive_min": exp["naive_min"],
        "use_matches_oracle": use_ok,
        "naive_meets_floor": naive_ok,
        "naive_strictly_exceeds_use": naive_inflates,
        "pass": use_ok and naive_ok and naive_inflates,
    }


def fixture_boundaries() -> list[dict[str, Any]]:
    rows = []
    for spec in PAIR_FILES:
        src_text = _read(spec["src"])
        dst_text = _read(spec["dst"])
        src_c = count_text(src_text)
        dst_c = count_text(dst_text)
        rates = survival(src_c["use"], dst_c["use"])
        oracle = ORACLE[spec["oracle_key"]]
        src_ok = src_c["use"] == oracle["src_use"]
        dst_ok = dst_c["use"] == oracle["dst_use"]
        sem = compare_pair(src_text, dst_text)
        rows.append(
            {
                "id": spec["id"],
                "src_rel": f"fixtures/{spec['src']}",
                "dst_rel": f"fixtures/{spec['dst']}",
                "src_use": src_c["use"],
                "dst_use": dst_c["use"],
                "src_naive": src_c["naive"],
                "dst_naive": dst_c["naive"],
                "survival": rates,
                "oracle_src_use": oracle["src_use"],
                "oracle_dst_use": oracle["dst_use"],
                "matches_oracle": src_ok and dst_ok,
                "semantic": {
                    "source_use_n": sem["source_use_n"],
                    "mechanical_survivors": sem["mechanical_survivors"],
                    "mechanical_losses": sem["mechanical_losses"],
                    "semantic_survivors_among_mech_loss": sem[
                        "semantic_survivors_among_mech_loss"
                    ],
                    "true_losses": sem["true_losses"],
                    "semantic_only": [
                        {
                            "kind": r["kind"],
                            "value": r["value"],
                            "claim_id": r["claim_id"],
                            "why": r["why"],
                        }
                        for r in sem["semantic_only_rows"]
                    ],
                    "true_loss": [
                        {
                            "kind": r["kind"],
                            "value": r["value"],
                            "claim_id": r["claim_id"],
                            "why": r["why"],
                        }
                        for r in sem["true_loss_rows"]
                    ],
                },
            }
        )
    return rows


def live_pairs(repo: Path) -> dict[str, Any]:
    roots = [repo / "command-center"]
    found: list[str] = []
    skip = {"command-center/p2-wave/probes/ADV-0107"}
    for root in roots:
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(repo).as_posix()
            if any(rel.startswith(s) for s in skip):
                continue
            if not any(m in p.name for m in LIVE_NAME_MARKERS):
                continue
            if p.stat().st_size <= 0:
                continue
            found.append(rel)
            if len(found) >= 40:
                break
    return {
        "pair_count": 0,
        "digest_named_files": found[:40],
        "digest_named_file_count": len(found),
        "reason": (
            "No production raw↔digest pairs with a declared pairing key were "
            "found. Digest-named files are listed when present; survival is "
            "NOT-CHECKED on the live program until a pairing exists."
        ),
    }


def measure() -> dict[str, Any]:
    mention = mention_control()
    bounds = fixture_boundaries()
    live = live_pairs(REPO)
    all_oracle = all(b["matches_oracle"] for b in bounds)
    sem0 = bounds[0]["semantic"]
    planted_keep = any(
        r.get("claim_id") == "C-U3" and r["kind"] == "unverified"
        for r in sem0["semantic_only"]
    )
    planted_file = any(
        "queue.py:100" in str(r.get("value")) for r in sem0["semantic_only"]
    )
    planted_loss = any(
        r.get("claim_id") == "C-U4" and r["kind"] == "unverified"
        for r in sem0["true_loss"]
    )
    url_all_lost = bounds[0]["survival"]["url"]["survival_rate"] == 0.0
    return {
        "mention": mention,
        "boundaries": bounds,
        "live": live,
        "fixture_oracle_ok": all_oracle,
        "semantic_planted_keep_ok": planted_keep and planted_file,
        "semantic_planted_loss_ok": planted_loss,
        "url_total_loss_at_first_boundary": url_all_lost,
        "pass_mechanical": mention["pass"] and all_oracle,
        "pass_semantic": planted_keep and planted_file and planted_loss,
    }
