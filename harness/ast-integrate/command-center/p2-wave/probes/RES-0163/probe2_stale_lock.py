#!/usr/bin/env python3
"""Probe 2: two-rail claims, capture rehash, crash-without-release negative control."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lib as L  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:RES-0163-probe2 {msg}")
    return 1


def claim_errors(claims: list, index: dict) -> list[str]:
    by_id = L.rail_by_id(index)
    errs: list[str] = []
    if not isinstance(claims, list) or len(claims) < 6:
        return [f"claims too few: {0 if not isinstance(claims, list) else len(claims)}"]
    for claim in claims:
        cid = claim.get("claim_id")
        tier = claim.get("evidence_tier")
        verdict = claim.get("reviewer_verdict")
        band = claim.get("sherman_kent")
        rails = claim.get("rails") or []
        kinds = {r.get("kind") for r in rails if isinstance(r, dict)}
        if not band:
            errs.append(f"{cid}: missing sherman_kent")
        if not claim.get("named_independent_verification_path"):
            errs.append(f"{cid}: missing independent verification path")
        if verdict == "SURVIVES" and tier in {"E1", "E2"}:
            if "structured-api" not in kinds:
                errs.append(f"{cid}: SURVIVES {tier} lacks structured-api {kinds}")
            if len(rails) < 2:
                errs.append(f"{cid}: SURVIVES {tier} has <2 rails")
            if kinds <= {"structured-api"}:
                errs.append(f"{cid}: SURVIVES {tier} only structured-api")
        if verdict == "SURVIVES" and tier in {"E3", "E4"}:
            errs.append(f"{cid}: SURVIVES at {tier}")
        for rail in rails:
            if not isinstance(rail, dict):
                errs.append(f"{cid}: rail not object")
                continue
            if rail.get("http_status") != 200 and tier in {"E1", "E2"}:
                errs.append(f"{cid}/{rail.get('id')}: http {rail.get('http_status')}")
            path = L.REPO / str(rail.get("capture_path") or "")
            if not path.is_file():
                errs.append(f"{cid}/{rail.get('id')}: missing {path}")
                continue
            live = L.sha256_file(path)
            if live != rail.get("sha256"):
                errs.append(
                    f"{cid}/{rail.get('id')}: sha mismatch live={live[:12]} art={str(rail.get('sha256'))[:12]}"
                )
            if not rail.get("local"):
                cap = by_id.get(rail.get("id"))
                if cap and cap.get("sha256") != rail.get("sha256"):
                    errs.append(f"{cid}/{rail.get('id')}: index sha != artifact sha")
            quote = str(rail.get("quote") or "")
            body = path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8", "replace")
            if quote and quote not in body:
                errs.append(f"{cid}/{rail.get('id')}: quote not in capture")
            for k in ("permalink", "fetch_timestamp", "sha256"):
                if rail.get(k) in (None, ""):
                    errs.append(f"{cid}/{rail.get('id')}: missing {k}")
    return errs


def stale_errors(art: dict) -> list[str]:
    errs: list[str] = []
    loc = L.load_local()
    nc = art.get("negative_control") or {}
    if set(nc.get("local_disqualified_ids") or []) != set(loc.get("disqualified_ids") or []):
        errs.append("local_disqualified_ids drift vs live experiment")
    planted = nc.get("planted") or {}
    if planted.get("verdict") != "DISQUALIFIED":
        errs.append("planted not DISQUALIFIED")
    # Both-states: occupancy QUALIFIED, locked-file DISQUALIFIED.
    by_id = {o["id"]: o for o in loc.get("options") or []}
    occ = by_id.get("git-worktree-occupancy") or {}
    locked = by_id.get("git-worktree-locked-file") or {}
    naive = by_id.get("naive-lockfile-no-pid-no-ttl") or {}
    emacs = by_id.get("emacs-style-pid-lock") or {}
    if occ.get("verdict") != "QUALIFIED":
        errs.append("occupancy not QUALIFIED")
    if not (occ.get("measured") or {}).get("unlocked_reclaimed"):
        errs.append("occupancy prune did not reclaim")
    if locked.get("verdict") != "DISQUALIFIED":
        errs.append("locked-file not DISQUALIFIED")
    if not (locked.get("measured") or {}).get("locked_still_present"):
        errs.append("locked-file did not persist after prune")
    if naive.get("verdict") != "DISQUALIFIED":
        errs.append("naive not DISQUALIFIED")
    if emacs.get("verdict") != "QUALIFIED":
        errs.append("emacs-style not QUALIFIED")
    if not (emacs.get("measured") or {}).get("emacs_dead_reclaimable"):
        errs.append("dead pid not reclaimable")
    # Classifier both-states on a story-less option.
    empty = L.LX.classify({"stale_lock_story": "", "stale_mechanisms": []})
    if empty != "DISQUALIFIED":
        errs.append("empty story not DISQUALIFIED")
    fake = L.LX.classify(
        {
            "stale_lock_story": "words only",
            "stale_mechanisms": [],
        }
    )
    if fake != "DISQUALIFIED":
        errs.append("story-without-mechanism not DISQUALIFIED")
    ok = L.LX.classify(
        {
            "stale_lock_story": "kill pid",
            "stale_mechanisms": ["pid_liveness"],
        }
    )
    if ok != "QUALIFIED":
        errs.append("pid_liveness not QUALIFIED")
    for row in art.get("systems") or []:
        if not row.get("no_server"):
            continue
        crash = str(row.get("crash_without_release") or "")
        if len(crash) < 20:
            errs.append(f"{row.get('id')}: crash_without_release too thin")
    return errs


def main() -> int:
    art = L.load_artifact()
    index = L.load_index()
    if str(art.get("state") or "").upper() in L.BLOCKED:
        return fail(f"self-declared {art.get('state')}")
    if L.SENTINEL not in json.dumps(art):
        return fail("sentinel absent")
    claims = art.get("claims") or []
    good = claim_errors(claims, index)
    if good:
        return fail("good claims: " + "; ".join(good[:8]))
    s_errs = stale_errors(art)
    if s_errs:
        return fail("stale control: " + "; ".join(s_errs[:8]))

    mutant = copy.deepcopy(claims)
    target = None
    for claim in mutant:
        if (
            claim.get("reviewer_verdict") == "SURVIVES"
            and claim.get("evidence_tier") == "E2"
            and len(claim.get("rails") or []) >= 2
        ):
            claim["rails"] = claim["rails"][:1]
            target = claim.get("claim_id")
            break
    if not target:
        return fail("no E2 claim to mutate")
    m_errs = claim_errors(mutant, index)
    if not m_errs:
        return fail("one-rail mutant did not fire")

    payload = {
        "probe": "probe2-stale-lock-two-rails",
        "unit_id": "RES-0163",
        "claims": len(claims),
        "mutated_claim": target,
        "mutation_errs": m_errs[:4],
        "disqualified": art["negative_control"]["local_disqualified_ids"],
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "NEGATIVE CONTROL: naive lockfile and git worktree locked file are "
        "DISQUALIFIED (no PID/TTL). Unlocked missing worktree prune QUALIFIED. "
        "Emacs dead-pid lock QUALIFIED. One-rail E2 mutant fires."
    )
    print(f"claims={len(claims)} mutated={target}")
    print("SUCCESS:RES-0163-probe2 two-rail evidence and stale-lock negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
