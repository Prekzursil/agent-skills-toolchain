"""Shared evaluation: identity proofs, alias matrix, estate census, required tests."""
from __future__ import annotations

import json
from pathlib import Path

import guards as G
import inventory as I
import scenario as S
from winpath import FIXTURE_VOLUME, same_identity, sep_fold, win_identity

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center" / "receipts" / "TST-0066.json"
SENTINEL = "SUCCESS:TST-0066"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def _shots_for(rows: list[dict], guard_id: str) -> list[dict]:
    return [r for r in rows if r["guard_id"] == guard_id]


def _verdict(rows: list[dict], guard_id: str, candidate: str) -> str:
    hits = [r for r in rows if r["guard_id"] == guard_id and r["candidate"] == candidate]
    if len(hits) != 1:
        raise RuntimeError(f"need one shot {guard_id!r} {candidate!r}, got {len(hits)}")
    return hits[0]["verdict"]


def required_tests(control_rows: list[dict], estate_class: list[dict]) -> list[dict]:
    tests: list[dict] = []

    def add(tid: str, ok: bool, detail: str) -> None:
        tests.append(
            {
                "id": tid,
                "result": "PASS" if ok else "FAIL",
                "detail": detail,
            }
        )

    # Identities must actually be aliases, else the matrix is theatre.
    id_rows = S.prove_identities()
    add(
        "identity-aliases-are-real",
        all(r["ok"] for r in id_rows),
        json.dumps([r for r in id_rows if not r["ok"]][:4]),
    )

    c_dot = _verdict(control_rows, "canonical-deny", S.DENIED_SECRET_DOT)
    c_spc = _verdict(control_rows, "canonical-deny", S.DENIED_SECRET_SPACE)
    c_83 = _verdict(control_rows, "canonical-deny", S.DENIED_SECRET_83)
    add(
        "test_trailing_dot_alias_does_not_bypass_the_guard",
        c_dot == G.REJECT and c_spc == G.REJECT,
        f"canonical-deny dot={c_dot} space={c_spc}",
    )
    add(
        "test_short_name_alias_does_not_bypass_the_guard",
        c_83 == G.REJECT,
        f"canonical-deny 8.3={c_83}",
    )

    s_dot = _verdict(control_rows, "control-deny", S.DENIED_SECRET_DOT)
    s_83 = _verdict(control_rows, "control-deny", S.DENIED_SECRET_83)
    s_long = _verdict(control_rows, "control-deny", S.DENIED_SECRET)
    add(
        "test_string_comparing_control_guard_IS_bypassed",
        s_long == G.REJECT and s_dot == G.ACCEPT and s_83 == G.ACCEPT,
        f"control-deny long={s_long} dot={s_dot} 8.3={s_83}",
    )

    # Canonical allow/containment: aliases of in-policy stay in-policy;
    # both escape aliases stay out-of-policy. String-unequal, identity-equal
    # must share a verdict — proof comparison runs after canonicalisation.
    hook_long = _verdict(control_rows, "canonical-allow", S.ALLOWED_HOOK)
    hook_dot = _verdict(control_rows, "canonical-allow", S.ALLOWED_HOOK_DOT)
    hook_83 = _verdict(control_rows, "canonical-allow", S.ALLOWED_HOOK_83)
    out_dot = _verdict(control_rows, "canonical-allow", S.OUTSIDE_HOOKS_VIA_DOT)
    out_83 = _verdict(control_rows, "canonical-allow", S.OUTSIDE_HOOKS_VIA_83)
    in_long = _verdict(control_rows, "canonical-contain", S.INSIDE_LONG)
    in_dot = _verdict(control_rows, "canonical-contain", S.INSIDE_DOT)
    in_83 = _verdict(control_rows, "canonical-contain", S.INSIDE_VIA_83)
    esc_dot = _verdict(control_rows, "canonical-contain", S.OUTSIDE_VIA_DOT)
    esc_83 = _verdict(control_rows, "canonical-contain", S.OUTSIDE_VIA_83)
    unequal_strings = sep_fold(S.DENIED_SECRET) != sep_fold(S.DENIED_SECRET_DOT)
    same_id = same_identity(S.DENIED_SECRET, S.DENIED_SECRET_DOT, FIXTURE_VOLUME)
    canon_applied = (
        unequal_strings
        and same_id
        and hook_long == hook_dot == hook_83 == G.ACCEPT
        and out_dot == out_83 == G.REJECT
        and in_long == in_dot == in_83 == G.ACCEPT
        and esc_dot == esc_83 == G.REJECT
        and c_dot == c_83 == G.REJECT
    )
    add(
        "test_canonicalisation_is_applied_before_every_comparison",
        canon_applied,
        (
            f"unequal_strings={unequal_strings} same_id={same_id} "
            f"allow={hook_long}/{hook_dot}/{hook_83} out={out_dot}/{out_83} "
            f"contain={in_long}/{in_dot}/{in_83} esc={esc_dot}/{esc_83}"
        ),
    )

    string_guards = [g for g in estate_class if g["compares_path_strings"]]
    add(
        "estate-string-guards-named",
        len(string_guards) >= 1,
        json.dumps([g["guard_id"] for g in string_guards]),
    )
    # Evidence requirement: every estate guard fired BOTH aliases.
    both_aliases = True
    missing = []
    for g in estate_class:
        cands = {s["candidate"] for s in g["shots"]}
        if g["guard_id"] == "estate-reconcile-deny":
            need = {S.ESTATE_DENIED_DOT, S.ESTATE_DENIED_83}
        elif g["guard_id"] == "estate-permission-allowlist":
            need = {S.ALLOWED_HOOK_DOT, S.ALLOWED_HOOK_83}
        else:
            need = {S.INSIDE_DOT, S.INSIDE_VIA_83}
        if not need <= cands:
            both_aliases = False
            missing.append({"guard": g["guard_id"], "missing": sorted(need - cands)})
    add(
        "both-aliases-attempted-per-estate-guard",
        both_aliases,
        json.dumps(missing),
    )
    return tests


def artifact_error() -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return "artifact sentinel absent"
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"artifact unparseable:{type(exc).__name__}"
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return f"artifact self-declared {st}"
    if doc.get("unit_id") != "TST-0066":
        return f"artifact unit_id {doc.get('unit_id')!r}"
    ctrl = doc.get("detector_control") or {}
    if ctrl.get("bypassed") is not True:
        return "detector_control.bypassed is not true"
    return None


def evaluate() -> dict:
    id_rows = S.prove_identities()
    control_rows = I.control_and_canonical_shots()
    estate_rows = I.estate_shots()
    estate_class = I.classify_estate(estate_rows)
    tests = required_tests(control_rows, estate_class)
    failed = [t for t in tests if t["result"] != "PASS"]
    string_guards = [
        {
            "guard_id": g["guard_id"],
            "kind": g["kind"],
            "policy": g["policy"],
            "compares_path_strings": True,
        }
        for g in estate_class
        if g["compares_path_strings"]
    ]
    return {
        "identities": id_rows,
        "control_shots": control_rows,
        "estate_shots": estate_rows,
        "estate_classification": estate_class,
        "string_comparing_estate_guards": string_guards,
        "tests": tests,
        "failed": failed,
        "canonical_deny_secret": win_identity(S.DENIED_SECRET, FIXTURE_VOLUME),
        "pass": not failed,
    }
