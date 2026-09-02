#!/usr/bin/env python3
"""Probe 2: both-states detector controls from fixtures, independent of the artifact conclusion."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import extract as X  # noqa: E402
import runner as R  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0037-doc-command-conformance.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0037-probe2 {msg}")
    return 1


def main() -> int:
    fixtures = X.fixture_doc_paths(REPO)
    extracted: list[dict] = []
    for path in fixtures:
        extracted.extend(X.extract_file(path, REPO))
    if len(extracted) < 4:
        return fail(f"expected >=4 fixture commands, got {len(extracted)}")
    rows = R.execute_all(extracted, REPO, timeout=45)
    by_inv = {r["invocation"]: r for r in rows}

    missing = next(
        (r for r in rows if "cnf0037-definitely-not-a-real-command" in r["invocation"]),
        None,
    )
    differ = next((r for r in rows if "actual-line" in r["invocation"]), None)
    cred = next((r for r in rows if "OPENAI_API_KEY" in r["invocation"]), None)
    good = next((r for r in rows if "hello-cnf-0037" in r["invocation"]), None)

    missing_ok = (
        missing is not None
        and missing["outcome"] == "COMMAND-MISSING"
        and missing["classification"] == "documentation-defect"
        and str(missing["source_path"]).endswith("advanced.md")
        and int(missing["source_line"]) >= 1
    )
    # Recompute the diff from raw strings; a hand-waved "different" flag is not enough.
    live_diff = R.output_diff(
        differ.get("documented_output") or "", differ.get("actual_output") or ""
    ) if differ else ""
    differ_ok = (
        differ is not None
        and differ["outcome"] == "DIFF"
        and bool(live_diff)
        and live_diff == (differ.get("diff") or "")
        and "documented-other-line" in live_diff
        and "actual-line" in live_diff
    )
    cred_ok = (
        cred is not None
        and cred["outcome"] == "BLOCKED"
        and cred.get("actual_output") == ""
        and cred.get("actual_exit") is None
        and "credentials" in str(cred.get("blocked_reason") or "")
    )
    good_ok = good is not None and good["outcome"] == "MATCH"

    dropped = [r for r in rows if r["outcome"] != "BLOCKED"]
    omit_keys = X.silently_omitted(extracted, dropped)
    silent_skip_fires = any("OPENAI_API_KEY" in f"{p[2]}" for p in omit_keys)

    full_omit = X.silently_omitted(extracted, rows)
    silent_on_full = full_omit == []

    print(
        json.dumps(
            {
                "missing_ok": missing_ok,
                "differ_ok": differ_ok,
                "cred_ok": cred_ok,
                "good_ok": good_ok,
                "silent_skip_fires": silent_skip_fires,
                "silent_on_full": silent_on_full,
                "missing_source": None
                if missing is None
                else f"{missing['source_path']}:{missing['source_line']}",
                "invocations": [r["invocation"] for r in rows],
            },
            sort_keys=True,
        )
    )
    if not (missing_ok and differ_ok and cred_ok and good_ok and silent_skip_fires and silent_on_full):
        return fail("detector did not discriminate")

    # Artifact must record the same control outcomes (checked after independent derivation).
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    rec = {c.get("verbatim_invocation"): c for c in (doc.get("commands") or [])}
    for inv, live in by_inv.items():
        art = rec.get(inv)
        if art is None:
            return fail(f"fixture invocation absent from artifact: {inv}")
        if art.get("outcome") != live.get("outcome"):
            return fail(f"artifact outcome {art.get('outcome')} != live {live.get('outcome')} for {inv}")
    print("SUCCESS:CNF-0037-probe2 detector controls fire on known-broken fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
