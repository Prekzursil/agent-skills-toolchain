#!/usr/bin/env python3
"""Probe 2: independent orphan-figure scan, both-states control, empty ledger.

The reviewer path does not call report.extract_figures_from_text. It parses
JSON figures arrays and markdown run_ids= attributes with its own regex, then
resolves those run ids against the ledger index.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.bench import ledger as L  # noqa: E402
from tools.bench import report as R  # noqa: E402

LEDGER = REPO / "command-center" / "bench" / "results" / "runs.jsonl"
INDEX = REPO / "command-center" / "bench" / "report-index.json"
PUBLISHED = REPO / "command-center" / "bench" / "published"

# Independent of tools.bench.report.FIG_RE (which uses <!--fig ... -->).
INDEP_JSON_RUN = re.compile(r'"run_ids"\s*:\s*\[(.*?)\]', re.DOTALL)
INDEP_MD_RUN = re.compile(r'run_ids="([^"]*)"')
INDEP_MD_VALUE = re.compile(r'value="([^"]*)"')


def fail(msg: str) -> int:
    print(f"FAILED:TST-0310-probe2 {msg}")
    return 1


def independent_run_ids_from_json(text: str) -> list[str]:
    found: list[str] = []
    for blob in INDEP_JSON_RUN.findall(text):
        found.extend(re.findall(r'"([^"]+)"', blob))
    return found


def independent_run_ids_from_markdown(text: str) -> list[str]:
    found: list[str] = []
    for blob in INDEP_MD_RUN.findall(text):
        found.extend([p for p in blob.split(",") if p])
    return found


def resolve_against_ledger(run_ids: list[str], by_id: dict) -> list[str]:
    return [rid for rid in run_ids if rid not in by_id]


def main() -> int:
    rows = L.load_ledger(LEDGER)
    by_id = L.index_by_run_id(rows)
    if len(by_id) != 9:
        return fail(f"expected 9 ledger rows, got {len(by_id)}")

    live = R.check(LEDGER, PUBLISHED, INDEX)
    if not live.ok:
        return fail(f"live published tree is red {live.as_dict()}")

    indep_ids: list[str] = []
    for name in ("leaderboard.json", "dashboard.json", "leaderboard.md", "report.md"):
        path = PUBLISHED / name
        text = path.read_text(encoding="utf-8")
        if name.endswith(".json"):
            indep_ids.extend(independent_run_ids_from_json(text))
        else:
            indep_ids.extend(independent_run_ids_from_markdown(text))
    missing = resolve_against_ledger(indep_ids, by_id)
    if missing:
        return fail(f"independent scan found unresolved run ids {sorted(set(missing))}")
    if not indep_ids:
        return fail("independent scan found zero run ids on live published tree")
    print(
        f"independent_live run_id_mentions={len(indep_ids)} "
        f"unique={len(set(indep_ids))} unresolved=0"
    )

    with tempfile.TemporaryDirectory(prefix="tst0310-p2-") as tmp:
        tmp_path = Path(tmp)
        published = tmp_path / "published"
        R.generate(LEDGER, published)

        green = R.check(LEDGER, published, INDEX)
        if not green.ok:
            return fail(f"scratch generate was red {green.as_dict()}")
        print(f"both_states green ok=True unresolved={green.figures_unresolved}")

        stray = tmp_path / "stray-notes.md"
        stray.write_text(
            (
                "# stray notes\n\n"
                "Observed accuracy was "
                '<!--fig id="pasted.accuracy" value="0.999" '
                'run_ids="run-not-in-ledger" kind="cell"-->'
                "0.999<!--/fig-->.\n"
            ),
            encoding="utf-8",
            newline="\n",
        )
        # Independent detection (does not call report.extract_figures_from_text).
        stray_ids = independent_run_ids_from_markdown(stray.read_text(encoding="utf-8"))
        stray_missing = resolve_against_ledger(stray_ids, by_id)
        if stray_ids != ["run-not-in-ledger"] or not stray_missing:
            return fail(f"independent parser missed planted orphan ids={stray_ids}")

        red = R.check(LEDGER, published, INDEX, extra_scan=[stray])
        if red.ok:
            return fail("gate stayed green with planted orphan figure")
        if red.figures_unresolved < 1:
            return fail(f"orphan did not increment unresolved {red.as_dict()}")
        print(
            f"both_states red ok=False unresolved={red.figures_unresolved} "
            f"reasons={red.reasons}"
        )

        empty_ledger = tmp_path / "empty.jsonl"
        empty_ledger.write_text("", encoding="utf-8")
        empty_pub = tmp_path / "empty-pub"
        empty_files = R.generate(empty_ledger, empty_pub)
        if "0.940" in empty_files["leaderboard.md"] or "0.940" in empty_files["report.md"]:
            return fail("empty ledger still emitted fused accuracy 0.940")
        empty_check = R.check(empty_ledger, empty_pub, INDEX)
        if not empty_check.ok:
            return fail(f"empty ledger generate was red {empty_check.as_dict()}")
        if empty_check.ledger_rows != 0:
            return fail(f"empty ledger_rows={empty_check.ledger_rows}")
        print(
            f"empty_ledger rows=0 ok=True figures_checked={empty_check.figures_checked} "
            f"unresolved={empty_check.figures_unresolved}"
        )

    payload = {
        "independent_unresolved": 0,
        "independent_run_id_mentions": len(indep_ids),
        "both_states_green": True,
        "both_states_red": True,
        "planted_orphan_detected_independently": True,
        "empty_ledger_no_fake_figures": True,
        "live_figures_checked": live.figures_checked,
        "live_figures_unresolved": live.figures_unresolved,
        "reviewer_id": "TST-0310-probe2-independent-orphan-scan",
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:TST-0310-probe2 orphan scan, both-states, empty ledger")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
