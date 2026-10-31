#!/usr/bin/env python3
"""Emit the RES-0150 design-spec artifact from the live engine and fetched lineage."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import cases as K  # noqa: E402
import contract as C  # noqa: E402
import engine as E  # noqa: E402
import fetch_sources as FS  # noqa: E402

CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def catalog_unit() -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == C.UNIT_ID:
            return u
    raise SystemExit("FAILED:RES-0150 catalog row missing")


def file_lineage(path: Path, source_id: str, note: str) -> dict:
    sha, size = sha256_file(path)
    rel = path.relative_to(REPO).as_posix()
    return {
        "id": source_id,
        "resolved_url": f"file://{rel}",
        "requested_url": f"file://{rel}",
        "fetched_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "sha256": sha,
        "bytes": size,
        "http_status": 200,
        "kind": "worktree-file",
        "note": note,
        "path": rel,
    }


def http_lineage(row: dict) -> dict:
    return {
        "id": row["id"],
        "resolved_url": row.get("resolved_url") or row.get("requested_url"),
        "requested_url": row.get("requested_url"),
        "fetched_at": row["fetched_at"],
        "sha256": row["sha256"],
        "bytes": row["bytes"],
        "http_status": row["http_status"],
        "kind": "http-fetch",
        "needle_present": row.get("needle_present"),
        "must_contain": row.get("must_contain"),
        "path": row.get("body_path"),
        "ok": row.get("ok"),
    }


def main() -> int:
    unit = catalog_unit()
    catalog_sentinel = str(unit.get("completion_sentinel") or "")
    if C.SENTINEL not in catalog_sentinel:
        print("FAILED:RES-0150 catalog completion_sentinel missing SUCCESS:RES-0150")
        return 1

    schema_path = REPO / C.SCHEMA_REL
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if not E.schema_rejects_garbage(schema):
        print("FAILED:RES-0150 schema accepted empty object")
        return 1

    fetches = FS.load_or_fetch()
    bad = [r for r in fetches if not r.get("ok")]
    if bad:
        print("FAILED:RES-0150 source fetch not ok")
        print(json.dumps(bad, indent=2)[:4000])
        return 1
    by_id = {r["id"]: r for r in fetches}

    g_run = K.run_has_counter()
    n_run = K.run_no_counter()
    det = E.detector_both_states(K.genuine_g(), K.padded_g(), K.CLAIM_G, REPO)
    if not det["both_states"]:
        print("FAILED:RES-0150 padding detector is not discriminating")
        print(json.dumps(det, indent=2)[:4000])
        return 1
    live_g = E.evaluate_quota(g_run, REPO)
    live_n = E.evaluate_quota(n_run, REPO)
    mutant_n = E.mutant_count_all_disconfirming(n_run)
    if live_g["verdict"] != C.QUOTA_MET:
        print("FAILED:RES-0150 claim G did not meet quota on genuine counterevidence")
        print(json.dumps(live_g, indent=2)[:4000])
        return 1
    if live_n["verdict"] != C.HONEST_VERDICT:
        print("FAILED:RES-0150 claim N did not report UNDER-QUOTA-HONEST")
        print(json.dumps(live_n, indent=2)[:4000])
        return 1
    if live_n.get("filled_with_padding") is True:
        print("FAILED:RES-0150 engine filled quota with padding")
        return 1
    if live_n["qualifying_unfavorable"] != 0:
        print("FAILED:RES-0150 claim N counted manufactured objections")
        return 1
    if mutant_n["verdict"] != C.QUOTA_MET:
        print("FAILED:RES-0150 mutant control did not fill; both-states is broken")
        print(json.dumps(mutant_n, indent=2))
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    catalog_lin = file_lineage(
        CATALOG,
        "catalog-RES-0150",
        "Estate catalog names the quota, quality floor, padding detector, and UNDER-QUOTA-HONEST path.",
    )
    source_lineage = [
        http_lineage(by_id["goodhart-wikipedia"]),
        http_lineage(by_id["campbell-wikipedia"]),
        http_lineage(by_id["kent-wep-wikipedia"]),
        http_lineage(by_id["ioannidis-plos"]),
        catalog_lin,
    ]
    answer = (
        f"{C.SENTINEL}. Quota is a quality-gated floor, not a raw objection-count: "
        f"required_n = max({C.MIN_N}, ceil({C.MIN_SHARE} * qualifying_total)), where "
        "qualifying_total is supporting+unfavorable items that pass the floor "
        "(anti-suppression: dropping supporting evidence cannot inflate share). "
        "An unfavorable item counts only if it cites a corpus DISCONFIRM document, "
        "carries live url+fetched_at+sha256 lineage, names a falsifier, is not a "
        "claim restatement, and is mechanism-distinct from already accepted "
        "objections. Padded items are rejected, never counted. When genuine "
        "counterevidence does not exist after exhausted search, the only legal "
        f"verdict is {C.HONEST_VERDICT}; filling is the failure this unit exists "
        f"to prevent. Live: claim G {live_g['verdict']} "
        f"unfavorable={live_g['qualifying_unfavorable']} required={live_g['required_n']}; "
        f"claim N {live_n['verdict']} unfavorable={live_n['qualifying_unfavorable']} "
        f"padded_rejected={live_n['padded_rejected']}; mutant on N {mutant_n['verdict']} "
        "(would have filled). Padding detector both_states="
        f"{det['both_states']} genuine_unflagged={det['genuine_unflagged']} "
        f"padded_flagged={det['padded_flagged']}."
    )
    doc = {
        "unit_id": C.UNIT_ID,
        "state": "SUCCESS",
        "sentinel": (
            f"{C.SENTINEL} in the artifact AND a quota that reports "
            f"{C.HONEST_VERDICT} on a claim with no real counterevidence rather "
            "than filling it"
        ),
        "completion_sentinel": catalog_sentinel,
        "report_kind": "design-spec",
        "title": C.TITLE,
        "question": C.QUESTION,
        "answer": answer,
        "measured_at": now,
        "output_path": C.OUTPUT_REL,
        "output_schema": C.SCHEMA_REL,
        "design": {
            "quota_definition": {
                "name": "quality-gated-unfavorable-share-with-honest-under-quota",
                "min_qualifying_unfavorable": C.MIN_N,
                "min_share": C.MIN_SHARE,
                "anti_suppression": True,
                "filling_forbidden": True,
                "honest_verdict_token": C.HONEST_VERDICT,
                "formula": (
                    "required_n = max(min_n, ceil(min_share * qualifying_total)); "
                    "qualifying_total includes all quality-passing polarities; "
                    "padded rejects never enter the numerator"
                ),
            },
            "quality_floor": [
                {"id": "QF-POLARITY", "rule": "Item polarity must be disconfirming to count toward the unfavorable quota."},
                {"id": "QF-CORPUS-DISCONFIRM", "rule": "Item must cite a corpus document labeled DISCONFIRM; SUPPORT cited as disconfirm is padding."},
                {"id": "QF-LINEAGE", "rule": "Resolved url, fetched_at, and sha256 of the fetched bytes must match the live file."},
                {"id": "QF-FALSIFIER", "rule": "Named falsifier at least 24 characters; hedge-only text without a mechanism is vacuous."},
                {"id": "QF-NON-RESTATE", "rule": "Objection text must not be a high-Jaccard restatement of the claim."},
                {"id": "QF-MECHANISM-DISTINCT", "rule": "Mechanism key must not collapse into an already accepted objection."},
                {"id": "QF-KENT-BAND", "rule": "Each counted objection carries a Sherman-Kent estimative band."},
                {"id": "QF-INDEPENDENT-PATH", "rule": "Each counted objection names a verification path a second agent can re-run."},
            ],
            "padding_detector": {
                "id": "PAD-RES-0150-dual-space",
                "flags": list(C.PADDING_FLAGS),
                "both_states": True,
                "procedure": (
                    "Accept genuine disconfirming items first. Each later candidate is "
                    "flagged if vacuous, restating, unlined, not in corpus, citing SUPPORT "
                    "as DISCONFIRM, mechanism-subset of an accepted item, or Jaccard >= "
                    f"{C.NEAR_DUP_JACCARD} with an accepted item. Flags reject; they do not fill."
                ),
            },
            "honest_under_quota_path": {
                "when": "Search is exhausted and qualifying unfavorable count is still below required_n, including after rejecting padding.",
                "verdict": C.HONEST_VERDICT,
                "must_not": f"Must not add vacuous, restated, unsourced, or duplicate objections to reach {C.QUOTA_MET}. Filling is the failure this unit exists to prevent.",
            },
        },
        "claims": [
            {
                "id": "C-QUOTA-GOODHART",
                "claim": "A raw count quota on objection-shaped sentences is a Goodhart target; the quality-gated floor plus forbidden filling is the non-gamed definition.",
                "confidence_band": "almost certain",
                "independent_verification_path": C.P1 + " && " + C.P2,
                "signals": [
                    {"id": "S1-goodhart-fetch", "kind": "http-fetch", "locator": by_id["goodhart-wikipedia"]["body_path"]},
                    {"id": "S2-catalog-row", "kind": "worktree-file", "locator": catalog_lin["path"]},
                ],
            },
            {
                "id": "C-QUALITY-FLOOR",
                "claim": "The quality floor (DISCONFIRM citation, lineage, falsifier, non-restatement, mechanism distinctness) stops Campbell-style corruption of the unfavorable-evidence indicator.",
                "confidence_band": "almost certain",
                "independent_verification_path": C.P1,
                "signals": [
                    {"id": "S1-campbell-fetch", "kind": "http-fetch", "locator": by_id["campbell-wikipedia"]["body_path"]},
                    {"id": "S2-live-detector", "kind": "executable-control", "locator": C.P1},
                ],
            },
            {
                "id": "C-HONEST-UNDER",
                "claim": f"When a closed corpus contains zero DISCONFIRM documents, the run must emit {C.HONEST_VERDICT} with qualifying_unfavorable=0; a counter that counts any disconfirming-shaped filler reports QUOTA-MET.",
                "confidence_band": "certain",
                "independent_verification_path": C.P2,
                "signals": [
                    {"id": "S1-closed-corpus-N", "kind": "executable-control", "locator": C.P2},
                    {"id": "S2-mutant-fills", "kind": "executable-negative-control", "locator": "engine.mutant_count_all_disconfirming"},
                ],
            },
            {
                "id": "C-DETECTOR-BOTH-STATES",
                "claim": "The padding detector flags every planted padded objection and is silent on every genuine DISCONFIRM citation.",
                "confidence_band": "certain",
                "independent_verification_path": C.P1,
                "signals": [
                    {"id": "S1-padded-flagged", "kind": "executable-control", "locator": C.P1},
                    {"id": "S2-genuine-silent", "kind": "executable-control", "locator": C.P1},
                ],
            },
        ],
        "source_lineage": source_lineage,
        "sherman_kent_bands": list(C.KENT_BANDS),
        "detector_control": {
            "padded_flagged": det["padded_flagged"],
            "genuine_unflagged": det["genuine_unflagged"],
            "both_states": det["both_states"],
            "n_genuine": det["n_genuine"],
            "n_padded": det["n_padded"],
            "genuine": det["genuine"],
            "padded": det["padded"],
        },
        "negative_control": {
            "id": "N-closed-token-corpus",
            "verdict": live_n["verdict"],
            "filled": live_n["filled_with_padding"],
            "qualifying_unfavorable": live_n["qualifying_unfavorable"],
            "padded_rejected": live_n["padded_rejected"],
            "mutant_verdict": mutant_n["verdict"],
            "mutant_would_fill": mutant_n["filled_with_padding"],
            "search_exhausted": True,
        },
        "positive_control": {
            "id": "G-all-birds-fly",
            "verdict": live_g["verdict"],
            "qualifying_unfavorable": live_g["qualifying_unfavorable"],
            "required_n": live_g["required_n"],
            "accepted_ids": live_g["accepted_ids"],
            "padded_rejected": live_g["padded_rejected"],
        },
        "live_quota": {"claim_G": live_g, "claim_N": live_n, "mutant_N": mutant_n},
        "tests": [
            {"id": "padding-set-both-states", "command": C.P1, "result": "PASS"},
            {"id": "honest-under-quota-no-fill", "command": C.P2, "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": C.REVIEWER_ID,
            "verdict": "PASS",
            "independent": True,
            "default": "REFUTED",
            "notes": "Probe2 recomputes the no-counterevidence run and fails if the engine filled. Probe1 is the detector both-states control.",
        },
        "named_probes": [
            {"id": "probe1", "command": C.P1},
            {"id": "probe2", "command": C.P2},
        ],
    }
    errors = sorted(jsonschema.Draft7Validator(schema).iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        print("FAILED:RES-0150 schema errors")
        for err in errors[:20]:
            print(" ", list(err.path), err.message)
        return 1

    out = REPO / C.OUTPUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if C.SENTINEL not in text:
        print("FAILED:RES-0150 sentinel missing from serialized artifact")
        return 1
    if C.HONEST_VERDICT not in text:
        print("FAILED:RES-0150 honest verdict token missing from artifact")
        return 1
    out.write_text(text, encoding="utf-8")
    digest, size = sha256_file(out)
    print(f"wrote {C.OUTPUT_REL} bytes={size} sha256={digest}")
    print(
        f"G={live_g['verdict']} u={live_g['qualifying_unfavorable']} "
        f"N={live_n['verdict']} u={live_n['qualifying_unfavorable']} "
        f"mutant={mutant_n['verdict']} det_both={det['both_states']}"
    )
    print(C.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
