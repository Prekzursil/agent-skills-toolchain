#!/usr/bin/env python3
"""Named probe 1: injection-shaped description is quoted/neutralized (both-states).

GOOD: adapter.render_prompt contains the quoting-oracle encoding and no
instruction marker survives outside the data fences.
BAD: leaky interpolation of the raw description; the same leak detector fires.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import adapter  # noqa: E402
import quoting  # noqa: E402


def main() -> int:
    loaded = adapter.discover_from_path()
    doc = loaded["doc"]
    control = doc.get("injection_control") or {}
    want_id = control.get("package_id") or "injection-shaped"
    markers = tuple(control.get("markers") or quoting.INSTRUCTION_MARKERS)

    rows = adapter.raw_entry_rows(doc)
    raw_inj = None
    raw_index = None
    for i, row in enumerate(rows):
        if isinstance(row, dict) and adapter._entry_id(row) == want_id:
            raw_inj = row
            raw_index = i
            break
    if raw_inj is None:
        print("FAILED:IMP-0152-probe1 injection fixture entry missing")
        return 1

    raw_desc = raw_inj.get("description") or ""
    oracle_quoted = quoting.quote(raw_desc)
    candidates = loaded["candidates"]
    cand = next((c for c in candidates if c.get("package_id") == want_id), None)
    if cand is None:
        print("FAILED:IMP-0152-probe1 adapter dropped the injection entry")
        return 1

    prompt = adapter.render_prompt(cand)
    leaks_good = quoting.instruction_leaks(prompt, markers)
    oracle_in_prompt = oracle_quoted in prompt
    quoted_matches = cand["description_quoted"] == oracle_quoted
    digest_ok = cand["description_sha256"] == hashlib.sha256(
        raw_desc.encode("utf-8")
    ).hexdigest()
    raw_not_on_candidate = "description" not in cand
    fence_break_neutralized = quoting.END_NEUTRAL in oracle_quoted
    # Exactly one closed data region in the rendered prompt.
    closed_regions = quoting.quote_count(prompt)

    leaky = adapter.render_prompt_leaky(raw_inj, raw_index or 0)
    leaks_bad = quoting.instruction_leaks(leaky, markers)

    silent_on_good = oracle_in_prompt and not leaks_good and quoted_matches
    fired_on_bad = bool(leaks_bad)

    out = {
        "probe": "probe1-injection-neutralize",
        "unit_id": "IMP-0152",
        "registry_source": loaded["registry_source"],
        "package_id": want_id,
        "oracle_in_prompt": oracle_in_prompt,
        "quoted_matches_oracle": quoted_matches,
        "description_sha256_ok": digest_ok,
        "raw_description_absent_from_candidate": raw_not_on_candidate,
        "fence_break_neutralized": fence_break_neutralized,
        "closed_quoted_regions": closed_regions,
        "leaks_good": leaks_good,
        "leaks_bad": leaks_bad,
        "silent_on_good": silent_on_good,
        "fired_on_bad": fired_on_bad,
        "pass": bool(
            silent_on_good
            and fired_on_bad
            and digest_ok
            and raw_not_on_candidate
            and fence_break_neutralized
            and closed_regions == 1
        ),
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"oracle_in_prompt={oracle_in_prompt} leaks_good={leaks_good} "
        f"leaks_bad={leaks_bad} fired_on_bad={fired_on_bad} "
        f"silent_on_good={silent_on_good}"
    )
    if not out["pass"]:
        print("FAILED:IMP-0152-probe1 injection neutralization both-states")
        return 1
    print("SUCCESS:IMP-0152-probe1 injection-shaped description quoted/neutralized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
