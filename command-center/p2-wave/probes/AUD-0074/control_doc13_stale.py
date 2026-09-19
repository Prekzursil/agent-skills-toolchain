#!/usr/bin/env python3
"""AUD-0074 control: known doc-13 correction must produce >=1 stale-downstream flag.

Both-states:
  BAD  — edges that cite doc-13 from pre-correction citers must flag stale.
  GOOD — edges that cite doc-13 from post-correction citers must NOT flag.

Zero flags on the known bad case means the timestamp check is inert → FAIL.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]  # .../probes/AUD-0074 -> repo root
CORPUS = HERE / "fixtures" / "corpus"
CONTROL = HERE / "fixtures" / "control"
PROBE2 = HERE / "probe2_timestamp_ordering.py"
PROBE1 = HERE / "probe1_citation_edges.py"

DOC13 = "13-ARCHITECTURE-CANDIDATES.md"


def run_py(script: Path, raw: Path, result: Path) -> tuple[int, str]:
    import subprocess

    cmd = [
        "python3",
        "-B",
        str(script),
        "--raw-output",
        str(raw),
        "--result-json",
        str(result),
    ]
    if script.name.startswith("probe2"):
        cmd.extend(["--edges-json", str(HERE / "probe1-citation-edges.json")])
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO))
    out = (r.stdout or "") + (r.stderr or "")
    return r.returncode, out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-output", type=Path, required=True)
    ap.add_argument("--result-json", type=Path, required=True)
    args = ap.parse_args()

    # Ensure corpus built
    import subprocess

    build = HERE / "fixtures" / "build_corpus.py"
    br = subprocess.run(
        ["python3", "-B", str(build)],
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    if br.returncode != 0:
        raise SystemExit(f"FAILED:AUD-0074-control corpus build: {br.stderr}")

    # Re-run probe1 then probe2 against the planted corpus (bad state includes
    # pre-correction citers 17-DECISION-LOG + 15-IMPLEMENTATION-PRECONDITIONS).
    rc1, out1 = run_py(
        PROBE1,
        HERE / "probe1-citation-edges.raw.txt",
        HERE / "probe1-citation-edges.json",
    )
    rc2, out2 = run_py(
        PROBE2,
        HERE / "probe2-timestamp-ordering.raw.txt",
        HERE / "probe2-timestamp-ordering.json",
    )
    p2 = json.loads(
        (HERE / "probe2-timestamp-ordering.json").read_text(encoding="utf-8")
    )
    bad_flags = int(p2.get("doc13_stale_downstream_flag_count") or 0)
    bad_flag_rows = [
        f for f in (p2.get("stale_downstream_flags") or []) if f.get("to") == DOC13
    ]

    # GOOD state: rewrite the two planted-stale citers to post-correction mtimes
    # and fresh decision-log wording, re-run probe2, expect zero doc13 stale flags
    # for those citers.
    import os

    corr = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc).timestamp()
    after = corr + 86400 * 5
    fresh_body = (CONTROL / "17-DECISION-LOG.fresh.md").read_text(encoding="utf-8")
    # Save bad copies
    decision = CORPUS / "17-DECISION-LOG.md"
    impl = CORPUS / "15-IMPLEMENTATION-PRECONDITIONS.md"
    bad_decision = decision.read_text(encoding="utf-8")
    bad_impl = impl.read_text(encoding="utf-8")

    decision.write_text(
        "# 17-DECISION-LOG.md (AUD-0074 good-state)\n\n"
        + fresh_body
        + f"\n## Citations\n- depends on `{DOC13}`\n- depends on `16-GRILL-QUEUE.md`\n",
        encoding="utf-8",
        newline="\n",
    )
    os.utime(decision, (after, after))
    # Keep citation to doc13 but bump mtime after correction
    impl.write_text(
        "# 15-IMPLEMENTATION-PRECONDITIONS.md (AUD-0074 good-state)\n\n"
        f"Post-correction consumer of `{DOC13}` (MECH-NN namespace).\n\n"
        f"## Citations\n- depends on `{DOC13}`\n- depends on `14-NO-REGRESSION-CONTRACT.md`\n",
        encoding="utf-8",
        newline="\n",
    )
    os.utime(impl, (after, after))

    good_raw = HERE / "control-good-probe2.raw.txt"
    good_json = HERE / "control-good-probe2.json"
    # Need probe1 edges refreshed (same citations) then probe2
    run_py(PROBE1, HERE / "_tmp_p1_good.raw.txt", HERE / "_tmp_p1_good.json")
    # Point probe2 at good edges file
    shutil.copy(HERE / "_tmp_p1_good.json", HERE / "probe1-citation-edges.json")
    rcg, outg = run_py(PROBE2, good_raw, good_json)
    p2g = json.loads(good_json.read_text(encoding="utf-8"))
    good_flags = int(p2g.get("doc13_stale_downstream_flag_count") or 0)

    # Restore bad/planted corpus for the packed receipt (control asserts against bad)
    decision.write_text(bad_decision, encoding="utf-8", newline="\n")
    impl.write_text(bad_impl, encoding="utf-8", newline="\n")
    before = corr - 86400 * 2
    os.utime(decision, (before, before))
    os.utime(impl, (before, before))
    # Restore probe1/2 outputs to bad-state measurements
    run_py(
        PROBE1,
        HERE / "probe1-citation-edges.raw.txt",
        HERE / "probe1-citation-edges.json",
    )
    run_py(
        PROBE2,
        HERE / "probe2-timestamp-ordering.raw.txt",
        HERE / "probe2-timestamp-ordering.json",
    )

    fired_bad = bad_flags >= 1
    silent_good = good_flags == 0
    ok = fired_bad and silent_good

    result = {
        "unit": "AUD-0074",
        "control": "doc13-correction-stale-downstream",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "bad_state_doc13_stale_flags": bad_flags,
        "bad_state_flags": bad_flag_rows,
        "good_state_doc13_stale_flags": good_flags,
        "fired_on_bad_state": fired_bad,
        "silent_on_good_state": silent_good,
        "ok": ok,
        "note": (
            "Zero flags on the known doc-13 correction case means the timestamp "
            "check is inert."
        ),
        "probe1_rc": rc1,
        "probe2_rc": rc2,
        "good_probe2_rc": rcg,
    }

    raw_lines = [
        "AUD-0074 CONTROL: known doc-13 correction must produce >=1 stale-downstream flag",
        f"CAPTURED_AT={result['captured_at']}",
        f"BAD_DOC13_STALE_FLAGS={bad_flags}",
        f"GOOD_DOC13_STALE_FLAGS={good_flags}",
        f"FIRED_ON_BAD={fired_bad}",
        f"SILENT_ON_GOOD={silent_good}",
        f"CONTROL_OK={ok}",
    ]
    for f in bad_flag_rows:
        raw_lines.append(f"BAD_FLAG|{json.dumps(f, sort_keys=True)}")
    raw_lines.append("SUCCESS:AUD-0074-control" if ok else "FAILED:AUD-0074-control")
    raw = "\n".join(raw_lines) + "\n"
    args.raw_output.write_text(raw, encoding="utf-8", newline="\n")
    args.result_json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(raw, end="")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
