#!/usr/bin/env python3
"""Probe 1 (IMP-0052): structural check — every rendered message has three non-empty parts.

Independent of redaction: this probe never plants secrets and never greps for them.
Both-states control: an empty-impact mutant must fail the parser.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))
import message_renderer as mr  # noqa: E402

MUTANT_EMPTY_IMPACT = (
    f"{mr.LABEL_CAUSE} the packer refused to emit\n"
    f"{mr.LABEL_IMPACT} \n"
    f"{mr.LABEL_NEXT} python3 --version\n"
)


def main() -> int:
    codes = mr.all_codes()
    print(f"catalog_codes={len(codes)}")
    if len(codes) < 10:
        print("FAILED:IMP-0052-probe1 catalog has fewer than 10 codes")
        return 1

    failed = []
    for code in codes:
        text = mr.render_text(mr.InternalError(code=code))
        parsed = mr.parse_three_part(text)
        print(
            f"code={code} ok={parsed['ok']} "
            f"cause_len={len(parsed['cause'])} "
            f"impact_len={len(parsed['impact'])} "
            f"next_len={len(parsed['next_command'])} "
            f"traceback={parsed['has_traceback']}"
        )
        if not parsed["ok"] or parsed["has_traceback"]:
            failed.append(code)

    unknown = mr.render_text(mr.InternalError(code="AST.PLUGIN.NOT.IN.CATALOG"))
    parsed_u = mr.parse_three_part(unknown)
    print(
        f"unknown_code ok={parsed_u['ok']} next={parsed_u['next_command']!r} "
        f"traceback={parsed_u['has_traceback']}"
    )
    if not parsed_u["ok"]:
        print("FAILED:IMP-0052-probe1 unknown code missing a part")
        return 1

    mutant = mr.parse_three_part(MUTANT_EMPTY_IMPACT)
    print(
        f"negative_control_empty_impact ok={mutant['ok']} "
        f"impact={mutant['impact']!r} fired={not mutant['ok']}"
    )
    if mutant["ok"]:
        print("FAILED:IMP-0052-probe1 empty-impact mutant was accepted")
        return 1

    if failed:
        print(f"FAILED:IMP-0052-probe1 incomplete codes={failed}")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe1-three-part-structure",
                "unit_id": "IMP-0052",
                "codes_checked": len(codes),
                "unknown_ok": True,
                "empty_impact_rejected": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0052-probe1 three-part structure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
