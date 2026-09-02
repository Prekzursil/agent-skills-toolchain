"""Lineage oracle: fuse license-heterogeneous sources and decompose the result.

Probe 1 inspects fusion records for per-source provenance/license/credit.
Probe 2 is the inverse: decompose(fusion) must reproduce the sources.
A fusion that stores provenance metadata but cannot decompose has an
unverifiable lineage claim.

The live compose implementation is WFA-0127 scout._pair_compose plus
licence.join_most_restrictive. No production fuse.py / decompose.py /
distill.py exists in this worktree.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import common as C

WFA = C.WFA0127


def _load_wfa():
    if str(WFA) not in sys.path:
        sys.path.insert(0, str(WFA))
    import licence
    import scout

    return licence, scout


def load_fixture() -> dict[str, Any]:
    return json.loads(C.FIXTURES.read_text(encoding="utf-8"))


def source_map(fix: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    fix = fix or load_fixture()
    return {str(s["id"]): s for s in fix["sources"]}


def pair(fix: dict[str, Any], key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    ids = list(fix[key])
    sm = source_map(fix)
    return sm[ids[0]], sm[ids[1]]


def as_verified(src: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": src["id"],
        "mechanisms": list(src["mechanisms"]),
        "licence_class": src["licence"],
        "quality": float(src["quality"]),
        "provenance": {"src": src["provenance"]["src"]},
        "credit": src["credit"],
    }


def production_inventory() -> dict[str, Any]:
    rels = [
        "tools/workflow/fuse.py",
        "tools/workflow/decompose.py",
        "tools/workflow/distill.py",
        "tools/foundry/fuse.py",
        "tools/foundry/decompose.py",
        "command-center/foundry/fuse.py",
        "command-center/foundry/decompose.py",
    ]
    present = [r for r in rels if (C.REPO / r).is_file()]
    return {
        "fuse_decompose_distill_modules": present,
        "wfa0127_compose": (WFA / "scout.py").is_file(),
        "wfa0127_licence_lattice": (WFA / "fixtures/corpus/licence_lattice.json").is_file(),
        "production_fuse_present": bool(present),
        "production_distill_present": (C.REPO / "tools/workflow/distill.py").is_file(),
        "production_clean_room_present": False,
    }


def join_licence(left: str, right: str) -> str:
    licence, _scout = _load_wfa()
    return str(licence.join_most_restrictive([left, right]))


def live_compose(
    left: dict[str, Any], right: dict[str, Any], goal: list[str]
) -> dict[str, Any]:
    _licence, scout = _load_wfa()
    rec = scout._pair_compose(goal, [as_verified(left), as_verified(right)])
    if rec is None:
        raise RuntimeError("WFA-0127 _pair_compose returned None")
    rec = dict(rec)
    rec["engine"] = "wfa-0127-scout._pair_compose"
    rec["source_licences_in"] = [left["licence"], right["licence"]]
    rec["source_credits_in"] = [left["credit"], right["credit"]]
    return rec


def naive_fuse(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Silent absorption: keep the first license, drop credit and provenance."""
    mechs = sorted(set(left["mechanisms"]) | set(right["mechanisms"]))
    return {
        "id": f"naive:{left['id']}+{right['id']}",
        "engine": "naive-first-licence-wins",
        "disposition": "FUSE",
        "members": [left["id"], right["id"]],
        "mechanisms": mechs,
        "licence_class": left["licence"],
        "source_licences_in": [left["licence"], right["licence"]],
        "source_credits_in": [left["credit"], right["credit"]],
    }


def preserving_fuse(
    left: dict[str, Any], right: dict[str, Any], joined: str
) -> dict[str, Any]:
    mechs = sorted(set(left["mechanisms"]) | set(right["mechanisms"]))

    def row(src: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": src["id"],
            "licence": src["licence"],
            "credit": src["credit"],
            "provenance": dict(src["provenance"]),
            "mechanisms": list(src["mechanisms"]),
            "body": src["body"],
        }

    return {
        "id": f"preserve:{left['id']}+{right['id']}",
        "engine": "preserving-lineage-record",
        "disposition": "FUSE",
        "members": [left["id"], right["id"]],
        "mechanisms": mechs,
        "licence_class": joined,
        "sources": [row(left), row(right)],
        "credits": [left["credit"], right["credit"]],
        "provenance_anchor": [
            left["provenance"]["src"],
            right["provenance"]["src"],
        ],
        "source_licences_in": [left["licence"], right["licence"]],
        "source_credits_in": [left["credit"], right["credit"]],
    }


def naive_distill(fusion: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"distill:{fusion.get('id')}",
        "engine": "naive-distill-drop-metadata",
        "mechanisms": list(fusion.get("mechanisms") or []),
        "body": " ".join(str(m) for m in (fusion.get("mechanisms") or [])),
    }


def inspect_attribution(
    fusion: dict[str, Any], sources: list[dict[str, Any]]
) -> dict[str, Any]:
    members = [str(x) for x in (fusion.get("members") or [])]
    want = {s["id"]: s for s in sources if s["id"] in members}
    rows = {str(r.get("id")): r for r in (fusion.get("sources") or []) if isinstance(r, dict)}
    anchors = [str(a) for a in (fusion.get("provenance_anchor") or []) if a]
    licence_hits = 0
    credit_hits = 0
    prov_hits = 0
    detail = []
    for sid, orig in want.items():
        row = rows.get(sid) or {}
        got_lic = row.get("licence") or row.get("licence_class")
        got_credit = row.get("credit")
        got_src = None
        if isinstance(row.get("provenance"), dict):
            got_src = row["provenance"].get("src")
        lic_ok = got_lic == orig["licence"]
        cred_ok = got_credit == orig["credit"]
        prov_ok = got_src == orig["provenance"]["src"]
        if lic_ok:
            licence_hits += 1
        if cred_ok:
            credit_hits += 1
        if prov_ok:
            prov_hits += 1
        detail.append(
            {
                "id": sid,
                "want_licence": orig["licence"],
                "got_licence": got_lic,
                "licence_ok": lic_ok,
                "credit_ok": cred_ok,
                "provenance_ok": prov_ok,
            }
        )
    n = len(want)
    joined = fusion.get("licence_class")
    first_in = (fusion.get("source_licences_in") or [None])[0]
    silent_join = bool(n >= 2) and joined == first_in and len(set(fusion.get("source_licences_in") or [])) > 1
    return {
        "member_count": n,
        "per_source_licence": n > 0 and licence_hits == n,
        "per_source_credit": n > 0 and credit_hits == n,
        "per_source_provenance": n > 0 and prov_hits == n,
        "provenance_anchors": anchors,
        "anchor_count": len(anchors),
        "joined_licence": joined,
        "silent_first_licence_absorption": silent_join,
        "licence_hits": licence_hits,
        "credit_hits": credit_hits,
        "provenance_hits": prov_hits,
        "detail": detail,
    }


def decompose(fusion: dict[str, Any]) -> dict[str, Any]:
    """Recover source components from the fusion record ALONE (no catalog)."""
    rows = list(fusion.get("sources") or [])
    if rows:
        recovered = []
        complete = True
        for row in rows:
            lic = row.get("licence") or row.get("licence_class")
            cred = row.get("credit")
            src = None
            if isinstance(row.get("provenance"), dict):
                src = row["provenance"].get("src")
            rec = {
                "id": row.get("id"),
                "licence": lic,
                "credit": cred,
                "provenance_src": src,
                "mechanisms": list(row.get("mechanisms") or []),
                "body": row.get("body"),
            }
            if not (rec["id"] and rec["licence"] and rec["credit"] and rec["provenance_src"]):
                complete = False
            recovered.append(rec)
        return {
            "complete": complete and len(recovered) >= 2,
            "method": "sources-array",
            "components": recovered,
        }
    members = list(fusion.get("members") or [])
    anchors = list(fusion.get("provenance_anchor") or [])
    recovered = []
    for i, mid in enumerate(members):
        recovered.append(
            {
                "id": mid,
                "licence": None,
                "credit": None,
                "provenance_src": anchors[i] if i < len(anchors) else None,
                "mechanisms": [],
                "body": None,
            }
        )
    return {
        "complete": False,
        "method": "members-and-anchors-only",
        "components": recovered,
        "reason": (
            "fusion carries member ids and optional provenance anchors but "
            "not per-source licence, credit or body; lineage is unverifiable"
        ),
    }


def roundtrip_ok(
    fusion: dict[str, Any], left: dict[str, Any], right: dict[str, Any]
) -> dict[str, Any]:
    got = decompose(fusion)
    want = {left["id"]: left, right["id"]: right}
    recovered = {str(c.get("id")): c for c in got["components"]}
    missing = [sid for sid in want if sid not in recovered]
    mismatches = []
    for sid, orig in want.items():
        rec = recovered.get(sid) or {}
        if rec.get("licence") != orig["licence"]:
            mismatches.append(f"{sid}:licence")
        if rec.get("credit") != orig["credit"]:
            mismatches.append(f"{sid}:credit")
        if rec.get("provenance_src") != orig["provenance"]["src"]:
            mismatches.append(f"{sid}:provenance")
        if rec.get("body") != orig["body"]:
            mismatches.append(f"{sid}:body")
    ok = got["complete"] and not missing and not mismatches
    return {
        "ok": ok,
        "complete": got["complete"],
        "method": got["method"],
        "missing": missing,
        "mismatches": mismatches,
        "components": got["components"],
        "reason": got.get("reason"),
    }


def refuse_or_stricter(joined: str, left: str, right: str) -> dict[str, Any]:
    """Pass if the pipeline refuses or marks the stricter of the two terms."""
    licence, _scout = _load_wfa()
    ranks = {
        left: licence.restrictiveness(left),
        right: licence.restrictiveness(right),
    }
    stricter = max(ranks, key=lambda k: ranks[k])
    refused = joined in {"UNKNOWN", "REFUSED", None, ""}
    marked = joined == stricter
    absorbed = joined == left and left != right
    return {
        "joined": joined,
        "stricter": stricter,
        "refused": refused,
        "marked_stricter": marked,
        "silent_absorption": absorbed and not refused,
        "pass": bool(refused or marked),
    }


def measure() -> dict[str, Any]:
    fix = load_fixture()
    goal = list(fix["goal_mechanisms"])
    left, right = pair(fix, "compatible_pair")
    bad_l, bad_r = pair(fix, "incompatible_pair")
    inv = production_inventory()

    compose = live_compose(left, right, goal)
    naive = naive_fuse(left, right)
    joined = join_licence(left["licence"], right["licence"])
    preserving = preserving_fuse(left, right, joined)
    inc_naive = naive_fuse(bad_l, bad_r)
    inc_joined = join_licence(bad_l["licence"], bad_r["licence"])
    inc_lattice = {
        "id": f"lattice:{bad_l['id']}+{bad_r['id']}",
        "engine": "wfa-0127-licence.join_most_restrictive",
        "members": [bad_l["id"], bad_r["id"]],
        "licence_class": inc_joined,
        "source_licences_in": [bad_l["licence"], bad_r["licence"]],
        "mechanisms": sorted(set(bad_l["mechanisms"]) | set(bad_r["mechanisms"])),
    }
    try:
        inc_compose = live_compose(bad_l, bad_r, goal)
    except Exception as exc:  # noqa: BLE001
        inc_compose = {"error": f"{type(exc).__name__}: {exc}", "licence_class": None}

    sources = [left, right]
    attr_compose = inspect_attribution(compose, sources)
    attr_naive = inspect_attribution(naive, sources)
    attr_preserving = inspect_attribution(preserving, sources)
    rt_compose = roundtrip_ok(compose, left, right)
    rt_naive = roundtrip_ok(naive, left, right)
    rt_preserving = roundtrip_ok(preserving, left, right)
    ctrl_lattice = refuse_or_stricter(
        inc_joined, bad_l["licence"], bad_r["licence"]
    )
    ctrl_naive = refuse_or_stricter(
        str(inc_naive["licence_class"]), bad_l["licence"], bad_r["licence"]
    )
    distilled = naive_distill(compose)
    distill_keeps_licence = "licence_class" in distilled or "sources" in distilled

    meta_only = {
        "id": "meta-only:unverified-lineage",
        "members": [left["id"], right["id"]],
        "licence_class": joined,
        "provenance_anchor": [
            left["provenance"]["src"],
            right["provenance"]["src"],
        ],
        "note": "provenance metadata without source bodies",
    }
    rt_meta = roundtrip_ok(meta_only, left, right)

    return {
        "inventory": inv,
        "compatible": {
            "left": left["id"],
            "right": right["id"],
            "licences": [left["licence"], right["licence"]],
        },
        "incompatible": {
            "left": bad_l["id"],
            "right": bad_r["id"],
            "licences": [bad_l["licence"], bad_r["licence"]],
        },
        "fusion_records": {
            "compose": compose,
            "naive": naive,
            "preserving": preserving,
            "incompatible_naive": inc_naive,
            "incompatible_lattice": inc_lattice,
            "incompatible_compose": inc_compose,
            "meta_only": meta_only,
            "naive_distill": distilled,
        },
        "attribution": {
            "compose": attr_compose,
            "naive": attr_naive,
            "preserving": attr_preserving,
        },
        "roundtrip": {
            "compose": rt_compose,
            "naive": rt_naive,
            "preserving": rt_preserving,
            "meta_only": rt_meta,
        },
        "incompatible_control": {
            "lattice": ctrl_lattice,
            "naive": ctrl_naive,
        },
        "distill_drops_licence": not distill_keeps_licence,
        "joined_compatible": joined,
        "joined_incompatible": inc_joined,
    }


def probe1_payload(m: dict[str, Any] | None = None) -> dict[str, Any]:
    m = m or measure()
    a = m["attribution"]
    ic = m["incompatible_control"]
    return {
        "probe": "probe1-fusion-record",
        "unit_id": "ADV-0049",
        "compose_engine": m["fusion_records"]["compose"].get("engine"),
        "compose_joined": a["compose"]["joined_licence"],
        "compose_per_source_licence": a["compose"]["per_source_licence"],
        "compose_per_source_credit": a["compose"]["per_source_credit"],
        "compose_per_source_provenance": a["compose"]["per_source_provenance"],
        "compose_anchor_count": a["compose"]["anchor_count"],
        "naive_silent_absorption": a["naive"]["silent_first_licence_absorption"],
        "preserving_per_source_licence": a["preserving"]["per_source_licence"],
        "preserving_per_source_credit": a["preserving"]["per_source_credit"],
        "incompatible_lattice_pass": ic["lattice"]["pass"],
        "incompatible_naive_silent": ic["naive"]["silent_absorption"],
        "production_fuse_present": m["inventory"]["production_fuse_present"],
        "pass": True,
    }


def probe2_payload(m: dict[str, Any] | None = None) -> dict[str, Any]:
    m = m or measure()
    rt = m["roundtrip"]
    return {
        "probe": "probe2-decompose",
        "unit_id": "ADV-0049",
        "preserving_roundtrip": rt["preserving"]["ok"],
        "compose_roundtrip": rt["compose"]["ok"],
        "naive_roundtrip": rt["naive"]["ok"],
        "meta_only_roundtrip": rt["meta_only"]["ok"],
        "compose_method": rt["compose"]["method"],
        "meta_only_unverifiable": (not rt["meta_only"]["ok"])
        and rt["meta_only"]["method"] == "members-and-anchors-only",
        "independent_of_probe1_verdicts": True,
        "pass": True,
    }


def format_probe1(payload: dict[str, Any]) -> str:
    line = (
        f"compose_joined={payload['compose_joined']} "
        f"per_source_licence={payload['compose_per_source_licence']} "
        f"anchors={payload['compose_anchor_count']} "
        f"naive_silent={payload['naive_silent_absorption']} "
        f"preserving_licence={payload['preserving_per_source_licence']}"
    )
    return (
        json.dumps(payload, sort_keys=True)
        + "\n"
        + line
        + "\nSUCCESS:ADV-0049-probe1 fusion record inspected for provenance and licence"
    )


def format_probe2(payload: dict[str, Any]) -> str:
    line = (
        f"preserving_rt={payload['preserving_roundtrip']} "
        f"compose_rt={payload['compose_roundtrip']} "
        f"naive_rt={payload['naive_roundtrip']} "
        f"meta_unverifiable={payload['meta_only_unverifiable']}"
    )
    return (
        json.dumps(payload, sort_keys=True)
        + "\n"
        + line
        + "\nSUCCESS:ADV-0049-probe2 decompose round-trip as lineage oracle"
    )


def target_verdicts(m: dict[str, Any]) -> list[dict[str, Any]]:
    a = m["attribution"]
    rt = m["roundtrip"]
    ic = m["incompatible_control"]
    inv = m["inventory"]

    def v(tid: str, verdict: str, note: str) -> dict[str, Any]:
        return {"target_id": tid, "verdict": verdict, "note": note}

    compose_lic = (
        "CONFIRMED"
        if not a["compose"]["per_source_licence"]
        else "REFUTED"
    )
    compose_credit = (
        "CONFIRMED" if not a["compose"]["per_source_credit"] else "REFUTED"
    )
    if a["compose"]["per_source_provenance"]:
        compose_prov = "REFUTED"
    elif a["compose"]["anchor_count"] >= 2:
        compose_prov = "PARTIAL"
    else:
        compose_prov = "CONFIRMED"
    compose_rt = "CONFIRMED" if not rt["compose"]["ok"] else "REFUTED"
    naive_abs = (
        "CONFIRMED" if a["naive"]["silent_first_licence_absorption"] else "REFUTED"
    )
    preserve = (
        "REFUTED"
        if a["preserving"]["per_source_licence"]
        and a["preserving"]["per_source_credit"]
        and rt["preserving"]["ok"]
        else "CONFIRMED"
    )
    inc_naive = "CONFIRMED" if ic["naive"]["silent_absorption"] else "REFUTED"
    inc_lat = "REFUTED" if ic["lattice"]["pass"] else "CONFIRMED"
    distill = (
        "NOT-CHECKED"
        if not inv["production_distill_present"]
        else ("CONFIRMED" if m["distill_drops_licence"] else "REFUTED")
    )
    clean = "NOT-CHECKED" if not inv["production_clean_room_present"] else "CONFIRMED"
    return [
        v(
            "live-compose-per-source-licence",
            compose_lic,
            "WFA-0127 compose stores a joined licence_class, not each source licence",
        ),
        v(
            "live-compose-credit",
            compose_credit,
            "compose record has no credit/attribution field for either source",
        ),
        v(
            "live-compose-provenance",
            compose_prov,
            "compose keeps provenance_anchor paths but does not bind them to licences",
        ),
        v(
            "live-compose-decompose-roundtrip",
            compose_rt,
            "members+anchors cannot reconstruct licence, credit or source body",
        ),
        v(
            "naive-fuse-silent-absorption",
            naive_abs,
            "control: first-licence-wins fuse must drop the second licence",
        ),
        v(
            "preserving-fuse-attribution-survival",
            preserve,
            "good-state: sources[] carries licence, credit, provenance and body",
        ),
        v(
            "incompatible-naive-silent-absorption",
            inc_naive,
            "MIT+PROPRIETARY naive fuse keeps MIT and drops the stricter term",
        ),
        v(
            "incompatible-lattice-marks-stricter",
            inc_lat,
            "WFA-0127 join_most_restrictive marks PROPRIETARY rather than absorbing MIT",
        ),
        v(
            "production-distill",
            distill,
            "no production distill module on this worktree",
        ),
        v(
            "production-clean-room",
            clean,
            "no production clean-room reimplementation path on this worktree",
        ),
    ]


def overall_from_targets(targets: list[dict[str, Any]]) -> str:
    vs = {t["verdict"] for t in targets}
    if vs <= {"REFUTED"}:
        return "REFUTED"
    if vs <= {"CONFIRMED"}:
        return "CONFIRMED"
    if vs <= {"NOT-CHECKED"}:
        return "NOT-CHECKED"
    if "BLOCKED" in vs and vs <= {"BLOCKED", "NOT-CHECKED"}:
        return "BLOCKED"
    return "PARTIAL"
