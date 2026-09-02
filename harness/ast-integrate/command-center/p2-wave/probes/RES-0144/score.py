"""Apply both raters, compute kappa, run syndication vs unique-URL controls."""
from __future__ import annotations

import hashlib
import time
from typing import Any

import corpus as C
import kappa as K
import rater_a as A
import rater_b as B
from rubric import AUTHORITY_LEVELS, INDEPENDENCE_LEVELS, LOW_INDEPENDENCE, published_sha256

UNIT = "RES-0144"


def body_sha256(body: str) -> str:
    return hashlib.sha256(body.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def poller_independence(_src: dict[str, Any], _corpus: list[dict[str, Any]]) -> str:
    """Naive unique-URL heuristic: every distinct URL is ORIGINATING."""
    return "ORIGINATING"


def sheet_from(rows: list[dict[str, Any]], rater: str) -> dict[str, Any]:
    return {
        "unit_id": UNIT,
        "rater": rater,
        "n": len(rows),
        "rows": [
            {
                "id": r["id"],
                "authority": r["authority"],
                "independence": r["independence"],
                "low_independence": r["low_independence"],
                "why": r.get("why") or r.get("authority_why"),
            }
            for r in rows
        ],
    }


def disagreements(a_rows: list[dict[str, Any]], b_rows: list[dict[str, Any]], axis: str) -> list[dict[str, Any]]:
    bmap = {r["id"]: r for r in b_rows}
    out = []
    for ar in a_rows:
        br = bmap[ar["id"]]
        if ar[axis] != br[axis]:
            out.append(
                {
                    "id": ar["id"],
                    "axis": axis,
                    "rater_a": ar[axis],
                    "rater_b": br[axis],
                    "a_why": ar.get("why"),
                    "b_why": br.get("why") if axis == "independence" else br.get("authority_why"),
                }
            )
    return out


def level_pairs(dis: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in dis:
        key = f"{row['rater_a']}|{row['rater_b']}"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def both_states(corpus: list[dict[str, Any]], a_rows: list[dict[str, Any]], b_rows: list[dict[str, Any]]) -> dict[str, Any]:
    amap = {r["id"]: r for r in a_rows}
    bmap = {r["id"]: r for r in b_rows}
    smap = {s["id"]: s for s in corpus}

    def row_for(sid: str, plant: str) -> dict[str, Any]:
        src = smap[sid]
        a_low = bool(amap[sid]["low_independence"])
        b_low = bool(bmap[sid]["low_independence"])
        watcher_wake = a_low and b_low
        poller_high = poller_independence(src, corpus) not in LOW_INDEPENDENCE
        return {
            "id": sid,
            "plant": plant,
            "watcher_wake": watcher_wake,
            "poller_wake": poller_high,
            "rater_a_independence": amap[sid]["independence"],
            "rater_b_independence": bmap[sid]["independence"],
            "poller_independence": poller_independence(src, corpus),
        }

    synd = [row_for(i, "verbatim-syndicated-copy") for i in C.syndicated_ids()]
    indep = [row_for(i, "unique-originating-body") for i in C.independent_originating_ids()]
    synd_ok = all(r["watcher_wake"] is True and r["poller_wake"] is True for r in synd)
    indep_ok = all(r["watcher_wake"] is False and r["poller_wake"] is True for r in indep)
    if not synd:
        synd_ok = False
    if not indep:
        indep_ok = False
    silent_both = (not any(r["watcher_wake"] for r in synd)) and (not any(r["watcher_wake"] for r in indep))
    fire_both = all(r["watcher_wake"] for r in synd) and all(r["watcher_wake"] for r in indep)
    cases = []
    cases.append(
        {
            "id": "syndicated-verbatim-five",
            "plant": "five sources share one verbatim body at five URLs",
            "watcher_wake": all(r["watcher_wake"] for r in synd),
            "poller_wake": all(r["poller_wake"] for r in synd),
            "verdict": "PASS" if synd_ok else "FAIL",
            "members": synd,
        }
    )
    cases.append(
        {
            "id": "independent-originating-five",
            "plant": "five unique originating bodies at five URLs",
            "watcher_wake": any(r["watcher_wake"] for r in indep),
            "poller_wake": all(r["poller_wake"] for r in indep),
            "verdict": "PASS" if indep_ok else "FAIL",
            "members": indep,
        }
    )
    false_wake_n = sum(1 for r in synd if not r["watcher_wake"])
    return {
        "pass": bool(synd_ok and indep_ok and not silent_both and not fire_both),
        "syndicated_ok": synd_ok,
        "independent_ok": indep_ok,
        "silent_in_both_states": silent_both,
        "fires_in_both_states": fire_both,
        "false_wake_rate": false_wake_n / max(len(synd), 1),
        "poller_false_independent_rate": (
            sum(1 for r in synd if r["poller_wake"]) / max(len(synd), 1)
        ),
        "cases": cases,
    }


def run() -> dict[str, Any]:
    t0 = time.perf_counter()
    corpus = C.sources()
    a_rows = A.score_all(corpus)
    b_rows = B.score_all(corpus)
    elapsed = time.perf_counter() - t0
    if len(corpus) != 40 or len(a_rows) != 40 or len(b_rows) != 40:
        raise RuntimeError(f"sample-size {len(corpus)} {len(a_rows)} {len(b_rows)}")
    y_auth_a = [r["authority"] for r in a_rows]
    y_auth_b = [r["authority"] for r in b_rows]
    y_ind_a = [r["independence"] for r in a_rows]
    y_ind_b = [r["independence"] for r in b_rows]
    y_joint_a = [f"{r['authority']}+{r['independence']}" for r in a_rows]
    y_joint_b = [f"{r['authority']}+{r['independence']}" for r in b_rows]
    auth = K.cohen_kappa(y_auth_a, y_auth_b, AUTHORITY_LEVELS)
    indep = K.cohen_kappa(y_ind_a, y_ind_b, INDEPENDENCE_LEVELS)
    joint_labels = sorted(set(y_joint_a) | set(y_joint_b))
    joint = K.cohen_kappa(y_joint_a, y_joint_b, joint_labels)
    d_auth = disagreements(a_rows, b_rows, "authority")
    d_ind = disagreements(a_rows, b_rows, "independence")
    ctrl = both_states(corpus, a_rows, b_rows)
    synd_ids = set(C.syndicated_ids())
    synd_a_low = all(r["low_independence"] for r in a_rows if r["id"] in synd_ids)
    synd_b_low = all(r["low_independence"] for r in b_rows if r["id"] in synd_ids)
    return {
        "corpus": corpus,
        "rater_a": a_rows,
        "rater_b": b_rows,
        "sheet_a": sheet_from(a_rows, "A"),
        "sheet_b": sheet_from(b_rows, "B"),
        "kappa_authority": auth,
        "kappa_independence": indep,
        "kappa_joint": joint,
        "authority_disagreements": d_auth,
        "independence_disagreements": d_ind,
        "authority_disagreement_levels": level_pairs(d_auth),
        "independence_disagreement_levels": level_pairs(d_ind),
        "controls": ctrl,
        "syndicated_all_low_a": synd_a_low,
        "syndicated_all_low_b": synd_b_low,
        "elapsed_seconds": elapsed,
        "sample_size": 40,
        "rubric_sha256": published_sha256(),
        "lineage": [
            {
                "id": s["id"],
                "resolved_url": s["url"],
                "fetch_timestamp": s["captured_at"],
                "sha256": body_sha256(s["body"]),
            }
            for s in corpus
        ],
    }
