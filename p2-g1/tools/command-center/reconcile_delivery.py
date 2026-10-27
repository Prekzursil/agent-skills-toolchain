"""Reconcile the 2,007 declared work units against what was actually DELIVERED.

The problem this exists to answer, from `command-center/P13-BLINDSPOT-REVIEW.md`:

    1 of 2,007 catalogued work units has produced the artifact it declared.

That number is correct and it is also badly misleading on its own. Two mechanically
independent probes agreed on it (per-path `stat()`, and set-intersection against 8,911
git-tracked files), so the *measurement* is sound. But the conclusion a reader reaches from
"1 of 2,007" -- that essentially nothing was built -- is contradicted by the same review's
own text: the repo holds 8,911 tracked files, a green suite, and shipped plugin, marketplace,
routing and coordination phases. The delivered work is real. It simply landed in a different
path namespace from the one the plan declared, and **nothing in the repo maps between them**.

So the honest open question is not "was the work done" but "which declared unit, if any, does
each delivered artifact satisfy" -- and that question has never been asked mechanically.

WHY THIS IS AN ALGORITHM AND NOT A FAN-OUT
------------------------------------------
`rules/common/fan-out-contract.md` section C4 measured this exact shape: six Opus agents
classifying 338 files scored 86% accuracy, and **every one of the 47 disagreements pointed in
the data-loss direction** because a one-directional read cannot see two-directional
divergence. A declared-vs-delivered match is set membership and string comparison. It is
therefore written as code, exactly, and agents are reserved for the residual cases where
judgement is genuinely required.

DISPOSITIONS, weakest evidence last
-----------------------------------
  DELIVERED-AT-DECLARED-PATH  the declared output_path exists and is non-empty.
  DELIVERED-ELSEWHERE-EXACT   a file with the identical basename exists somewhere tracked.
                              Strong: the plan named the artifact, the artifact exists, only
                              the directory differs.
  DELIVERED-ELSEWHERE-STEM    a tracked file's stem matches the declared stem case-folded
                              and separator-folded. Weaker; a stem can collide.
  UNIT-ID-REFERENCED          no filename match, but the unit's own id appears in tracked
                              content. Evidence the unit was *worked on*, NOT that its
                              artifact exists. Deliberately a distinct verdict, because
                              folding it into a DELIVERED bucket is how a program talks
                              itself into a completion number it did not earn.
  NOT-PRODUCED                none of the above. The honest default.

Ambiguity is preserved rather than resolved: a declared basename matching several tracked
files is recorded with every candidate, so a human or an agent can adjudicate. Silently
picking the first would manufacture certainty.

FAIL CLOSED (`rules/common/ci-hygiene.md` section 1): zero units, an unreadable catalog, or an
empty git file list is a failure, never "nothing found -> pass".
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

if __package__ in (None, ""):  # pragma: no cover - import shim for direct runs
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalog as cat


def _fold(name: str) -> str:
    """Case- and separator-fold a filename stem so `WAVE4_FOO` and `wave4-foo` agree."""
    return name.lower().replace("_", "-").replace(" ", "-")


#: Documents that DECLARE the work units. A unit id appearing in one of these is a
#: restatement of the plan, not evidence the unit was executed, so they are excluded from
#: the id-mention evidence set. See the use-vs-mention note in `reconcile()`.
DECLARING_DOCS = (
    "command-center/WORK-UNIT-CATALOG.json",
    "command-center/catalog-slices/",
    "command-center/CATALOG-INTEGRITY.json",
    "command-center/DELIVERY-RECONCILIATION.json",  # this tool's own output
    "command-center/DEPENDENCY-GRAPH.json",
)


def _is_declaring_doc(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    return any(rel == entry or rel.startswith(entry) for entry in DECLARING_DOCS)


def tracked_files(root: Path) -> list[str]:
    """Every git-tracked path, as forward-slash repo-relative strings."""
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def declared_units(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    return [u for u in (catalog.get("work_units") or []) if isinstance(u, dict)]


def _nonempty(root: Path, rel: str) -> bool:
    path = root / rel
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def reconcile(root: Path, catalog: dict[str, Any]) -> dict[str, Any]:
    units = declared_units(catalog)
    if not units:
        raise ValueError("catalog holds zero work units (fail closed)")
    files = tracked_files(root)
    if not files:
        raise ValueError("git ls-files returned nothing (fail closed)")

    by_base: dict[str, list[str]] = defaultdict(list)
    by_stem: dict[str, list[str]] = defaultdict(list)
    for rel in files:
        base = rel.rsplit("/", 1)[-1]
        by_base[base].append(rel)
        by_stem[_fold(base.rsplit(".", 1)[0])].append(rel)

    # One pass over tracked text to find which unit ids are mentioned anywhere. Reading the
    # tree once and testing membership beats 2,007 greps, and it is exact rather than
    # heuristic.
    #
    # USE-VS-MENTION, and it is not hypothetical here. The first run of this function scored
    # UNIT-ID-REFERENCED on 1,977 of 2,007 units -- which is 100% of every unit that reached
    # that branch. A detector that fires on everything it sees is measuring itself. The cause:
    # `WORK-UNIT-CATALOG.json` is a tracked file that CONTAINS all 2,007 ids by construction,
    # as do the per-phase slices it was merged from, so "this id appears in tracked content"
    # was really "this id appears in the plan that declares it" -- true of every unit, and
    # evidence of nothing. The plan is excluded from the evidence set; only a mention OUTSIDE
    # the declaring documents is evidence the unit was worked on.
    ids = {str(u.get("id", "")).strip() for u in units if str(u.get("id", "")).strip()}
    mentioned: set[str] = set()
    scanned = 0
    skipped_declaring = 0
    for rel in files:
        if _is_declaring_doc(rel):
            skipped_declaring += 1
            continue
        path = root / rel
        try:
            if path.stat().st_size > 4_000_000:
                continue
            blob = path.read_bytes()
        except OSError:
            continue
        if b"\0" in blob[:2048]:  # binary; ids do not live there
            continue
        scanned += 1
        text = blob.decode("utf-8", "replace")
        for uid in ids:
            if uid and uid in text:
                mentioned.add(uid)

    rows: list[dict[str, Any]] = []
    for unit in units:
        uid = str(unit.get("id", "")).strip()
        declared = str(unit.get("output_path", "") or "").strip().replace("\\", "/")
        row: dict[str, Any] = {
            "id": uid,
            "phase": unit.get("phase"),
            "declared_output_path": declared or None,
        }
        if declared and _nonempty(root, declared):
            row["disposition"] = "DELIVERED-AT-DECLARED-PATH"
            row["evidence"] = declared
            rows.append(row)
            continue

        base = declared.rsplit("/", 1)[-1] if declared else ""
        exact = [c for c in by_base.get(base, []) if c != declared] if base else []
        if exact:
            row["disposition"] = "DELIVERED-ELSEWHERE-EXACT"
            row["candidates"] = sorted(exact)
            row["ambiguous"] = len(exact) > 1
            rows.append(row)
            continue

        stem = _fold(base.rsplit(".", 1)[0]) if base else ""
        near = [c for c in by_stem.get(stem, []) if c != declared] if stem else []
        if near:
            row["disposition"] = "DELIVERED-ELSEWHERE-STEM"
            row["candidates"] = sorted(near)
            row["ambiguous"] = len(near) > 1
            rows.append(row)
            continue

        if uid in mentioned:
            row["disposition"] = "UNIT-ID-REFERENCED"
            row["caveat"] = (
                "the unit id appears in tracked content, which is evidence the unit was "
                "worked on and NOT evidence its declared artifact exists"
            )
            rows.append(row)
            continue

        row["disposition"] = "NOT-PRODUCED"
        rows.append(row)

    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["disposition"]] += 1
    ambiguous = sum(1 for row in rows if row.get("ambiguous"))

    delivered = (
        counts["DELIVERED-AT-DECLARED-PATH"]
        + counts["DELIVERED-ELSEWHERE-EXACT"]
        + counts["DELIVERED-ELSEWHERE-STEM"]
    )
    return {
        "artifact": "DELIVERY-RECONCILIATION",
        "derivation": "tools/command-center/reconcile_delivery.py",
        "question": (
            "for each of the catalogue's declared work units, does a delivered artifact "
            "satisfy it, and where"
        ),
        "units_total": len(units),
        "tracked_files": len(files),
        "text_files_scanned_for_ids": scanned,
        "declaring_docs_excluded_from_id_scan": skipped_declaring,
        "counts": dict(sorted(counts.items())),
        "ambiguous_matches": ambiguous,
        "delivered_any_form": delivered,
        "delivered_pct": round(100.0 * delivered / len(units), 2),
        "interpretation": {
            "at_declared_path_only": counts["DELIVERED-AT-DECLARED-PATH"],
            "note": (
                "`delivered_any_form` counts filename evidence, not verified content. A "
                "basename match proves an artifact of that NAME exists somewhere tracked; it "
                "does not prove that artifact satisfies the unit's evidence_requirement or "
                "its completion_sentinel. Treat it as an upper bound on delivery and the "
                "at-declared-path count as the lower bound. UNIT-ID-REFERENCED is in neither."
            ),
        },
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--catalog", default=str(cat.catalog_path()))
    parser.add_argument("--out", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    root = cat.repo_root()
    try:
        catalog = cat.load(args.catalog)
        report = reconcile(root, catalog)
    except Exception as exc:
        print(f"FAILED:cc-reconcile {exc}")
        return 1

    out = (
        Path(args.out)
        if args.out
        else root / "command-center" / "DELIVERY-RECONCILIATION.json"
    )
    cat.save(report, out)

    if args.json:
        slim = {k: v for k, v in report.items() if k != "rows"}
        print(json.dumps(slim, indent=2, sort_keys=True))
    else:
        for key, value in report["counts"].items():
            print(f"  {key:32s} {value}")
        print(
            f"  ambiguous (name matched >1 tracked file) {report['ambiguous_matches']}"
        )
    print(
        f"SUCCESS:cc-reconcile units={report['units_total']} "
        f"delivered_any_form={report['delivered_any_form']} "
        f"({report['delivered_pct']}%) at_declared_path="
        f"{report['interpretation']['at_declared_path_only']} -> {os.path.relpath(out, root)}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
