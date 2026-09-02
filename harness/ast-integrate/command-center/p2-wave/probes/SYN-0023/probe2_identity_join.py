#!/usr/bin/env python3
"""Probe 2: identity join vs title join, plus independent share recompute."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from attribute import (  # noqa: E402
    CONFORMITY,
    CORROBORATED,
    JOIN_IDENTITY,
    JOIN_TITLE,
    OUT_REL,
    attribute_scenario,
    load_json,
    load_planted_scenarios,
    share_from_labels,
)


def title_trap() -> dict:
    for scenario in load_planted_scenarios():
        if scenario.get("id") == "planted-title-trap":
            return scenario
    raise SystemExit("FAILED:SYN-0023-probe2 title-trap fixture missing")


def main() -> int:
    scenario = title_trap()
    ident = attribute_scenario(scenario, join=JOIN_IDENTITY)
    titled = attribute_scenario(scenario, join=JOIN_TITLE)
    print(
        "title_trap identity="
        f"{ident['observed_label']} title_join={titled['observed_label']}"
    )
    print(
        "identities "
        f"{ {aid: rec['identity'] for aid, rec in ident['artifacts'].items()} }"
    )
    if ident["observed_label"] != CORROBORATED:
        print("FAILED:SYN-0023-probe2 identity join labelled title collision CONFORMITY")
        return 1
    if titled["observed_label"] != CONFORMITY:
        print("FAILED:SYN-0023-probe2 title join did not collapse same-title artifacts")
        return 1
    if ident["observed_label"] == titled["observed_label"]:
        print("FAILED:SYN-0023-probe2 identity and title joins agreed; detector is inert")
        return 1
    titles = {rec.get("title") for rec in ident["artifacts"].values()}
    shas = {rec.get("sha256") for rec in ident["artifacts"].values()}
    if len(titles) != 1:
        print(f"FAILED:SYN-0023-probe2 fixture titles not collided titles={titles}")
        return 1
    if len(shas) != 2:
        print(f"FAILED:SYN-0023-probe2 fixture sha256 not distinct shas={shas}")
        return 1

    def domain(doc: dict) -> dict:
        report = doc.get("report")
        if isinstance(report, dict) and (
            report.get("kind") == "convergence-attribution"
            or report.get("planted_controls")
            or report.get("join_key")
        ):
            return report
        return doc

    art = REPO / OUT_REL
    if art.is_file() and art.stat().st_size > 0:
        doc = load_json(art)
        payload = domain(doc) if isinstance(doc, dict) else {}
        planted = payload.get("planted_controls") or []
        labels = [str(row.get("observed_label")) for row in planted if isinstance(row, dict)]
        recomputed = share_from_labels(labels, "planted controls (recomputed)")
        published = payload.get("planted_conformity_share") or {}
        print(
            "recomputed_planted_share "
            f"{recomputed['numerator']}/{recomputed['denominator']} "
            f"published={published.get('numerator')}/{published.get('denominator')}"
        )
        if published.get("numerator") != recomputed["numerator"] or published.get(
            "denominator"
        ) != recomputed["denominator"]:
            print("FAILED:SYN-0023-probe2 planted share does not recompute from table")
            return 1
        live = payload.get("conformity_share") or {}
        live_labels = [
            str(row.get("label"))
            for row in (payload.get("agreed_conclusions") or [])
            if isinstance(row, dict) and row.get("population") == "live"
        ]
        live_re = share_from_labels(
            live_labels, "SYN-0010 agreed conclusions (live); planted controls excluded"
        )
        if live.get("numerator") != live_re["numerator"] or live.get("denominator") != live_re[
            "denominator"
        ]:
            print("FAILED:SYN-0023-probe2 live share does not recompute from table")
            return 1
        if live_re["denominator"] == 0 and live.get("status") != "UNIVERSE-EMPTY":
            print("FAILED:SYN-0023-probe2 empty live universe not labelled UNIVERSE-EMPTY")
            return 1
        if str(payload.get("join_key") or doc.get("join_key")) != "artifact-identity":
            print("FAILED:SYN-0023-probe2 join_key is not artifact-identity")
            return 1
    else:
        print("receipt absent; title-trap only")

    print(
        json.dumps(
            {
                "probe": "probe2-identity-join",
                "identity_label": ident["observed_label"],
                "title_label": titled["observed_label"],
                "pass": True,
            }
        )
    )
    print("SUCCESS:SYN-0023-probe2 identity join and share recompute")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
