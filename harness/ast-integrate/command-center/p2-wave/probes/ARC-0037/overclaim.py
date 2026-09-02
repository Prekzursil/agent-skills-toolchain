"""Overclaim check for ARC-0037.

Every REFUTED claim names DESIGN vs SENTENCE and a scoped restatement.
Both loci must appear. The pre-flight must be an executable predicate,
and local-unsafe must be distinct from anywhere-unsafe.
"""
from __future__ import annotations

from typing import Any

LOCUS = frozenset({"DESIGN", "SENTENCE"})
VERDICTS = frozenset({"REFUTED", "CONFIRMED", "PARTIAL", "NOT-CHECKED"})


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

    pred = doc.get("preflight_predicate") or {}
    if not isinstance(pred, dict):
        return False, "preflight-missing"
    if not str(pred.get("executable") or "").strip():
        return False, "preflight-not-executable"
    if pred.get("actionable") is not True:
        return False, "preflight-not-actionable"

    scope = doc.get("scope") or {}
    if not isinstance(scope, dict):
        return False, "scope-missing"
    if scope.get("unsafe_locally") is not True:
        return False, "scope-unsafe-locally-not-true"
    if scope.get("unsafe_anywhere") is not False:
        return False, "scope-collapsed-to-anywhere"
    if not str(scope.get("cloud_only_is_different_finding") or "").strip():
        return False, "scope-cloud-finding-missing"

    ceil = doc.get("resource_ceiling") or {}
    if not isinstance(ceil, dict):
        return False, "ceiling-missing"
    try:
        nproc = int(ceil["max_concurrent_processes"])
        nbytes = int(ceil["max_committed_bytes"])
    except (KeyError, TypeError, ValueError):
        return False, "ceiling-not-numeric"
    if nproc < 1 or nbytes < 1:
        return False, "ceiling-nonpositive"

    blast = doc.get("process_blast") or {}
    if not isinstance(blast, dict) or blast.get("computed_not_asserted") is not True:
        return False, "process-blast-not-computed"
    try:
        sessions = int(blast["estate_sessions"])
        servers = int(blast["estate_servers_per_session"])
        procs = int(blast["estate_processes"])
    except (KeyError, TypeError, ValueError):
        return False, "process-blast-counts-missing"
    if sessions * servers != procs:
        return False, "process-blast-arithmetic-wrong"
    return True, f"refuted={refuted} confirmed={confirmed}"
