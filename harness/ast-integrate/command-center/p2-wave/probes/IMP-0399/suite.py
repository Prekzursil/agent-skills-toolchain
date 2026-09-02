#!/usr/bin/env python3
"""Regression suite the IMP-0399 mutation harness turns RED."""
from __future__ import annotations

from typing import Any

from router import PIN_DIGEST, PIN_MODEL_ID, popularity_top3, route


def _fail(fid: str, detail: str) -> dict[str, str]:
    return {"id": fid, "detail": detail}


def run_suite(cfg: dict[str, Any]) -> dict[str, Any]:
    corpus = (cfg.get("corpus") or {}).get("items") or []
    failures: list[dict[str, str]] = []
    per_item: list[dict[str, Any]] = []

    for item in corpus:
        qid = str(item.get("id") or "")
        expected = list(item.get("expected") or [])
        got_route = route(
            cfg,
            str(item.get("query") or ""),
            cwd=str(item.get("cwd") or "/opt/app"),
            project=str(item.get("project") or "app"),
        )
        got = list(got_route.get("selected") or [])
        row = {
            "id": qid,
            "expected": expected,
            "got": got,
            "embed_status": got_route.get("embed_status"),
            "mode": got_route.get("mode"),
            "triggers_fired": got_route.get("triggers_fired"),
            "match": got == expected,
        }
        per_item.append(row)
        if got != expected:
            failures.append(
                _fail(
                    f"CORPUS:{qid}",
                    f"expected={expected} got={got} mode={got_route.get('mode')}",
                )
            )
        if "cap.debug-dump" in got:
            failures.append(
                _fail(
                    f"BAN-LEAK:{qid}",
                    "banned cap.debug-dump was selected",
                )
            )
        if got_route.get("embed_status") != "PINNED":
            failures.append(
                _fail(
                    f"PIN-REQUIRED:{qid}",
                    f"embed_status={got_route.get('embed_status')} "
                    f"digest={got_route.get('model_digest')!r}",
                )
            )
        elif got_route.get("model_digest") != PIN_DIGEST:
            failures.append(
                _fail(
                    f"PIN-DIGEST:{qid}",
                    "pinned digest does not match encoder identity",
                )
            )
        elif got_route.get("model_id") != PIN_MODEL_ID:
            failures.append(
                _fail(
                    f"PIN-MODEL:{qid}",
                    f"model_id={got_route.get('model_id')!r}",
                )
            )

        again = route(
            cfg,
            str(item.get("query") or ""),
            cwd=str(item.get("cwd") or "/opt/app"),
            project=str(item.get("project") or "app"),
        )
        if again.get("selected") != got:
            failures.append(
                _fail(f"DETERMINISM:{qid}", "second route differed")
            )

    # Corpus must defeat always-top-3 popularity (IMP-0398 property).
    top3 = popularity_top3(cfg)
    base_hits = 0
    for item in corpus:
        expected = set(item.get("expected") or [])
        if set(top3) == expected:
            base_hits += 1
    n = len(corpus) or 1
    baseline_exact = base_hits / n
    if baseline_exact >= 0.20:
        failures.append(
            _fail(
                "CORPUS-TOO-EASY",
                f"always-top-3 exact-set rate {baseline_exact:.3f} >= 0.20 "
                f"top3={top3}",
            )
        )

    negatives = [i for i in corpus if not (i.get("expected") or [])]
    if len(corpus) and (len(negatives) / len(corpus)) < 0.25:
        failures.append(
            _fail(
                "CORPUS-NEGATIVES",
                f"negative fraction {len(negatives)}/{len(corpus)} < 0.25",
            )
        )

    red = len(failures) > 0
    return {
        "red": red,
        "green": not red,
        "n_failures": len(failures),
        "failures": failures,
        "n_items": len(corpus),
        "n_negatives": len(negatives),
        "negative_fraction": (len(negatives) / n) if corpus else 0.0,
        "popularity_top3": top3,
        "baseline_exact_set_rate": baseline_exact,
        "per_item": per_item,
        "pin_digest": PIN_DIGEST,
    }
