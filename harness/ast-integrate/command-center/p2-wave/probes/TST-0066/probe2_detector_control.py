#!/usr/bin/env python3
"""Probe 2: detector control — string-comparing guard IS bypassed.

Mechanically different from probe 1: does not score the estate census.
It only plants a deny-list keyed on the long name, proves BOTH aliases
are string-unequal to that name (so a string compare cannot see them)
and identity-equal (so they are the same file), then shows:

  * the string mutant ACCEPTs both aliases (hole)
  * the canonical mutant REJECTs both aliases (closed)
  * an empty deny list is refused as vacuous (would make every ACCEPT
    look like a bypass)

Silence on the string mutant is detector-failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import evaluate as E  # noqa: E402
import guards as G  # noqa: E402
import scenario as S  # noqa: E402
from winpath import FIXTURE_VOLUME, same_identity, sep_fold, win_identity  # noqa: E402

OUT = HERE / "probe2-detector-control.raw.json"


def main() -> int:
    denied = S.DENIED_SECRET
    aliases = {
        "trailing_dot": S.DENIED_SECRET_DOT,
        "trailing_space": S.DENIED_SECRET_SPACE,
        "short_name": S.DENIED_SECRET_83,
    }
    if not denied.strip():
        print("FAILED:TST-0066-probe2 vacuous empty deny list")
        return 1

    rows = []
    for name, alias in aliases.items():
        str_eq = sep_fold(denied) == sep_fold(alias)
        ident = same_identity(denied, alias, FIXTURE_VOLUME)
        s_ver = G.string_deny_exact(denied, alias)
        c_ver = G.canonical_deny_exact(denied, alias, FIXTURE_VOLUME)
        rows.append(
            {
                "alias": name,
                "candidate": alias,
                "string_equal_to_denied": str_eq,
                "same_win_identity": ident,
                "denied_identity": win_identity(denied, FIXTURE_VOLUME),
                "alias_identity": win_identity(alias, FIXTURE_VOLUME),
                "string_guard": s_ver,
                "canonical_guard": c_ver,
            }
        )

    payload = {
        "probe": "probe2-detector-control",
        "unit_id": "TST-0066",
        "denied": denied,
        "rows": rows,
        "pass": False,
    }

    if any(r["string_equal_to_denied"] for r in rows):
        payload["error"] = "alias is string-equal; control cannot demonstrate a hole"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:TST-0066-probe2 aliases collapsed to the denied string")
        return 1
    if not all(r["same_win_identity"] for r in rows):
        payload["error"] = "alias is not the same Windows identity as denied"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:TST-0066-probe2 identity map broken")
        return 1
    if any(r["string_guard"] != G.ACCEPT for r in rows):
        payload["error"] = "string-comparing control was not bypassed"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:TST-0066-probe2 detector-failure: control not bypassed")
        return 1
    if any(r["canonical_guard"] != G.REJECT for r in rows):
        payload["error"] = "canonical guard missed an alias of the denied file"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:TST-0066-probe2 canonical deny bypassed")
        return 1

    # Negative: the long name itself must still be rejected by both.
    if G.string_deny_exact(denied, denied) != G.REJECT:
        payload["error"] = "string deny missed the exact denied path"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print("FAILED:TST-0066-probe2 control cannot see the exact path")
        return 1
    if G.canonical_deny_exact(denied, denied) != G.REJECT:
        payload["error"] = "canonical deny missed the exact denied path"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print("FAILED:TST-0066-probe2 canonical cannot see the exact path")
        return 1

    art_err = E.artifact_error()
    if art_err:
        payload["error"] = art_err
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print(f"FAILED:TST-0066-probe2 {art_err}")
        return 1

    payload["pass"] = True
    payload["bypassed"] = True
    payload["aliases_fired"] = list(aliases)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "bypassed=True aliases="
        + ",".join(aliases)
        + " string_ACCEPT="
        + str(sum(1 for r in rows if r["string_guard"] == G.ACCEPT))
        + " canonical_REJECT="
        + str(sum(1 for r in rows if r["canonical_guard"] == G.REJECT))
        + " same_search=guards.string_deny_exact"
    )
    print("SUCCESS:TST-0066-probe2 string-comparing control IS bypassed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
