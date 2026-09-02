"""Run the ADV-0135 evasion corpus against shipped control assertions."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import controls  # noqa: E402
import councils as C  # noqa: E402
import substance  # noqa: E402

TARGET_ALSO_SILENT = {
    "A2": ("CNL-0120", "CNL-0070"),
}


def _strip_labels(council: dict[str, Any]) -> dict[str, Any]:
    blind = json.loads(json.dumps(council))
    for key in ("attack_id", "name", "defeated_control", "slipped_assertion", "kind"):
        blind.pop(key, None)
    return blind


def _row_for_council(
    council: dict[str, Any],
    *,
    attack_id: str,
    name: str,
    defeated: str,
    slipped: str,
    nc_id: str,
) -> dict[str, Any]:
    verdicts = controls.run_all(council)
    by_id = {v["control_id"]: v for v in verdicts}
    target = by_id[defeated]
    rev = substance.classify(_strip_labels(council))
    extra_ok = True
    extra_ids = TARGET_ALSO_SILENT.get(attack_id, ())
    extra_silent = []
    for cid in extra_ids:
        extra_silent.append(not by_id[cid]["fired"])
        extra_ok = extra_ok and not by_id[cid]["fired"]
    return {
        "id": attack_id,
        "name": name,
        "defeated_control": defeated,
        "slipped_assertion": slipped,
        "transcript": council,
        "control_verdicts": [
            {
                "control_id": v["control_id"],
                "fired": v["fired"],
                "verdict": v["verdict"],
                "assertion": v["assertion"],
                "detail": v["detail"],
            }
            for v in verdicts
        ],
        "target_fired": target["fired"],
        "target_verdict": target["verdict"],
        "evades_target": (not target["fired"]) and extra_ok,
        "extra_target_silent": extra_silent,
        "negative_control_id": nc_id,
        "substance_clusters": rev["substance_clusters"],
        "author_clusters": rev["author_clusters"],
        "reviewer_class": rev["class"],
        "reviewer_collapsed": rev["collapsed"],
        "reviewer_algorithm": rev["algorithm"],
    }


def _row_for_healthy(
    council: dict[str, Any],
    *,
    nc_id: str,
    paired: str,
    defeated: str,
) -> dict[str, Any]:
    verdicts = controls.run_all(council)
    by_id = {v["control_id"]: v for v in verdicts}
    target = by_id[defeated]
    rev = substance.classify(_strip_labels(council))
    any_fire = [v["control_id"] for v in verdicts if v["fired"]]
    return {
        "id": nc_id,
        "paired_attack_id": paired,
        "n_participants": council["n_participants"],
        "topology": council["topology"],
        "round_budget": council["round_budget"],
        "target_control": defeated,
        "target_control_fired": target["fired"],
        "target_control_silent": not target["fired"],
        "any_control_fired": any_fire,
        "all_shipped_silent": not any_fire,
        "reviewer_class": rev["class"],
        "reviewer_collapsed": rev["collapsed"],
        "substance_clusters": rev["substance_clusters"],
        "author_clusters": rev["author_clusters"],
        "control_verdicts": [
            {
                "control_id": v["control_id"],
                "fired": v["fired"],
                "verdict": v["verdict"],
            }
            for v in verdicts
        ],
        "transcript_id": council["council_id"],
    }


def _coc(council: dict[str, Any], expected_ids: tuple[str, ...]) -> dict[str, Any]:
    verdicts = controls.run_all(council)
    by_id = {v["control_id"]: v for v in verdicts}
    caught = [cid for cid in expected_ids if by_id[cid]["fired"]]
    fired = bool(caught)
    rev = substance.classify(_strip_labels(council))
    return {
        "id": council["council_id"],
        "caught_by": caught,
        "expected_to_catch": list(expected_ids),
        "fired": fired,
        "proves_harness_observes_firing": fired,
        "control_verdicts": [
            {
                "control_id": v["control_id"],
                "fired": v["fired"],
                "verdict": v["verdict"],
            }
            for v in verdicts
        ],
        "reviewer_class": rev["class"],
        "substance_clusters": rev["substance_clusters"],
    }


def measure() -> dict[str, Any]:
    attacks: list[dict[str, Any]] = []
    negatives: list[dict[str, Any]] = []
    for aid, name, defeated, slipped, attack_fn, healthy_fn in C.ATTACKS:
        nc_id = f"NC-{aid}"
        arow = _row_for_council(
            attack_fn(),
            attack_id=aid,
            name=name,
            defeated=defeated,
            slipped=slipped,
            nc_id=nc_id,
        )
        hrow = _row_for_healthy(
            healthy_fn(),
            nc_id=nc_id,
            paired=aid,
            defeated=defeated,
        )
        arow["healthy_negative_control_passed"] = bool(
            hrow["target_control_silent"]
            and hrow["all_shipped_silent"]
            and hrow["reviewer_class"] == "healthy"
            and not hrow["reviewer_collapsed"]
        )
        attacks.append(arow)
        negatives.append(hrow)

    coc_unanimity = _coc(C.caught_instant_unanimity(), ("CNL-0059", "CNL-0086-DEBATE-SHAPE"))
    coc_drop = _coc(C.caught_dropped_dissent(), ("CNL-0097", "CNL-0120", "CNL-0070"))

    n_evade = sum(1 for a in attacks if a["evades_target"])
    n_collapsed = sum(1 for a in attacks if a["reviewer_class"] == "collapsed")
    n_nc_pass = sum(1 for a in attacks if a["healthy_negative_control_passed"])
    n_all_silent = sum(
        1
        for a in attacks
        if a["evades_target"]
        and not any(v["fired"] for v in a["control_verdicts"])
    )
    author_reviewer_agree = all(
        a["substance_clusters"] == a["author_clusters"] for a in attacks
    ) and all(
        h["substance_clusters"] == h["author_clusters"] for h in negatives
    )

    return {
        "attacks": attacks,
        "negative_controls": negatives,
        "control_of_the_control": coc_unanimity,
        "control_of_the_control_dropped_dissent": coc_drop,
        "n_attacks": len(attacks),
        "n_evading": n_evade,
        "n_reviewer_collapsed": n_collapsed,
        "n_negative_passed": n_nc_pass,
        "n_fully_silent_on_shipped": n_all_silent,
        "author_reviewer_agree": author_reviewer_agree,
        "geometry": {
            "n_participants": C.N_PARTICIPANTS,
            "topology": C.TOPOLOGY,
            "round_budget": C.ROUND_BUDGET,
        },
        "ok": bool(
            len(attacks) >= 5
            and n_evade >= 5
            and n_collapsed == len(attacks)
            and n_nc_pass == len(attacks)
            and n_all_silent >= 5
            and coc_unanimity["fired"]
            and coc_drop["fired"]
            and author_reviewer_agree
            and all(h["reviewer_class"] == "healthy" for h in negatives)
        ),
    }


def artifact_attacks(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Read attack rows from a receipt (report/extensions) or a flat emit."""
    if isinstance(doc.get("attacks"), list) and doc["attacks"]:
        return [a for a in doc["attacks"] if isinstance(a, dict)]
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if isinstance(report.get("attacks"), list) and report["attacks"]:
        return [a for a in report["attacks"] if isinstance(a, dict)]
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    if isinstance(ext.get("attacks"), list):
        return [a for a in ext["attacks"] if isinstance(a, dict)]
    return []


def artifact_coc(doc: dict[str, Any]) -> dict[str, Any]:
    if isinstance(doc.get("control_of_the_control"), dict):
        return doc["control_of_the_control"]
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if isinstance(report.get("control_of_the_control"), dict):
        return report["control_of_the_control"]
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    if isinstance(ext.get("control_of_the_control"), dict):
        return ext["control_of_the_control"]
    return {}


def artifact_reviewer_flags(doc: dict[str, Any]) -> dict[str, Any]:
    rev = doc.get("reviewer") if isinstance(doc.get("reviewer"), dict) else {}
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    flags = {}
    if isinstance(ext.get("reviewer_flags"), dict):
        flags = ext["reviewer_flags"]
    elif isinstance(ext.get("reviewer"), dict):
        flags = ext["reviewer"]
    return {
        "independent": rev.get("independent") is True,
        "verdict": str(rev.get("verdict") or "").upper(),
        "labels_hidden": rev.get("labels_hidden") is True
        or flags.get("labels_hidden") is True,
        "control_executed": rev.get("control_executed") is True
        or flags.get("control_executed") is True,
    }


def regression_payloads(live: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in live["attacks"]:
        if not row["evades_target"]:
            continue
        out.append(
            {
                "filed_against": row["defeated_control"],
                "attack_id": row["id"],
                "path": (
                    "command-center/p2-wave/probes/ADV-0135/fixtures/regressions/"
                    f"{row['id']}.json"
                ),
                "council_id": row["transcript"]["council_id"],
                "slipped_assertion": row["slipped_assertion"],
            }
        )
    return out
