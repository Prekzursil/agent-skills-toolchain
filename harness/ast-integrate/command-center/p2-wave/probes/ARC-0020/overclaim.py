"""Overclaim check for the A3 marketplace threat model.

REFUTED rows must name DESIGN vs SENTENCE. Attack classes that are kept
must cite dated prior art AND a concrete design path; threats without a
path must live in dropped_threats, not in attack_classes.
"""
from __future__ import annotations

from typing import Any

LOCUS = frozenset({"DESIGN", "SENTENCE"})
VERDICTS = frozenset({"REFUTED", "CONFIRMED", "PARTIAL", "NOT-CHECKED"})
REQUIRED_CLASSES = frozenset(
    {
        "malicious-or-over-permissioned",
        "typosquat",
        "signature-stripped",
        "dependency-confusion",
        "stale-revocation",
    }
)


def check_overclaim(doc: dict[str, Any]) -> tuple[bool, str]:
    claims = doc.get("claims")
    if not isinstance(claims, list) or len(claims) < 3:
        return False, "claims-missing-or-short"
    refuted = 0
    confirmed = 0
    loci: set[str] = set()
    for i, row in enumerate(claims):
        if not isinstance(row, dict):
            return False, f"claims[{i}]-not-object"
        verdict = str(row.get("verdict") or "")
        if verdict not in VERDICTS:
            return False, f"claims[{i}]-bad-verdict:{verdict}"
        if verdict == "REFUTED":
            refuted += 1
            locus = str(row.get("defect_locus") or "")
            if locus not in LOCUS:
                return False, f"claims[{i}]-REFUTED-missing-defect_locus"
            if not str(row.get("claim") or "").strip():
                return False, f"claims[{i}]-empty-claim"
            if not str(row.get("scoped_restatement") or "").strip():
                return False, f"claims[{i}]-REFUTED-missing-scoped_restatement"
            loci.add(locus)
        elif verdict == "CONFIRMED":
            confirmed += 1
    if refuted < 1:
        return False, "no-REFUTED-claim"
    if confirmed < 1:
        return False, "no-CONFIRMED-claim"
    if "DESIGN" not in loci or "SENTENCE" not in loci:
        return False, f"REFUTED-loci-incomplete:{sorted(loci)}"

    pc = doc.get("path_coverage") or {}
    if not isinstance(pc, dict) or pc.get("computed_not_asserted") is not True:
        return False, "path-coverage-not-computed"
    if pc.get("all_execute_paths_cross_choke") is not True:
        return False, "path-coverage-incomplete"
    try:
        n_paths = int(pc["public_path_count"])
        n_sink = int(pc["sink_caller_count"])
    except (KeyError, TypeError, ValueError):
        return False, "path-coverage-counts-missing"
    if n_paths < 2 or n_sink != 1:
        return False, f"path-coverage-counts-bad paths={n_paths} sink={n_sink}"

    nc = doc.get("negative_control") or {}
    if not isinstance(nc, dict):
        return False, "negative-control-missing"
    if nc.get("metadata_ok_signature_bad_refused") is not True:
        return False, "negative-control-not-refused"
    if nc.get("metadata_ok_signature_ok_allowed") is not True:
        return False, "positive-control-not-allowed"

    classes = doc.get("attack_classes") or []
    if not isinstance(classes, list) or len(classes) < 5:
        return False, "attack-classes-short"
    seen: set[str] = set()
    for i, row in enumerate(classes):
        if not isinstance(row, dict):
            return False, f"attack_classes[{i}]-not-object"
        cid = str(row.get("id") or "")
        seen.add(cid)
        art = row.get("prior_art") or {}
        if not isinstance(art, dict):
            return False, f"attack_classes[{i}]-prior-art-missing"
        if not str(art.get("dated") or "").strip():
            return False, f"attack_classes[{i}]-prior-art-undated"
        url = str(art.get("url") or "")
        if not url.startswith("https://"):
            return False, f"attack_classes[{i}]-prior-art-url"
        path = row.get("design_path") or {}
        if not isinstance(path, dict):
            return False, f"attack_classes[{i}]-design-path-missing"
        if not str(path.get("path") or "").strip() or not str(path.get("snippet") or "").strip():
            return False, f"attack_classes[{i}]-design-path-empty"
    missing = REQUIRED_CLASSES - seen
    if missing:
        return False, f"attack-classes-missing:{sorted(missing)}"

    dropped = doc.get("dropped_threats") or []
    if not isinstance(dropped, list) or len(dropped) < 1:
        return False, "dropped-threats-missing"
    for i, row in enumerate(dropped):
        if not isinstance(row, dict):
            return False, f"dropped_threats[{i}]-not-object"
        if not str(row.get("why_no_design_path") or "").strip():
            return False, f"dropped_threats[{i}]-missing-why"

    upstream = doc.get("upstream_design") or {}
    if not isinstance(upstream, dict):
        return False, "upstream-design-missing"
    if upstream.get("present") is True:
        return False, "claimed-A3-DESIGN-present"
    if "A3/DESIGN.json" in str(upstream.get("stand_in") or ""):
        return False, "stand-in-is-missing-DESIGN"

    if doc.get("adv_rebuild_circle") is True:
        return False, "adv-rebuild-circle"
    return True, f"refuted={refuted} confirmed={confirmed} classes={len(seen)}"
