#!/usr/bin/env python3
"""Runtime-string partition vs second-control-plane guard, then TRANSLATE."""
from __future__ import annotations

from collections import Counter, defaultdict

from plane import (
    ADOPT_CLASSES,
    LEGITIMATE_LIBS,
    TORN_DOWN,
    adapter_for,
    chosen_identifier_set,
    named_foreign_runtime,
    norm_token,
    runtime_is_chosen,
    tokens,
)

MENTION_PREFIXES = (
    "do not import ",
    "do not use ",
    "never import ",
    "refuses ",
    "refuse ",
)


def _mention_only(text: str, name: str) -> bool:
    low = text.lower()
    n = name.lower()
    for pref in MENTION_PREFIXES:
        if f"{pref}{n}" in low or f"{pref}a {n}" in low:
            return True
    return False


def signal_a_on_chosen(candidate: dict, identifiers: set[str]) -> bool:
    return runtime_is_chosen(str(candidate.get("runtime") or ""), identifiers)


def _foreign_token(value: str) -> str | None:
    n = norm_token(value)
    if not n:
        return None
    if n in LEGITIMATE_LIBS or n.split("-")[0] in LEGITIMATE_LIBS:
        return None
    hit = named_foreign_runtime(value)
    if hit:
        return hit
    toks = tokens(value)
    for name in TORN_DOWN + ("github-actions", "metaswarm", "gha"):
        compact = name.replace("-", "")
        if name in toks or compact in {t.replace("-", "") for t in toks}:
            return name
    return None


def guard_hit(candidate: dict, allowlist: frozenset[str] | None = None) -> dict:
    """Second-control-plane guard (local stand-in when WFA-0056 is absent).

    Fires on a named torn-down / scheduler runtime, on imports, on spawned
    processes, and on dependency-manifest tokens. Silent on legitimate libraries
    and on use-vs-mention refusals in notes.
    """
    allow = allowlist or frozenset()
    runtime = str(candidate.get("runtime") or "")
    reasons = []
    detected = None
    named = named_foreign_runtime(runtime)
    if named and named not in allow:
        reasons.append({"via": "runtime-string", "plane": named})
        detected = named

    def consider(value: str, via: str) -> None:
        nonlocal detected
        hit = _foreign_token(value)
        if hit and hit not in allow:
            reasons.append({"via": via, "plane": hit, "token": value})
            detected = detected or hit

    for item in candidate.get("imports") or []:
        consider(str(item), "import")
    for item in candidate.get("processes") or []:
        consider(str(item), "process")
    for item in candidate.get("manifest_requires") or []:
        consider(str(item), "manifest")

    notes = str(candidate.get("notes") or "")
    mech = str(candidate.get("mechanisms") or "")
    for blob, via in ((mech, "mechanisms"), (notes, "notes")):
        hit = _foreign_token(blob)
        if not hit or hit in allow:
            continue
        if via == "notes" and _mention_only(notes, hit):
            continue
        if not any(r.get("plane") == hit for r in reasons):
            reasons.append({"via": via, "plane": hit})
            detected = detected or hit

    tripped = bool(reasons)
    return {
        "tripped": tripped,
        "detected_plane": detected,
        "reasons": reasons,
        "silent": not tripped,
    }


def target_adapter(candidate: dict, guard: dict) -> dict:
    foreign = guard.get("detected_plane") or named_foreign_runtime(
        str(candidate.get("runtime") or "")
    )
    return adapter_for(candidate, foreign)


def analyse(candidates: list[dict], allowlist: frozenset[str] | None = None) -> dict:
    ident_doc = chosen_identifier_set()
    ident = set(ident_doc["identifiers"])
    partition: dict[str, list[str]] = defaultdict(list)
    on_plane = []
    off_plane = []
    empty_runtime = []
    adopt = []
    disagreements = []
    translate = []
    guard_rows = []

    for c in candidates:
        rt = str(c.get("runtime") or "")
        key = norm_token(rt) or "<empty>"
        partition[key].append(c["id"])
        a_chosen = signal_a_on_chosen(c, ident)
        if not rt:
            empty_runtime.append(c["id"])
            a_chosen = False
        if a_chosen:
            on_plane.append(c["id"])
        else:
            off_plane.append(c["id"])
        g = guard_hit(c, allowlist)
        guard_rows.append(
            {
                "id": c["id"],
                "classification": c.get("classification"),
                "runtime": rt,
                "guard": g,
                "signal_a_on_chosen": a_chosen,
            }
        )
        is_adopt = str(c.get("classification") or "") in ADOPT_CLASSES
        if is_adopt:
            adopt.append(c["id"])
            a_translate = not a_chosen
            b_translate = bool(g["tripped"])
            if a_translate != b_translate:
                disagreements.append(
                    {
                        "id": c["id"],
                        "classification": c.get("classification"),
                        "runtime": rt,
                        "family": c.get("family"),
                        "signal_a": "TRANSLATE" if a_translate else "KEEP",
                        "signal_b": "TRANSLATE" if b_translate else "KEEP",
                        "guard_detected_plane": g.get("detected_plane"),
                        "why": (
                            "runtime-string vs guard disagree; "
                            "string can be wrong (WFA-0072 evidence B)"
                        ),
                    }
                )
            if a_translate or b_translate:
                adapter = target_adapter(c, g)
                translate.append(
                    {
                        "id": c["id"],
                        "from_classification": c.get("classification"),
                        "to_classification": "TRANSLATE",
                        "runtime": rt,
                        "family": c.get("family"),
                        "signal_a_off_plane": a_translate,
                        "guard_tripped": b_translate,
                        "detected_plane": g.get("detected_plane"),
                        "target_adapter": adapter["adapter_id"],
                        "target_adapter_path": adapter["adapter_path"],
                        "target_adapter_name": adapter["name"],
                        "adapter_matched_on": adapter["matched_on"],
                        "identity_kind": c.get("identity_kind"),
                    }
                )

    cls = Counter(str(c.get("classification") or "") for c in candidates)
    fam = Counter(str(c.get("family") or "") for c in candidates)
    runtime_hist = {k: len(v) for k, v in sorted(partition.items())}

    both_agree_zero = len(translate) == 0 and len(disagreements) == 0
    return {
        "n": len(candidates),
        "classification_histogram": dict(cls),
        "family_histogram": dict(fam),
        "translate_in_source": int(cls.get("TRANSLATE", 0)),
        "adopt_n": len(adopt),
        "runtime_partition": runtime_hist,
        "on_chosen_plane": len(on_plane),
        "off_chosen_plane": len(off_plane),
        "empty_runtime": len(empty_runtime),
        "disagreements": disagreements,
        "translate_backlog": translate,
        "translate_n": len(translate),
        "zero_reclassification_ok": both_agree_zero,
        "chosen": ident_doc,
        "guard_allowlist": sorted(allowlist or []),
        "guard_fired_n": sum(1 for r in guard_rows if r["guard"]["tripped"]),
    }


def both_states_plant(candidates: list[dict], analyse_fn=analyse) -> dict:
    from corpus import overlay_benign_lib, overlay_plant

    base = analyse_fn(candidates)
    planted = analyse_fn(overlay_plant(candidates, True))
    unplanted = analyse_fn(overlay_plant(candidates, False))
    benign = analyse_fn(overlay_benign_lib(candidates, True))

    plant_ids_base = {d["id"] for d in base["disagreements"]}
    plant_ids_on = {d["id"] for d in planted["disagreements"]}
    plant_ids_off = {d["id"] for d in unplanted["disagreements"]}
    from corpus import PLANT_ID

    plant_appeared = PLANT_ID in plant_ids_on and PLANT_ID not in plant_ids_base
    plant_cleared = PLANT_ID not in plant_ids_off
    benign_silent = PLANT_ID not in {d["id"] for d in benign["disagreements"]}
    benign_not_translated_extra = not any(
        t["id"] == PLANT_ID and t["guard_tripped"] for t in benign["translate_backlog"]
    )
    return {
        "plant_id": PLANT_ID,
        "base_disagreement_n": len(base["disagreements"]),
        "planted_disagreement_n": len(planted["disagreements"]),
        "unplanted_disagreement_n": len(unplanted["disagreements"]),
        "plant_appeared": plant_appeared,
        "plant_cleared": plant_cleared,
        "benign_lib_silent": benign_silent and benign_not_translated_extra,
        "planted_translate_has_adapter": all(
            t.get("target_adapter") for t in planted["translate_backlog"]
        ),
        "ok": plant_appeared
        and plant_cleared
        and benign_silent
        and benign_not_translated_extra
        and all(t.get("target_adapter") for t in planted["translate_backlog"]),
    }
