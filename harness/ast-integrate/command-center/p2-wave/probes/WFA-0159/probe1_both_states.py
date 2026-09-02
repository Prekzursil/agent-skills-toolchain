#!/usr/bin/env python3
"""Probe 1: archived/relicensed demote; unchanged must not.

Required order: run the demote cases BEFORE trusting the unchanged verdicts.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import decay as D  # noqa: E402
import live_fetch as LF  # noqa: E402
import registry as R  # noqa: E402

UP = HERE / "fixtures" / "upstream"


def _row(corpus: dict, cid: str) -> dict:
    for item in corpus["candidates"]:
        if item.get("id") == cid:
            return item
    raise KeyError(cid)


def _live(name: str) -> dict:
    return LF.load_fixture_live(UP / name)


def main() -> int:
    now = datetime.now(timezone.utc)
    corpus = R.load_control_corpus()
    recount = R.recount_adopt(corpus["candidates"])
    if recount["adopt_as_is"] < 1 or recount["adopt_with_wrapper"] < 1:
        print(f"FAILED:WFA-0159-probe1 control corpus histogram {recount}")
        return 1

    # Demote cases first — do not read unchanged verdicts until these fire.
    archived_c = D.apply_relative_validated_at(
        _row(corpus, "ctrl-archived-since-adopt"), now
    )
    relicensed_c = D.apply_relative_validated_at(
        _row(corpus, "ctrl-relicensed-since-adopt"), now
    )
    archived = D.revalidate(archived_c, _live("archived.json"), now)
    relicensed = D.revalidate(relicensed_c, _live("relicensed.json"), now)

    print(
        f"demote-first archived verdict={archived['verdict']} "
        f"reasons={archived['reasons']} class={archived['new_classification']}"
    )
    print(
        f"demote-first relicensed verdict={relicensed['verdict']} "
        f"reasons={relicensed['reasons']} class={relicensed['new_classification']}"
    )

    arch_ok = (
        archived["verdict"] == D.DEMOTE
        and "ARCHIVED" in archived["reasons"]
        and archived["new_classification"] == D.DEMOTE_CLASS
    )
    rel_ok = (
        relicensed["verdict"] == D.DEMOTE
        and "RELICENSED" in relicensed["reasons"]
        and relicensed["new_classification"] == D.DEMOTE_CLASS
    )
    if not (arch_ok and rel_ok):
        print("FAILED:WFA-0159-probe1 demote cases did not fire before unchanged")
        return 1
    print("demote-cases-ran-before-unchanged=True")

    unchanged_c = D.apply_relative_validated_at(
        _row(corpus, "ctrl-adopt-as-is-unchanged"), now
    )
    wrapper_c = D.apply_relative_validated_at(
        _row(corpus, "ctrl-adopt-wrapper-unchanged"), now
    )
    unchanged = D.revalidate(unchanged_c, _live("unchanged.json"), now)
    wrapper = D.revalidate(wrapper_c, _live("wrapper_ok.json"), now)
    print(
        f"unchanged verdict={unchanged['verdict']} reasons={unchanged['reasons']} "
        f"class={unchanged['new_classification']}"
    )
    print(
        f"wrapper-unchanged verdict={wrapper['verdict']} reasons={wrapper['reasons']} "
        f"class={wrapper['new_classification']}"
    )
    keep_ok = (
        unchanged["verdict"] == D.KEEP
        and unchanged["reasons"] == []
        and unchanged["new_classification"] == "ADOPT-AS-IS"
        and wrapper["verdict"] == D.KEEP
        and wrapper["new_classification"] == "ADOPT-WITH-WRAPPER"
    )
    if not keep_ok:
        print("FAILED:WFA-0159-probe1 unchanged upstream was demoted")
        return 1

    # Mutant: if we ignore archived, the engine would KEEP — prove we do not.
    live_arch_hidden = dict(_live("archived.json"))
    live_arch_hidden["archived"] = False
    hidden = D.revalidate(archived_c, live_arch_hidden, now)
    if hidden["verdict"] != D.KEEP:
        print(
            f"FAILED:WFA-0159-probe1 hidden-archive control expected KEEP got {hidden}"
        )
        return 1
    print("hidden-archive-without-flag=KEEP (engine keys off archived bit)")
    print("fired_on_bad=True silent_on_good=True")
    print("SUCCESS:WFA-0159-probe1 archived/relicensed demote; unchanged holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
