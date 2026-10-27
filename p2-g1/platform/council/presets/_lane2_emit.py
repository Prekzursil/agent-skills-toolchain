"""Emit the lane-2 preset JSON files and MEASURE them.

Run from this directory:  python _lane2_emit.py

Emits one `<council_id>.councilspec.json` per preset, then reads each file BACK
off disk and reports, per file: schema validity, semantic findings, seat
accounting versus the design card, and the byte size. Exit code is non-zero if
any file fails, so this doubles as a gate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "platform" / "lib"))

from _lane2_build_a import p17_red_blue_4, p18_oxford_4_plus_judge  # noqa: E402
from _lane2_build_b import (  # noqa: E402
    p19_socratic_chair_plus_4,
    p20_charrette_5_design,
    p21_six_hats_6,
    p22_nominal_group_6,
)
from _lane2_build_c import (  # noqa: E402
    p23_delphi_5_anon_3rounds,
    p24_ach_5_hypotheses,
    p25_war_room_5_incident,
    p26_postmortem_5_blameless,
)
from _lane2_build_d import (  # noqa: E402
    p27_kill_the_company_5,
    p28_stakeholder_negotiation_5,
    p29_two_key_authorization,
    p30_rfc_last_call_open,
)
from _lane2_build_e import (  # noqa: E402
    p31_deep_architecture_12,
    p32_deep_security_threat_model_10,
)
from _lane2_build_f import g_stakeholder_user_panel  # noqa: E402

# (design_index, card_id, seats_declared_on_card, roles_enumerated_on_card, builder)
LANE: List[Tuple[int, str, int, int, Any]] = [
    (17, "C-S17 red-blue-4", 4, 5, p17_red_blue_4),
    (18, "C-S18 oxford-4-plus-judge", 5, 5, p18_oxford_4_plus_judge),
    (19, "C-S19 socratic-chair-plus-4", 5, 5, p19_socratic_chair_plus_4),
    (20, "C-S20 charrette-5-design", 5, 5, p20_charrette_5_design),
    (21, "C-S21 six-hats-6", 6, 6, p21_six_hats_6),
    (22, "C-S22 nominal-group-6", 6, 7, p22_nominal_group_6),
    (23, "C-S23 delphi-5-anon-3rounds", 5, 6, p23_delphi_5_anon_3rounds),
    (24, "C-S24 ach-5-hypotheses", 5, 5, p24_ach_5_hypotheses),
    (25, "C-S25 war-room-5-incident", 5, 5, p25_war_room_5_incident),
    (26, "C-S26 postmortem-5-blameless", 5, 5, p26_postmortem_5_blameless),
    (27, "C-S27 kill-the-company-5", 5, 5, p27_kill_the_company_5),
    (28, "C-S28 stakeholder-negotiation-5", 5, 5, p28_stakeholder_negotiation_5),
    (29, "C-S29 two-key-authorization", 2, 2, p29_two_key_authorization),
    (30, "C-S30 rfc-last-call-open", 6, 6, p30_rfc_last_call_open),
    (31, "C-D31 deep-architecture-12", 12, 13, p31_deep_architecture_12),
    (
        32,
        "C-D32 deep-security-threat-model-10",
        10,
        10,
        p32_deep_security_threat_model_10,
    ),
    (
        0,
        "(gap fill: spec-required stakeholder_user_panel, no design card)",
        0,
        0,
        g_stakeholder_user_panel,
    ),
]


def total_seats(spec: Dict[str, Any]) -> int:
    n = len(spec.get("participants", {}).get("roster") or [])
    for sub in (spec.get("topology") or {}).get("subcouncils") or []:
        n += total_seats(sub)
    return n


def main() -> int:
    import jsonschema  # noqa: PLC0415
    from councilspec import semantics  # noqa: PLC0415

    schema_path = REPO / "platform" / "schema" / "councilspec.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)

    rows: List[Dict[str, Any]] = []
    failures = 0
    for index, card, seats_card, roles_card, build in LANE:
        spec = build()
        path = HERE / f"{spec['council_id']}.councilspec.json"
        # newline="\n" is load-bearing: on Windows the default text mode translates
        # "\n" to CRLF, and a committed CRLF blob is what makes a local formatter or
        # byte-comparison gate disagree with CI on the same commit.
        path.write_text(
            json.dumps(spec, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        # read BACK off disk - never report on the in-memory object
        loaded = json.loads(path.read_text(encoding="utf-8"))
        errors = sorted(
            validator.iter_errors(loaded), key=lambda e: list(e.absolute_path)
        )
        findings = semantics.check(loaded)
        sem_errors = [str(f) for f in findings if f.severity == "ERROR"]
        sem_warns = [str(f) for f in findings if f.severity == "WARN"]

        seats = total_seats(loaded)
        ok = not errors and not sem_errors
        if not ok:
            failures += 1
        rows.append(
            {
                "design_index": index,
                "design_card": card,
                "file": path.name,
                "bytes": path.stat().st_size,
                "council_id": loaded["council_id"],
                "preset": loaded["preset"],
                "schema_valid": not errors,
                "schema_errors": [
                    f"{list(e.absolute_path)}: {e.message}" for e in errors[:5]
                ],
                "semantic_errors": sem_errors,
                "semantic_warnings": sem_warns,
                "seats_in_instance": seats,
                "seats_declared_on_card": seats_card,
                "roles_enumerated_on_card": roles_card,
                "card_self_consistent": seats_card == roles_card,
                "verdict": "PASS" if ok else "FAIL",
            }
        )
        mark = "PASS" if ok else "FAIL"
        print(
            f"[{mark}] idx={index:>2} {path.name}  preset={loaded['preset']}  "
            f"seats={seats} (card said {seats_card}, card enumerated {roles_card})  "
            f"{path.stat().st_size} bytes"
        )
        for e in rows[-1]["schema_errors"]:
            print(f"        schema: {e}")
        for e in sem_errors:
            print(f"        sem   : {e}")
        for w in sem_warns:
            print(f"        warn  : {w}")

    out = HERE / "_lane2_emit_out.json"
    out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"\nfiles={len(rows)} pass={len(rows) - failures} fail={failures}")
    print(f"detail -> {out}")
    if failures:
        print(f"FAILED:build-preset-2 {failures} preset(s) do not validate")
        return 1
    print(
        "SUCCESS:build-preset-2 every emitted preset is schema-valid with zero semantic errors"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
