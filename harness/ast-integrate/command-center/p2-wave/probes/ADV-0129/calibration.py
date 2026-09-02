"""ADV-0129 local refuter-corps calibration substrate.

Production refuter runtime, CLAIM-REGISTRY.json, RES-0154 yield design, and
TST-0015 operator library are absent on this worktree. This module is the
confirmation-local operator library and mechanical corps. It does not claim
a missing production pipeline was exercised.
"""
from __future__ import annotations

import copy
import hashlib
import random
from pathlib import Path
from typing import Any

from stats import (
    Z_95,
    brier,
    brier_control,
    dumps,
    grouped,
    sha256_obj,
    wilson,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

SEED = 1290129
Z = Z_95
KNOWN_TOKEN = "ADV0129-KNOWN-DETECTED-TOKEN"
N_PER_STRATUM = 9
N_CLEAN = 27
N_ARM2 = 24

REFUTER_IDS = (
    "anchor-strict",
    "hygiene-scanner",
    "conservative-p0",
    "eager-pass",
)
ACCEPT = frozenset({"CONFIRMED", "PASS"})

HYGIENE_OPS = frozenset({"lf_crlf_flip", "path_separator_flip", "json_key_case_flip"})
P0_CATCH = frozenset({"sentinel_deletion", "default_argument_change"})
STRICT_OPS = HYGIENE_OPS | P0_CATCH | frozenset(
    {"mid_write_truncation", "use_vs_mention_swap"}
)

P0_REST = ["sentinel_deletion"] * 5 + ["default_argument_change"] * 6
P1_OPS = (
    ["json_key_case_flip"] * 4
    + ["mid_write_truncation"] * 4
    + ["use_vs_mention_swap"] * 4
)
P2_OPS = ["lf_crlf_flip"] * 6 + ["path_separator_flip"] * 6

ARM2_ANCHORS = (
    "command-center/WORK-UNIT-CATALOG.json",
    "command-center/p2-wave/_measure_one_delivered.py",
    "command-center/schema/architecture-review.schema.json",
    "command-center/schema/council-audit.schema.json",
)


def clean_body(i: int) -> dict[str, Any]:
    return {
        "claim_text": (
            f"Fixture claim {i:03d} asserts a measurable property of the queue item."
        ),
        "description": (
            f"Line A for item {i:03d}.\nLine B continues the description."
        ),
        "artifact_path": f"command-center/adversarial/queue/item-{i:03d}.json",
        "completion_sentinel": "SUCCESS:item-complete",
        "payload": hashlib.sha256(f"payload-{i}".encode("utf-8")).hexdigest(),
        "timeout_seconds": 30,
        "mode": "mention-only",
        "invoke": False,
        "note": f"queue-item-{i:03d}",
    }


def apply_operator(body: dict[str, Any], operator: str) -> dict[str, Any]:
    b = copy.deepcopy(body)
    if operator == "known_detected_token":
        b["note"] = f"{b['note']} {KNOWN_TOKEN}"
    elif operator == "lf_crlf_flip":
        b["description"] = b["description"].replace("\n", "\r\n")
    elif operator == "json_key_case_flip":
        b["Claim_Text"] = b.pop("claim_text")
    elif operator == "path_separator_flip":
        b["artifact_path"] = b["artifact_path"].replace("/", "\\")
    elif operator == "sentinel_deletion":
        b["completion_sentinel"] = ""
    elif operator == "mid_write_truncation":
        b["payload"] = b["payload"][:32]
    elif operator == "default_argument_change":
        b["timeout_seconds"] = 0
    elif operator == "use_vs_mention_swap":
        b["invoke"] = True
    else:
        raise ValueError(f"unknown operator {operator}")
    return b


def signatures(item: dict[str, Any]) -> list[str]:
    body = item.get("body") or {}
    found: list[str] = []
    if KNOWN_TOKEN in dumps(item):
        found.append("known_detected_token")
    if any(isinstance(v, str) and "\r\n" in v for v in body.values()):
        found.append("lf_crlf_flip")
    if any(any(c.isupper() for c in str(k)) for k in body):
        found.append("json_key_case_flip")
    path = body.get("artifact_path")
    if isinstance(path, str) and "\\" in path:
        found.append("path_separator_flip")
    if not body.get("completion_sentinel"):
        found.append("sentinel_deletion")
    payload = body.get("payload") or ""
    if isinstance(payload, str) and len(payload) != 64:
        found.append("mid_write_truncation")
    if body.get("timeout_seconds") != 30:
        found.append("default_argument_change")
    if body.get("mode") == "mention-only" and body.get("invoke") is True:
        found.append("use_vs_mention_swap")
    return found


def envelope(
    i: int, body: dict[str, Any], evidence: list[dict[str, Any]] | None
) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "id": f"CLM-{i:04d}",
        "path": f"command-center/adversarial/queue/item-{i:03d}.json",
        "author": f"queue-agent-{(i % 7) + 1}",
        "author_role": "finder",
        "schema": "claim-v1",
        "body": body,
    }
    if evidence is not None:
        rec["evidence_anchors"] = evidence
    return rec


def arm1_evidence(i: int) -> list[dict[str, Any]]:
    return [
        {
            "path": f"command-center/adversarial/queue/item-{i:03d}.json",
            "line": 1,
            "sha256": hashlib.sha256(f"arm1-{i}".encode("utf-8")).hexdigest(),
        }
    ]


def make_plant(i: int, operator: str, severity: str) -> dict[str, Any]:
    item = envelope(i, apply_operator(clean_body(i), operator), arm1_evidence(i))
    return {
        "id": item["id"],
        "kind": "plant",
        "operator": operator,
        "severity": severity,
        "item": item,
    }


def make_clean(i: int) -> dict[str, Any]:
    item = envelope(i, clean_body(i), arm1_evidence(i))
    return {
        "id": item["id"],
        "kind": "clean",
        "operator": None,
        "severity": None,
        "item": item,
    }


def file_sha256(rel: str) -> str:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def make_arm2(j: int) -> dict[str, Any]:
    i = 301 + j
    rel = ARM2_ANCHORS[j % len(ARM2_ANCHORS)]
    complete = envelope(i, clean_body(i), None)
    complete["adjudicated_verdict"] = "CONFIRMED"
    complete["adjudicated_at"] = "2026-08-01T00:00:00Z"
    complete["evidence_anchors"] = [
        {"path": rel, "line": 1, "sha256": file_sha256(rel)}
    ]
    stripped = {
        k: v
        for k, v in complete.items()
        if k not in {"evidence_anchors", "adjudicated_verdict", "adjudicated_at"}
    }
    return {
        "id": complete["id"],
        "kind": "arm2",
        "anchor": rel,
        "complete": complete,
        "stripped": stripped,
    }


def plant_pool() -> list[dict[str, Any]]:
    plants: list[dict[str, Any]] = []
    i = 101
    plants.append(make_plant(i, "known_detected_token", "P0"))
    i += 1
    for op in P0_REST:
        plants.append(make_plant(i, op, "P0"))
        i += 1
    for op in P1_OPS:
        plants.append(make_plant(i, op, "P1"))
        i += 1
    for op in P2_OPS:
        plants.append(make_plant(i, op, "P2"))
        i += 1
    return plants


def clean_pool() -> list[dict[str, Any]]:
    return [make_clean(i) for i in range(201, 237)]


def draw_sample(seed: int = SEED) -> dict[str, Any]:
    rng = random.Random(seed)
    pool = plant_pool()
    p0 = [p for p in pool if p["severity"] == "P0"]
    p1 = [p for p in pool if p["severity"] == "P1"]
    p2 = [p for p in pool if p["severity"] == "P2"]
    kd = [p for p in p0 if p["operator"] == "known_detected_token"]
    rest0 = [p for p in p0 if p["operator"] != "known_detected_token"]
    rest0.sort(key=lambda x: x["id"])
    rng.shuffle(rest0)
    chosen_p0 = kd + rest0[: N_PER_STRATUM - 1]
    p1.sort(key=lambda x: x["id"])
    rng.shuffle(p1)
    chosen_p1 = p1[:N_PER_STRATUM]
    p2.sort(key=lambda x: x["id"])
    rng.shuffle(p2)
    chosen_p2 = p2[:N_PER_STRATUM]
    plants = chosen_p0 + chosen_p1 + chosen_p2
    plants.sort(key=lambda x: x["id"])
    cleans = clean_pool()
    cleans.sort(key=lambda x: x["id"])
    rng.shuffle(cleans)
    chosen_clean = cleans[:N_CLEAN]
    stream = plants + chosen_clean
    rng.shuffle(stream)
    arm2 = [make_arm2(j) for j in range(N_ARM2)]
    payload = {
        "seed": seed,
        "stream": [
            {
                "id": rec["id"],
                "kind": rec["kind"],
                "operator": rec.get("operator"),
                "severity": rec.get("severity"),
                "item_sha256": sha256_obj(rec["item"]),
            }
            for rec in stream
        ],
        "arm2": [
            {
                "id": rec["id"],
                "complete_sha256": sha256_obj(rec["complete"]),
                "stripped_sha256": sha256_obj(rec["stripped"]),
                "anchor": rec["anchor"],
            }
            for rec in arm2
        ],
    }
    return {
        "seed": seed,
        "plants": plants,
        "cleans": chosen_clean,
        "stream": stream,
        "arm2": arm2,
        "fingerprint": sha256_obj(payload),
        "payload": payload,
        "known_detected_item_id": kd[0]["id"],
    }


def score(
    refuter_id: str, item: dict[str, Any], *, arm: int, stripped: bool
) -> dict[str, Any]:
    sigs = set(signatures(item))
    if "known_detected_token" in sigs:
        return {
            "verdict": "REFUTED",
            "confidence": 0.95,
            "p_defect": 0.95,
            "reason": "known-detected-token",
        }
    if refuter_id == "eager-pass":
        return {
            "verdict": "CONFIRMED",
            "confidence": 0.89,
            "p_defect": 0.11,
            "reason": "eager-pass-default",
        }
    catch = {
        "hygiene-scanner": HYGIENE_OPS,
        "conservative-p0": P0_CATCH,
        "anchor-strict": STRICT_OPS,
    }[refuter_id]
    hit = sorted(sigs & catch)
    if hit:
        pmap = {
            "hygiene-scanner": 0.75,
            "conservative-p0": 0.82,
            "anchor-strict": 0.86,
        }
        p = pmap[refuter_id]
        return {
            "verdict": "REFUTED",
            "confidence": p,
            "p_defect": p,
            "reason": f"signature:{hit[0]}",
        }
    if arm == 2 and stripped:
        if refuter_id == "anchor-strict":
            return {
                "verdict": "REFUTED",
                "confidence": 0.72,
                "p_defect": 0.72,
                "reason": "spec-11062-insufficient-evidence",
            }
        pmap = {"hygiene-scanner": 0.42, "conservative-p0": 0.45}
        return {
            "verdict": "NOT-CHECKED",
            "confidence": 0.58,
            "p_defect": pmap[refuter_id],
            "reason": "insufficient-evidence",
        }
    pmap = {
        "hygiene-scanner": 0.22,
        "conservative-p0": 0.23,
        "anchor-strict": 0.20,
    }
    return {
        "verdict": "CONFIRMED",
        "confidence": 0.80,
        "p_defect": pmap[refuter_id],
        "reason": "evidence-present-no-signature",
    }


def error_class(
    *,
    arm: int,
    variant: str | None,
    verdict: str,
    planted: bool,
) -> str | None:
    if arm == 1 and planted:
        return None if verdict == "REFUTED" else "false-pass"
    if arm == 1 and not planted:
        return "false-refute" if verdict == "REFUTED" else None
    if arm == 2 and variant == "stripped":
        return "false-pass" if verdict in ACCEPT else None
    if arm == 2 and variant == "complete":
        if verdict == "REFUTED":
            return "false-refute"
        if verdict != "CONFIRMED":
            return "failed-confirm"
        return None
    raise ValueError("unclassifiable row")


def row_correct(arm: int, variant: str | None, verdict: str, planted: bool) -> bool:
    if arm == 1 and planted:
        return verdict == "REFUTED"
    if arm == 1 and not planted:
        return verdict != "REFUTED"
    if arm == 2 and variant == "stripped":
        return verdict in {"REFUTED", "NOT-CHECKED"}
    if arm == 2 and variant == "complete":
        return verdict == "CONFIRMED"
    raise ValueError("unclassifiable correctness")


def build_rows(sample: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for refuter_id in REFUTER_IDS:
        for rec in sample["stream"]:
            planted = rec["kind"] == "plant"
            out = score(refuter_id, rec["item"], arm=1, stripped=False)
            verdict = out["verdict"]
            rows.append(
                {
                    "table": "arm1-recall",
                    "arm_id": "arm1-recall",
                    "arm": 1,
                    "variant": None,
                    "item_id": rec["id"],
                    "refuter_id": refuter_id,
                    "verdict": verdict,
                    "confidence": out["confidence"],
                    "p_defect": out["p_defect"],
                    "reason": out["reason"],
                    "y_should_refute": 1 if planted else 0,
                    "planted": planted,
                    "operator": rec.get("operator"),
                    "severity": rec.get("severity"),
                    "correct": row_correct(1, None, verdict, planted),
                    "error_class": error_class(
                        arm=1, variant=None, verdict=verdict, planted=planted
                    ),
                    "polarity_violation": False,
                }
            )
        for rec in sample["arm2"]:
            for variant, item, stripped, y in (
                ("stripped", rec["stripped"], True, 1),
                ("complete", rec["complete"], False, 0),
            ):
                out = score(refuter_id, item, arm=2, stripped=stripped)
                verdict = out["verdict"]
                rows.append(
                    {
                        "table": "arm2-polarity",
                        "arm_id": "arm2-polarity",
                        "arm": 2,
                        "variant": variant,
                        "item_id": rec["id"],
                        "refuter_id": refuter_id,
                        "verdict": verdict,
                        "confidence": out["confidence"],
                        "p_defect": out["p_defect"],
                        "reason": out["reason"],
                        "y_should_refute": y,
                        "planted": False,
                        "operator": None,
                        "severity": None,
                        "correct": row_correct(2, variant, verdict, False),
                        "error_class": error_class(
                            arm=2, variant=variant, verdict=verdict, planted=False
                        ),
                        "polarity_violation": variant == "stripped"
                        and verdict in ACCEPT,
                    }
                )
    return rows


def public_row(row: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "item_id",
        "refuter_id",
        "verdict",
        "confidence",
        "p_defect",
        "reason",
        "y_should_refute",
        "planted",
        "operator",
        "severity",
        "variant",
        "correct",
        "error_class",
        "polarity_violation",
    )
    return {k: row[k] for k in keys}


def metrics_from_tables(
    rows: list[dict[str, Any]], *, z: float = Z
) -> dict[str, Any]:
    wilson_rows: list[dict[str, Any]] = []
    brier_rows: list[dict[str, Any]] = []
    accuracy_rows: list[dict[str, Any]] = []
    direction_rows: list[dict[str, Any]] = []
    pass_as_evidence: list[dict[str, Any]] = []
    by_ref = grouped(rows, "refuter_id")
    for refuter_id in REFUTER_IDS:
        rr = by_ref[refuter_id]
        plants = [r for r in rr if r["arm"] == 1 and r["planted"]]
        k_hit = sum(1 for r in plants if r["verdict"] == "REFUTED")
        rec_w = {
            **wilson(k_hit, len(plants), z),
            "id": f"recall:{refuter_id}",
            "refuter_id": refuter_id,
            "metric": "arm1-recall",
        }
        wilson_rows.append(rec_w)
        for sev in ("P0", "P1", "P2"):
            sub = [r for r in plants if r.get("severity") == sev]
            k = sum(1 for r in sub if r["verdict"] == "REFUTED")
            wilson_rows.append(
                {
                    **wilson(k, len(sub), z),
                    "id": f"recall:{refuter_id}:{sev}",
                    "refuter_id": refuter_id,
                    "metric": f"arm1-recall-{sev}",
                    "severity": sev,
                }
            )
        stripped = [r for r in rr if r["arm"] == 2 and r["variant"] == "stripped"]
        k_pol = sum(1 for r in stripped if r["polarity_violation"])
        pol_w = {
            **wilson(k_pol, len(stripped), z),
            "id": f"polarity-violation:{refuter_id}",
            "refuter_id": refuter_id,
            "metric": "arm2-polarity-violation-rate",
        }
        wilson_rows.append(pol_w)
        br = brier([(float(r["p_defect"]), int(r["y_should_refute"])) for r in rr])
        brier_rows.append({"refuter_id": refuter_id, **br})
        k_ok = sum(1 for r in rr if r["correct"])
        accuracy_rows.append(
            {
                "refuter_id": refuter_id,
                "k_correct": k_ok,
                "n": len(rr),
                "point": wilson(k_ok, len(rr), z)["point"],
            }
        )
        fp = sum(1 for r in rr if r["error_class"] == "false-pass")
        fr = sum(1 for r in rr if r["error_class"] == "false-refute")
        n_err = fp + fr
        share = None if n_err == 0 else wilson(fp, n_err, z)["point"]
        direction_rows.append(
            {
                "refuter_id": refuter_id,
                "false_pass": fp,
                "false_refute": fr,
                "n_errors": n_err,
                "false_pass_share_of_errors": share,
                "note": (
                    "Reported separately from accuracy. A high-accuracy corps "
                    "whose errors are 100% false-pass is worse than a less "
                    "accurate balanced one."
                ),
            }
        )
        pass_as_evidence.append(
            {
                "refuter_id": refuter_id,
                "justified": rec_w["low"] > 0.80 and pol_w["high"] < 0.05,
                "rule": (
                    "CONFIRMED/PASS counts as evidence only if ARM-1 recall "
                    "Wilson lower bound > 0.80 AND ARM-2 polarity-violation "
                    "Wilson upper bound < 0.05. n=24 with 0 violations still "
                    "has upper bound ~0.14, so a point estimate of 0% is not "
                    "a license to treat PASS as evidence."
                ),
                "recall_low": rec_w["low"],
                "polarity_violation_high": pol_w["high"],
            }
        )
    return {
        "wilson_intervals": wilson_rows,
        "brier_scores": brier_rows,
        "accuracy": accuracy_rows,
        "error_direction": direction_rows,
        "pass_as_evidence": pass_as_evidence,
    }


def envelope_features(item: dict[str, Any]) -> dict[str, Any]:
    path = str(item.get("path") or "").replace("\\", "/")
    depth = len([p for p in path.split("/") if p])
    return {
        "path_depth": depth,
        "envelope_keys": tuple(sorted(item.keys())),
        "author_role": item.get("author_role"),
        "schema": item.get("schema"),
        "author_prefix": "queue-agent-N",
    }


def confounder_control(sample: dict[str, Any]) -> dict[str, Any]:
    plants = [r["item"] for r in sample["plants"]]
    cleans = [r["item"] for r in sample["cleans"]]
    plant_feats = {dumps(envelope_features(x)) for x in plants}
    clean_feats = {dumps(envelope_features(x)) for x in cleans}
    separated = bool(plant_feats - clean_feats) or bool(clean_feats - plant_feats)
    n = len(plants) + len(cleans)
    if n % 2 != 0:
        raise RuntimeError("confounder stream not balanced")
    k_chance = n // 2
    w = wilson(k_chance, n, Z)
    return {
        "reviewer": "envelope-only-spotter",
        "method": (
            "Classify plant vs real using only path depth, envelope keys, "
            "author role, schema, and author-prefix pattern. Body content "
            "and mutation signatures are hidden from this reviewer."
        ),
        "separated": separated,
        "n": n,
        "n_plants": len(plants),
        "n_cleans": len(cleans),
        "chance_k": k_chance,
        "wilson": {
            **w,
            "id": "confounder-chance",
            "refuter_id": "envelope-only-spotter",
        },
        "includes_chance_0_5": w["low"] <= 0.5 <= w["high"],
        "result": (
            "chance"
            if (not separated and w["low"] <= 0.5 <= w["high"])
            else "separated"
        ),
    }


def detector_control(rows: list[dict[str, Any]], item_id: str) -> dict[str, Any]:
    kd_rows = [
        r
        for r in rows
        if r["arm"] == 1 and r.get("operator") == "known_detected_token"
    ]
    misses = [r["refuter_id"] for r in kd_rows if r["verdict"] != "REFUTED"]
    return {
        "token": KNOWN_TOKEN,
        "item_id": item_id,
        "n_refuters": len(REFUTER_IDS),
        "caught_by_every_refuter": (not misses)
        and len(kd_rows) == len(REFUTER_IDS),
        "misses": misses,
        "note": (
            "A corps that misses the known-detected token invalidates the "
            "run rather than scoring zero recall."
        ),
    }


def negative_control(
    rows: list[dict[str, Any]], arm2: list[dict[str, Any]]
) -> dict[str, Any]:
    by_ref = grouped([r for r in rows if r["arm"] == 2], "refuter_id")
    per_refuter: list[dict[str, Any]] = []
    distinguishers: list[str] = []
    for refuter_id in REFUTER_IDS:
        rr = by_ref[refuter_id]
        complete_ok = True
        distinguishes_all = True
        same_verdict_n = 0
        for rec in arm2:
            c = next(
                r
                for r in rr
                if r["item_id"] == rec["id"] and r["variant"] == "complete"
            )
            s = next(
                r
                for r in rr
                if r["item_id"] == rec["id"] and r["variant"] == "stripped"
            )
            if c["verdict"] != "CONFIRMED":
                complete_ok = False
            if c["verdict"] == s["verdict"]:
                distinguishes_all = False
                same_verdict_n += 1
        if distinguishes_all:
            distinguishers.append(refuter_id)
        per_refuter.append(
            {
                "refuter_id": refuter_id,
                "complete_all_confirmed": complete_ok,
                "distinguishes_every_claim": distinguishes_all,
                "same_verdict_n": same_verdict_n,
            }
        )
    spec_ok = any(
        p["complete_all_confirmed"]
        for p in per_refuter
        if p["refuter_id"] != "eager-pass"
    )
    harness_ok = bool(distinguishers) and spec_ok
    return {
        "n_claims": len(arm2),
        "harness_measures_something": harness_ok,
        "distinguishers": distinguishers,
        "per_refuter": per_refuter,
        "note": (
            "If stripped and complete copies get the same verdict for every "
            "refuter, the harness is measuring nothing."
        ),
    }


def flake_runs(seed: int = SEED) -> dict[str, Any]:
    fps = []
    for run in (1, 2, 3):
        sample = draw_sample(seed)
        fps.append({"run": run, "sample_fingerprint": sample["fingerprint"]})
    base = fps[0]["sample_fingerprint"]
    for row in fps:
        row["identical_to_run_1"] = row["sample_fingerprint"] == base
    if not all(r["identical_to_run_1"] for r in fps):
        raise RuntimeError("deterministic sample was not stable across 3 draws")
    return {
        "runs_recorded": 3,
        "rule": (
            "Every run's outcome is recorded. A corps that scores well on "
            "run 3 of 3 is reported as 1/3, never as the result. This "
            "mechanical corps is deterministic, so the three draws are "
            "identical and are reported as 3/3 identical, not as a selected "
            "best run."
        ),
        "outcomes": fps,
        "reported_as": "3/3 identical (deterministic mechanical corps)",
    }


def run_calibration(seed: int = SEED) -> dict[str, Any]:
    sample = draw_sample(seed)
    rows = build_rows(sample)
    metrics = metrics_from_tables(rows, z=Z)
    detector = detector_control(rows, sample["known_detected_item_id"])
    if not detector["caught_by_every_refuter"]:
        raise RuntimeError(f"detector control failed: {detector}")
    confounder = confounder_control(sample)
    if confounder["separated"] or confounder["result"] != "chance":
        raise RuntimeError(f"confounder control failed: {confounder}")
    negative = negative_control(rows, sample["arm2"])
    if not negative["harness_measures_something"]:
        raise RuntimeError(f"negative control failed: {negative}")
    arm1_rows = [r for r in rows if r["arm"] == 1]
    arm2_rows = [r for r in rows if r["arm"] == 2]
    return {
        "sample": sample,
        "rows": rows,
        "tables": [
            {
                "id": "arm1-recall",
                "arm_id": "arm1-recall",
                "rows": [public_row(r) for r in arm1_rows],
            },
            {
                "id": "arm2-polarity",
                "arm_id": "arm2-polarity",
                "rows": [public_row(r) for r in arm2_rows],
            },
        ],
        "metrics": metrics,
        "controls": {
            "negative": negative,
            "detector": detector,
            "confounder": confounder,
            "scorer": brier_control(),
        },
        "flake": flake_runs(seed),
        "z": Z,
        "seed": seed,
    }
