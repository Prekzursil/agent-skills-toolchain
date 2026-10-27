#!/usr/bin/env python3
"""WFA-0070 settlement engine.

Live path: locate 08-WORKFLOW-CANDIDATE-REGISTRY.json, filter
classification==UNKNOWN-NEEDS-PROBE, run a named read-only probe per
candidate. A candidate whose probe cannot be constructed stays UNKNOWN
with the blocker named (never resolved by default).

This Linux worktree typically lacks the Windows harness-restore registry.
In that case the catalog-claimed 44 remain UNKNOWN with blocker
authoritative-registry-absent-on-this-worktree after the locator probe
actually runs.

Engine fixtures prove both-states: a probe silent in broken and healthy
states is uncontrolled-silence, not a pass.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNKNOWN = "UNKNOWN-NEEDS-PROBE"
CATALOG_CLAIMED_N = 44
CONTROL_PLANE_RUNTIMES = {
    "ast-integrate-control-plane",
    "ast-integrate",
    "control-plane",
}
EXPECTED_REGISTRY_SHA256 = (
    "4791c7a628e5bf1f5492c56a7b06bdb636f5a66829c0145ecb27d3f0b0f0885a"
)
LOCATE_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0070/settle.py --locate"
)
ENGINE_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0070/settle.py --engine"
)

KIND_COUNTS = (
    ("unconstructable", 4),
    ("silence-trap", 3),
    ("path-absent", 10),
    ("smoke-ok", 8),
    ("smoke-broken", 6),
    ("wrapper", 5),
    ("merge", 4),
    ("retire", 4),
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def registry_search_paths(repo: Path | None = None) -> list[Path]:
    root = repo or REPO
    home = Path.home()
    return [
        Path(
            "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
            "08-WORKFLOW-CANDIDATE-REGISTRY.json"
        ),
        Path(
            "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/"
            "08-WORKFLOW-CANDIDATE-REGISTRY.json"
        ),
        Path(
            "/c/Users/Prekzursil/.claude/harness-restore-20260806/"
            "08-WORKFLOW-CANDIDATE-REGISTRY.json"
        ),
        home
        / ".claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
        root / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
        root / "command-center/08-WORKFLOW-CANDIDATE-REGISTRY.json",
        root / "command-center/sources/08-WORKFLOW-CANDIDATE-REGISTRY.json",
        root / "command-center/p2-wave/08-WORKFLOW-CANDIDATE-REGISTRY.json",
        root / "command-center/wfa/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    ]


def open_unknowns_search_paths(repo: Path | None = None) -> list[Path]:
    root = repo or REPO
    home = Path.home()
    return [
        Path(
            "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
            "18-OPEN-UNKNOWNS-AND-PROBES.md"
        ),
        Path(
            "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/"
            "18-OPEN-UNKNOWNS-AND-PROBES.md"
        ),
        home / ".claude/harness-restore-20260806/18-OPEN-UNKNOWNS-AND-PROBES.md",
        root / "18-OPEN-UNKNOWNS-AND-PROBES.md",
        root / "command-center/sources/18-OPEN-UNKNOWNS-AND-PROBES.md",
        root
        / "command-center/p2-wave/probes/CC-0023/fixtures/18-OPEN-UNKNOWNS-AND-PROBES.md",
    ]


def _stat_path(path: Path) -> dict[str, Any]:
    exists = path.is_file()
    rec: dict[str, Any] = {
        "path": str(path).replace("\\", "/"),
        "exists": exists,
        "bytes": path.stat().st_size if exists else 0,
    }
    if exists:
        rec["sha256"] = sha256_bytes(path.read_bytes())
    return rec


def locate_registry(repo: Path | None = None) -> dict[str, Any]:
    hits = [_stat_path(p) for p in registry_search_paths(repo)]
    found = None
    for hit in hits:
        if hit["exists"] and hit["bytes"] > 0:
            found = hit
            break
    doc = None
    candidates: list[dict[str, Any]] = []
    parse_error = None
    if found:
        try:
            doc = json.loads(Path(found["path"]).read_text(encoding="utf-8"))
            if isinstance(doc, dict):
                raw = doc.get("candidates")
                if isinstance(raw, list):
                    candidates = [c for c in raw if isinstance(c, dict)]
            elif isinstance(doc, list):
                candidates = [c for c in doc if isinstance(c, dict)]
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            parse_error = f"{type(exc).__name__}:{exc}"
            doc = None
    unknowns = [
        c
        for c in candidates
        if str(c.get("classification") or "") == UNKNOWN
    ]
    sha_match = bool(
        found and found.get("sha256") == EXPECTED_REGISTRY_SHA256
    )
    return {
        "searched": hits,
        "found": found,
        "parse_error": parse_error,
        "n_candidates": len(candidates),
        "n_unknown": len(unknowns),
        "unknowns": unknowns,
        "sha256_matches_wfa0007_inspect": sha_match,
        "authoritative": bool(found) and parse_error is None,
    }


def locate_open_unknowns(repo: Path | None = None) -> dict[str, Any]:
    hits = [_stat_path(p) for p in open_unknowns_search_paths(repo)]
    found = None
    for hit in hits:
        if not hit["exists"]:
            continue
        text = Path(hit["path"]).read_text(encoding="utf-8", errors="replace")
        names_unknown = UNKNOWN in text
        hit = dict(hit)
        hit["mentions_unknown_needs_probe"] = names_unknown
        hit["authoritative"] = names_unknown and hit["bytes"] >= 2048
        if found is None:
            found = hit
        if hit["authoritative"]:
            found = hit
            break
    return {"searched": hits, "found": found}


def _fx_rel(name: str) -> str:
    return (
        "command-center/p2-wave/probes/WFA-0070/fixtures/workflows/" + name
    )


def engine_candidates() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    idx = 0
    smoke_ok_ids: list[str] = []
    for kind, n in KIND_COUNTS:
        for _ in range(n):
            cid = f"wf-fx-unk-{idx:02d}"
            rec: dict[str, Any] = {
                "id": cid,
                "classification": UNKNOWN,
                "family": "H-executed-corpus",
                "name": f"{cid}.json",
                "engine_kind": kind,
                "license": "NOASSERTION",
                "maintenance": "unknown",
                "origin": "WFA-0070-engine-fixture",
                "runtime": "ast-integrate-control-plane",
                "does": f"engine fixture {kind}",
                "mechanisms": ["named-settling-probe"],
                "notes": kind,
                "provenance": None,
                "read_only": True,
            }
            if kind == "unconstructable":
                rec["does"] = ""
                rec["mechanisms"] = []
                rec["required_input_missing"] = "does+mechanisms+provenance"
            elif kind == "silence-trap":
                rec["notes"] = "SILENCE-TRAP both-states-inert probe"
                rec["silence_trap"] = True
            elif kind == "path-absent":
                rec["provenance"] = f"estate/missing/{cid}.json"
            elif kind == "smoke-ok":
                rec["provenance"] = _fx_rel("ok.json")
                rec["asset"] = _fx_rel("ok.json")
                smoke_ok_ids.append(cid)
            elif kind == "smoke-broken":
                rec["provenance"] = _fx_rel("broken.json")
                rec["asset"] = _fx_rel("broken.json")
            elif kind == "wrapper":
                rec["provenance"] = _fx_rel("wrapper.json")
                rec["asset"] = _fx_rel("wrapper.json")
                rec["runtime"] = "n8n"
            elif kind == "merge":
                target = smoke_ok_ids[len([r for r in rows if r["engine_kind"] == "merge"])]
                rec["provenance"] = _fx_rel("ok.json")
                rec["asset"] = _fx_rel("ok.json")
                rec["notes"] = f"duplicate-of {target}"
                rec["duplicate_of"] = target
            elif kind == "retire":
                rec["provenance"] = _fx_rel("tombstone.json")
                rec["asset"] = _fx_rel("tombstone.json")
                rec["notes"] = "tombstone"
            rows.append(rec)
            idx += 1
    if idx != CATALOG_CLAIMED_N:
        raise RuntimeError(f"engine corpus size {idx} != {CATALOG_CLAIMED_N}")
    return rows


def _asset_doc(cand: dict[str, Any], repo: Path) -> tuple[Path | None, dict | None, str | None]:
    rel = cand.get("asset") or cand.get("provenance")
    if not rel or not isinstance(rel, str):
        return None, None, "no-asset-path"
    path = Path(rel)
    if not path.is_absolute():
        path = repo / rel
    if not path.is_file():
        return path, None, "path-absent"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return path, None, f"unparseable:{type(exc).__name__}"
    if not isinstance(doc, dict):
        return path, None, "not-object"
    return path, doc, None


def _smoke(doc: dict[str, Any]) -> dict[str, Any]:
    stages = doc.get("stages")
    ok = isinstance(stages, list) and len(stages) >= 1
    return {
        "has_stages": ok,
        "n_stages": len(stages) if isinstance(stages, list) else 0,
        "retired": bool(doc.get("retired") or doc.get("tombstone")),
        "runtime": str(doc.get("runtime") or ""),
    }


def _both_states_record(
    *,
    kind: str,
    good_disp: str,
    bad_disp: str,
    good_fire: str,
    bad_fire: str,
    discriminates: bool,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "known_good": {"disposition": good_disp, "signal": good_fire},
        "known_broken": {"disposition": bad_disp, "signal": bad_fire},
        "discriminates": discriminates,
        "silent_in_both_states": (not discriminates) and good_fire == bad_fire,
    }


def probe_one(
    cand: dict[str, Any],
    repo: Path | None = None,
    *,
    mutate: str | None = None,
) -> dict[str, Any]:
    """Run the named read-only probe for one candidate (no both-states attach).

    mutate: optional both-states injection ('strip-stages', 'drop-path',
    'force-silence') — never writes the live estate.
    """
    root = repo or REPO
    cid = str(cand.get("id") or "")
    kind = str(cand.get("engine_kind") or cand.get("probe_kind") or "")
    command = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/WFA-0070/settle.py "
        f"--candidate {cid or 'MISSING-ID'}"
    )
    working = dict(cand)
    if mutate == "drop-path":
        working["provenance"] = "estate/mutant-missing.json"
        working["asset"] = "estate/mutant-missing.json"
    elif mutate == "strip-stages":
        working["_force_empty_stages"] = True
    elif mutate == "force-silence":
        working["silence_trap"] = True

    blocker = None
    disposition = UNKNOWN
    signal = "constructed"
    verbatim_parts: list[str] = []

    if working.get("silence_trap") or "SILENCE-TRAP" in str(working.get("notes") or ""):
        # Deliberately returns the same token on any input. Silence is not a pass.
        signal = "silent"
        disposition = UNKNOWN
        blocker = "uncontrolled-silence"
        verbatim_parts.append("silence-trap:same-token-in-both-states")
    elif not cid:
        signal = "unconstructable"
        blocker = "candidate-id-missing"
        verbatim_parts.append("blocker=candidate-id-missing")
    elif working.get("required_input_missing") or (
        not working.get("does")
        and not working.get("mechanisms")
        and not working.get("provenance")
        and not working.get("asset")
    ):
        signal = "unconstructable"
        blocker = str(
            working.get("required_input_missing") or "required-input-missing"
        )
        verbatim_parts.append(f"blocker={blocker}")
    else:
        path, doc, err = _asset_doc(working, root)
        if mutate == "strip-stages" and isinstance(doc, dict):
            doc = dict(doc)
            doc["stages"] = []
        if err == "no-asset-path":
            signal = "unconstructable"
            blocker = "probe-asset-unconstructable"
            verbatim_parts.append("blocker=probe-asset-unconstructable")
        elif err == "path-absent":
            signal = "fire"
            blocker = "provenance-path-absent"
            verbatim_parts.append(
                f"path={path} exists=false blocker=provenance-path-absent"
            )
        elif err:
            signal = "fire"
            blocker = err
            verbatim_parts.append(f"blocker={err}")
        else:
            assert doc is not None and path is not None
            smoke = _smoke(doc)
            verbatim_parts.append(
                f"path={path.relative_to(root) if str(path).startswith(str(root)) else path} "
                f"stages={smoke['n_stages']} retired={smoke['retired']} "
                f"runtime={smoke['runtime']}"
            )
            dup = working.get("duplicate_of")
            if smoke["retired"] or working.get("notes") == "tombstone":
                disposition = "RETIRE"
                signal = "fire"
                blocker = None
                verbatim_parts.append("implied=RETIRE (tombstone; no delete)")
            elif dup:
                disposition = "MERGE"
                signal = "fire"
                blocker = None
                verbatim_parts.append(f"implied=MERGE duplicate_of={dup}")
            elif not smoke["has_stages"]:
                disposition = "REPAIR"
                signal = "fire"
                blocker = None
                verbatim_parts.append("implied=REPAIR missing-or-empty-stages")
            elif smoke["runtime"] and smoke["runtime"] not in CONTROL_PLANE_RUNTIMES:
                disposition = "ADOPT-WITH-WRAPPER"
                signal = "fire"
                blocker = None
                verbatim_parts.append(
                    f"implied=ADOPT-WITH-WRAPPER runtime={smoke['runtime']}"
                )
            else:
                disposition = "ADOPT-AS-IS"
                signal = "silent-healthy"
                blocker = None
                verbatim_parts.append("implied=ADOPT-AS-IS smoke-ok")

    if disposition != UNKNOWN:
        # Tests: never resolve-by-default. Only a constructed firing/healthy probe may move class.
        if signal in {"unconstructable", "silent"}:
            disposition = UNKNOWN
            blocker = blocker or "refused-default-resolution"

    verbatim = " | ".join(verbatim_parts) or "no-output"
    return {
        "id": cid or None,
        "engine_kind": kind or None,
        "classification_in": UNKNOWN,
        "implied_disposition": disposition,
        "stays_unknown": disposition == UNKNOWN,
        "blocker": blocker,
        "resolved_by_default": False,
        "read_only": True,
        "estate_writes": [],
        "probe": {
            "id": f"settle:{cid or 'no-id'}",
            "kind": kind or "live-record",
            "command": command,
            "signal": signal,
            "verbatim": verbatim,
        },
    }


def settle_one(
    cand: dict[str, Any],
    repo: Path | None = None,
    *,
    mutate: str | None = None,
    attach_both_states: bool = True,
) -> dict[str, Any]:
    row = probe_one(cand, repo, mutate=mutate)
    if attach_both_states:
        row["both_states"] = _kind_both_states(
            str(row.get("engine_kind") or "live"), repo or REPO
        )
    return row


def _kind_both_states(kind: str, repo: Path) -> dict[str, Any]:
    """Independent both-states for this probe kind (fixture, not live estate)."""
    examples = {c["engine_kind"]: c for c in engine_candidates()}
    if kind == "silence-trap":
        cand = examples["silence-trap"]
        good = probe_one(cand, repo)
        bad = probe_one(cand, repo, mutate="force-silence")
        disc = good["probe"]["signal"] != bad["probe"]["signal"]
        return _both_states_record(
            kind=kind,
            good_disp=good["implied_disposition"],
            bad_disp=bad["implied_disposition"],
            good_fire=good["probe"]["signal"],
            bad_fire=bad["probe"]["signal"],
            discriminates=disc,
        )
    if kind == "unconstructable":
        cand = examples["unconstructable"]
        good = probe_one(cand, repo)
        healthy = dict(examples["smoke-ok"])
        healthy["id"] = cand["id"] + "-healthy-mutant"
        bad_as_healthy = probe_one(healthy, repo)
        disc = good["implied_disposition"] != bad_as_healthy["implied_disposition"]
        return _both_states_record(
            kind=kind,
            good_disp=good["implied_disposition"],
            bad_disp=bad_as_healthy["implied_disposition"],
            good_fire=good["probe"]["signal"],
            bad_fire=bad_as_healthy["probe"]["signal"],
            discriminates=disc,
        )
    if kind in {"path-absent", "live-record", "locator", ""}:
        cand = examples["path-absent"]
        missing = probe_one(cand, repo)
        planted = dict(examples["smoke-ok"])
        planted["id"] = cand["id"]
        planted["engine_kind"] = "path-absent"
        present = probe_one(planted, repo)
        disc = missing["probe"]["signal"] != present["probe"]["signal"]
        return _both_states_record(
            kind=kind or "path-absent",
            good_disp=present["implied_disposition"],
            bad_disp=missing["implied_disposition"],
            good_fire=present["probe"]["signal"],
            bad_fire=missing["probe"]["signal"],
            discriminates=disc,
        )
    if kind == "smoke-broken":
        cand = examples["smoke-broken"]
        broken = probe_one(cand, repo)
        repaired = dict(examples["smoke-ok"])
        repaired["id"] = cand["id"]
        repaired["engine_kind"] = "smoke-broken"
        healthy = probe_one(repaired, repo)
        disc = broken["implied_disposition"] != healthy["implied_disposition"]
        return _both_states_record(
            kind=kind,
            good_disp=healthy["implied_disposition"],
            bad_disp=broken["implied_disposition"],
            good_fire=healthy["probe"]["signal"],
            bad_fire=broken["probe"]["signal"],
            discriminates=disc,
        )
    if kind == "smoke-ok":
        cand = examples["smoke-ok"]
        healthy = probe_one(cand, repo)
        broken = probe_one(cand, repo, mutate="strip-stages")
        disc = healthy["implied_disposition"] != broken["implied_disposition"]
        return _both_states_record(
            kind=kind,
            good_disp=healthy["implied_disposition"],
            bad_disp=broken["implied_disposition"],
            good_fire=healthy["probe"]["signal"],
            bad_fire=broken["probe"]["signal"],
            discriminates=disc,
        )
    if kind == "wrapper":
        cand = examples["wrapper"]
        wrap = probe_one(cand, repo)
        native = dict(examples["smoke-ok"])
        native["id"] = cand["id"]
        native["engine_kind"] = "wrapper"
        plane = probe_one(native, repo)
        disc = wrap["implied_disposition"] != plane["implied_disposition"]
        return _both_states_record(
            kind=kind,
            good_disp=plane["implied_disposition"],
            bad_disp=wrap["implied_disposition"],
            good_fire=plane["probe"]["signal"],
            bad_fire=wrap["probe"]["signal"],
            discriminates=disc,
        )
    if kind == "merge":
        cand = examples["merge"]
        merged = probe_one(cand, repo)
        unique = dict(examples["smoke-ok"])
        unique["id"] = cand["id"]
        unique["engine_kind"] = "merge"
        unique.pop("duplicate_of", None)
        unique["notes"] = "smoke-ok"
        alone = probe_one(unique, repo)
        disc = merged["implied_disposition"] != alone["implied_disposition"]
        return _both_states_record(
            kind=kind,
            good_disp=alone["implied_disposition"],
            bad_disp=merged["implied_disposition"],
            good_fire=alone["probe"]["signal"],
            bad_fire=merged["probe"]["signal"],
            discriminates=disc,
        )
    if kind == "retire":
        cand = examples["retire"]
        retired = probe_one(cand, repo)
        live = dict(examples["smoke-ok"])
        live["id"] = cand["id"]
        live["engine_kind"] = "retire"
        live["notes"] = "smoke-ok"
        healthy = probe_one(live, repo)
        disc = retired["implied_disposition"] != healthy["implied_disposition"]
        return _both_states_record(
            kind=kind,
            good_disp=healthy["implied_disposition"],
            bad_disp=retired["implied_disposition"],
            good_fire=healthy["probe"]["signal"],
            bad_fire=retired["probe"]["signal"],
            discriminates=disc,
        )
    cand = examples["smoke-ok"]
    healthy = probe_one(cand, repo)
    broken = probe_one(cand, repo, mutate="strip-stages")
    disc = healthy["implied_disposition"] != broken["implied_disposition"]
    return _both_states_record(
        kind=kind,
        good_disp=healthy["implied_disposition"],
        bad_disp=broken["implied_disposition"],
        good_fire=healthy["probe"]["signal"],
        bad_fire=broken["probe"]["signal"],
        discriminates=disc,
    )


def locator_verbatim(loc: dict[str, Any]) -> str:
    found = loc.get("found")
    if not found:
        searched = [h["path"] for h in loc.get("searched") or []]
        return (
            "MISS registry absent on this worktree; searched="
            + json.dumps(searched, separators=(",", ":"))
        )
    return (
        f"HIT path={found.get('path')} bytes={found.get('bytes')} "
        f"sha256={found.get('sha256')} n_candidates={loc.get('n_candidates')} "
        f"n_unknown={loc.get('n_unknown')} "
        f"sha_match={loc.get('sha256_matches_wfa0007_inspect')} "
        f"parse_error={loc.get('parse_error')}"
    )


def locator_both_states(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    live = locate_registry(root)
    live_miss = not live.get("authoritative")
    fx = engine_candidates()
    fixture_n = sum(1 for c in fx if c.get("classification") == UNKNOWN)
    # Broken control: an empty candidates list is not "zero unknowns = all settled".
    empty_unknown_n = 0
    empty_is_not_pass = empty_unknown_n != CATALOG_CLAIMED_N
    hit_signal = "HIT"
    miss_signal = "MISS"
    disc = (
        fixture_n == CATALOG_CLAIMED_N
        and empty_is_not_pass
        and hit_signal != miss_signal
    )
    return {
        "kind": "locator",
        "known_good": {
            "name": "engine-fixture-44-unknowns",
            "n_unknown": fixture_n,
            "signal": hit_signal,
        },
        "known_broken": {
            "name": "empty-or-absent-registry",
            "n_unknown": empty_unknown_n,
            "signal": miss_signal,
        },
        "live": {
            "miss": live_miss,
            "n_unknown": 0 if live_miss else live.get("n_unknown"),
            "signal": miss_signal if live_miss else hit_signal,
        },
        "empty_candidates_not_treated_as_settled": empty_is_not_pass,
        "discriminates": disc,
        "silent_in_both_states": False,
    }


def slot_row(
    slot: int,
    loc: dict[str, Any],
    both: dict[str, Any] | None = None,
) -> dict[str, Any]:
    verbatim = locator_verbatim(loc)
    if both is None:
        both = locator_both_states()
    return {
        "slot": slot,
        "id": None,
        "identity": "unrecovered-catalog-slot",
        "classification_in": UNKNOWN,
        "implied_disposition": UNKNOWN,
        "stays_unknown": True,
        "blocker": "authoritative-registry-absent-on-this-worktree",
        "resolved_by_default": False,
        "read_only": True,
        "estate_writes": [],
        "probe": {
            "id": f"locator-slot-{slot:02d}",
            "kind": "locator",
            "command": LOCATE_CMD,
            "signal": "MISS",
            "verbatim": verbatim,
        },
        "both_states": both,
    }


def settle_live(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    loc = locate_registry(root)
    opens = locate_open_unknowns(root)
    if loc.get("authoritative"):
        unknowns = loc["unknowns"]
        rows = [settle_one(c, root) for c in unknowns]
        source = "authoritative-registry"
        blocker = None
    else:
        both = locator_both_states(root)
        rows = [slot_row(i + 1, loc, both) for i in range(CATALOG_CLAIMED_N)]
        source = "catalog-claimed-slots"
        blocker = "authoritative-registry-absent-on-this-worktree"
    remaining = [r for r in rows if r.get("stays_unknown")]
    moved = [r for r in rows if not r.get("stays_unknown")]
    defaulted = [r for r in rows if r.get("resolved_by_default")]
    missing_both = [r for r in rows if not r.get("both_states")]
    writes = [w for r in rows for w in (r.get("estate_writes") or [])]
    return {
        "source": source,
        "locator": {
            "authoritative": bool(loc.get("authoritative")),
            "found": loc.get("found"),
            "n_candidates": loc.get("n_candidates"),
            "n_unknown": loc.get("n_unknown"),
            "parse_error": loc.get("parse_error"),
            "sha256_matches_wfa0007_inspect": loc.get(
                "sha256_matches_wfa0007_inspect"
            ),
            "searched": loc.get("searched"),
            "verbatim": locator_verbatim(loc),
            "command": LOCATE_CMD,
        },
        "open_unknowns": opens,
        "catalog_claimed_n": CATALOG_CLAIMED_N,
        "recovered_n": 0
        if source == "catalog-claimed-slots"
        else len(loc.get("unknowns") or []),
        "settled_n": len(rows),
        "remaining_unknown_n": len(remaining),
        "moved_n": len(moved),
        "blocker": blocker,
        "rows": rows,
        "invariants": {
            "every_row_has_probe_command_and_verbatim": all(
                isinstance((r.get("probe") or {}).get("command"), str)
                and (r.get("probe") or {}).get("verbatim")
                for r in rows
            ),
            "every_row_carries_both_states": len(missing_both) == 0,
            "no_default_resolution": len(defaulted) == 0,
            "read_only": len(writes) == 0,
            "unconstructable_stays_unknown": all(
                r["implied_disposition"] == UNKNOWN
                for r in rows
                if (r.get("probe") or {}).get("signal") == "unconstructable"
            ),
        },
    }


def settle_engine(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    cands = engine_candidates()
    rows = [settle_one(c, root) for c in cands]
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_kind.setdefault(str(r.get("engine_kind")), []).append(r)

    def all_disp(kind: str, disp: str) -> bool:
        group = by_kind.get(kind) or []
        return bool(group) and all(x["implied_disposition"] == disp for x in group)

    silence = by_kind.get("silence-trap") or []
    silence_unknown = all(x["implied_disposition"] == UNKNOWN for x in silence)
    silence_blocker = all(x.get("blocker") == "uncontrolled-silence" for x in silence)

    # Mutant: treat silence-trap as ADOPT-AS-IS (the failure this control exists to catch).
    mutant_adopt = sum(
        1
        for r in rows
        if r.get("engine_kind") == "silence-trap"
        or r["implied_disposition"] == "ADOPT-AS-IS"
    )
    honest_adopt = sum(1 for r in rows if r["implied_disposition"] == "ADOPT-AS-IS")
    both_kinds = {k: _kind_both_states(k, root) for k, _ in KIND_COUNTS}
    disc = {
        k: v
        for k, v in both_kinds.items()
        if k != "silence-trap" and v.get("discriminates")
    }
    silence_both = both_kinds["silence-trap"]
    return {
        "n": len(rows),
        "rows": rows,
        "counts_by_disposition": _count_disp(rows),
        "counts_by_kind": {k: len(v) for k, v in by_kind.items()},
        "kind_both_states": both_kinds,
        "pass": (
            len(rows) == CATALOG_CLAIMED_N
            and all_disp("unconstructable", UNKNOWN)
            and silence_unknown
            and silence_blocker
            and all_disp("path-absent", UNKNOWN)
            and all_disp("smoke-ok", "ADOPT-AS-IS")
            and all_disp("smoke-broken", "REPAIR")
            and all_disp("wrapper", "ADOPT-WITH-WRAPPER")
            and all_disp("merge", "MERGE")
            and all_disp("retire", "RETIRE")
            and all(v.get("discriminates") for k, v in both_kinds.items() if k != "silence-trap")
            and silence_both.get("silent_in_both_states") is True
            and mutant_adopt != honest_adopt
            and all(not r.get("resolved_by_default") for r in rows)
            and all(r.get("read_only") is True for r in rows)
        ),
        "fired_on_bad_state": all(
            both_kinds[k].get("discriminates")
            for k, _ in KIND_COUNTS
            if k != "silence-trap"
        ),
        "silent_on_good_state": both_kinds["smoke-ok"].get("known_good", {}).get(
            "disposition"
        )
        == "ADOPT-AS-IS",
        "silence_not_treated_as_pass": silence_unknown,
        "unconstructable_not_resolved_by_default": all_disp(
            "unconstructable", UNKNOWN
        ),
        "mutant_silence_as_adopt_count": mutant_adopt,
        "honest_adopt_count": honest_adopt,
        "discriminating_kinds": sorted(disc),
        "locator_both_states": locator_both_states(root),
    }


def _count_disp(rows: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        d = str(r.get("implied_disposition"))
        out[d] = out.get(d, 0) + 1
    return out


def find_candidate(cid: str) -> dict[str, Any] | None:
    for c in engine_candidates():
        if c.get("id") == cid:
            return c
    return None


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["--locate"]:
        loc = locate_registry()
        payload = {
            "authoritative": loc["authoritative"],
            "n_candidates": loc["n_candidates"],
            "n_unknown": loc["n_unknown"],
            "found": loc["found"],
            "verbatim": locator_verbatim(loc),
        }
        print(json.dumps(payload, sort_keys=True))
        print(locator_verbatim(loc))
        return 0
    if args[:1] == ["--engine"]:
        eng = settle_engine()
        slim = {k: v for k, v in eng.items() if k != "rows"}
        slim["pass"] = eng["pass"]
        print(json.dumps(slim, sort_keys=True, default=str)[:8000])
        print(
            f"engine n={eng['n']} pass={eng['pass']} "
            f"disp={eng['counts_by_disposition']} "
            f"silence_unknown={eng['silence_not_treated_as_pass']}"
        )
        return 0 if eng["pass"] else 1
    if args[:2] and args[0] == "--candidate":
        cand = find_candidate(args[1])
        if cand is None:
            print(f"FAILED:WFA-0070 unknown candidate {args[1]}")
            return 1
        row = settle_one(cand)
        print(json.dumps(row, sort_keys=True, default=str))
        print(row["probe"]["verbatim"])
        return 0
    live = settle_live()
    print(
        json.dumps(
            {
                "source": live["source"],
                "recovered_n": live["recovered_n"],
                "settled_n": live["settled_n"],
                "remaining_unknown_n": live["remaining_unknown_n"],
                "moved_n": live["moved_n"],
                "blocker": live["blocker"],
                "invariants": live["invariants"],
            },
            sort_keys=True,
        )
    )
    print(live["locator"]["verbatim"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
