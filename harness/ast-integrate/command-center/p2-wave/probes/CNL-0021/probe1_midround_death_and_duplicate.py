#!/usr/bin/env python3
"""Probe 1: mid-round death reaches a defined state; both-direction independence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import fixtures as F  # noqa: E402
from runtime import (  # noqa: E402
    detect_by_role,
    duplicate_pairs,
    hang_check,
    inherited_ballots,
    run,
)

ART = (
    REPO
    / "command-center/design/council/"
    / "CNL-0021-participant-replacement-and-duplicate-independence-detecti.md"
)
SENTINEL = "SUCCESS:CNL-0021"


def _dup_codes(seats) -> list[str]:
    return [f.code for f in duplicate_pairs(seats)]


def _dup_id_sets(seats) -> list[set[str]]:
    return [set(f.seats) for f in duplicate_pairs(seats) if f.code == "DUPLICATE-INDEPENDENCE"]


def main() -> int:
    report: dict = {"probe": "probe1", "unit_id": "CNL-0021", "checks": []}

    def check(name: str, ok: bool, **extra) -> None:
        row = {"name": name, "ok": bool(ok), **extra}
        report["checks"].append(row)
        print(f"{name}={ok}" + ("" if not extra else " " + json.dumps(extra, sort_keys=True)))
        if not ok:
            raise AssertionError(name)

    try:
        c, script = F.midround_death_honest()
        run(c, script)
        hang = hang_check(c)
        check(
            "midround_defined_state",
            c.status == "REPLACED-AND-CONTINUED" and hang is None,
            status=c.status,
            steps=c.steps,
        )
        inh = inherited_ballots(c, "seat-architect", "seat-architect-r2")
        check("no_vote_inheritance", len(inh) == 0, inherited=len(inh))
        origins = {i.idea_id: i.originator_seat_id for i in c.ideas}
        check("ideas_stay_with_dead_originator", origins.get("I1") == "seat-architect", origins=origins)
        repl_rounds = {b.round_id for b in c.ballots if b.seat_id == "seat-architect-r2"}
        check("replacement_ballots_only_after_seat", repl_rounds == {2}, rounds=sorted(repl_rounds))
        dead_still = c.seat("seat-architect")
        check("dead_seat_id_not_reused", dead_still is not None and not dead_still.alive)

        c2, s2 = F.midround_death_inherit_mutant()
        run(c2, s2)
        inh2 = inherited_ballots(c2, "seat-architect", "seat-architect-r2")
        check("inheritance_mutant_fires", len(inh2) > 0, inherited=len(inh2))

        c3, s3 = F.midround_death_hang_mutant()
        run(c3, s3)
        check("hang_mutant_fires", c3.status == "HUNG" and hang_check(c3) is not None, status=c3.status)

        c4, s4 = F.midround_death_no_replacement_quorum_ok()
        run(c4, s4)
        check("degraded_no_replacement", c4.status == "DEGRADED-NO-REPLACEMENT", status=c4.status)

        c5, s5 = F.midround_death_no_replacement_quorum_fail()
        run(c5, s5)
        check("aborted_quorum", c5.status == "ABORTED-QUORUM", status=c5.status)

        same = F.roster_same_base_model_different_roles()
        same_sets = _dup_id_sets(same)
        check(
            "same_base_model_detected",
            same_sets == [{"s-arch", "s-skep"}],
            findings=[f.code for f in duplicate_pairs(same)],
        )
        role_miss = detect_by_role(same)
        check(
            "role_checker_misses_collusion",
            len(role_miss) == 0,
            role_findings=len(role_miss),
        )

        diff = F.roster_genuinely_different()
        check("genuinely_different_not_flagged", _dup_id_sets(diff) == [])

        gpt = F.roster_gpt4o_vs_gpt41()
        check("gpt4o_not_collapsed_to_gpt41", _dup_id_sets(gpt) == [])

        xv = F.roster_cross_vendor_same_model()
        check(
            "cross_vendor_same_model_detected",
            _dup_id_sets(xv) == [{"s-oa", "s-az"}],
        )

        tri = F.roster_three_with_one_duplicate()
        check(
            "three_seat_one_pair",
            _dup_id_sets(tri) == [{"s-arch", "s-skep"}],
        )

        una = F.roster_unattested()
        codes = _dup_codes(una)
        check(
            "unattested_fail_closed_not_duplicate",
            codes == ["UNATTESTED"] and _dup_id_sets(una) == [],
            codes=codes,
        )
    except AssertionError as exc:
        print(json.dumps(report, indent=2, sort_keys=True))
        print(f"FAILED:CNL-0021-probe1 {exc}")
        return 1

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as exc:
            print(f"FAILED:CNL-0021-probe1 artifact-unparseable {exc}")
            return 1
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:CNL-0021-probe1 self-declared {st}")
            return 1
        if SENTINEL not in text:
            print("FAILED:CNL-0021-probe1 sentinel-absent")
            return 1
        measured = doc.get("measured") or {}
        if measured.get("honest_status") != "REPLACED-AND-CONTINUED":
            print("FAILED:CNL-0021-probe1 artifact honest_status drift")
            return 1
        if measured.get("honest_inherited") != 0:
            print("FAILED:CNL-0021-probe1 artifact inherited drift")
            return 1
        report["artifact_checked"] = True
    else:
        report["artifact_checked"] = False

    print(json.dumps({k: report[k] for k in ("probe", "unit_id", "artifact_checked")}, sort_keys=True))
    print("negative_control_reject_state=same-base-model pair with distinct role labels")
    print(
        "negative_control_verbatim="
        + json.dumps(
            {
                "code": "DUPLICATE-INDEPENDENCE",
                "seats": ["s-arch", "s-skep"],
                "detail": "canonical_model=claude-opus-4 shared by 2 seats",
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNL-0021-probe1 mid-round death defined-state both-direction independence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
