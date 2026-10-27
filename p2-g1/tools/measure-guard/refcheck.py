"""Every `subworkflows[].source` in a tracked document must resolve inside the repo.

THE DEFECT THIS GATE EXISTS FOR, measured 2026-08-10: three committed blueprints
(`bp-pln-02`, `bp-pln-03`, `bp-pln-04`) referenced
`platform/workflows/_shared/shared.pairwise-overlap-matrix.subworkflow.json` and
`shared.write-as-you-go-artifact.subworkflow.json`, and neither file was in version control. Every
commit script in the program excluded `/_` paths as agent scratch, so a fresh clone got blueprints
pointing at files that do not exist while the working tree looked complete.

WHY IT KEYS ON THE JSON PATH AND NOT ON THE FIELD NAME `source`. A gate over the NAME is invalid,
because `source` is polymorphic in this corpus - four distinct meanings measured:

    subworkflows[].source          a RUNTIME dependency          must resolve  <- gated here
    lineage.derived_from[].source  provenance / attribution      should resolve
    constraints[].source           a citation WITH A LOCATOR     free text by design
    lane_comparison_*.source       the document SET an audit read may name several

`constraints[].source` is the decisive one: the schema embedded in the very document that carries it
declares it as "The document or measurement it came from; empty means UNSOURCED", and three of that
file's four real values are not paths at all (`spawn brief`, `AGENTS.md 9` twice). A name-keyed gate
could only go green by corrupting values that conform to their own contract, or by special-casing
until it measured nothing.

EXCLUSION, and it is the only one. `platform/lib/wfdsl/examples/` holds schema-conformance fixtures.
`wf-full-coverage.json` self-describes as "The conformance workhorse: one workflow that exercises
every capability the spec requires of the DSL", and its `subworkflows.source` exists to COVER the
schema field: measured, `platform/lib/wfdsl/semantics.py:658,672` reads `subworkflows` only as a set
of declared NAMES to cross-check `workflow_id`, and nothing anywhere opens the path. Creating that
file would satisfy no consumer and would add a phantom blueprint to the corpus.

FAIL CLOSED. Zero references found is a FAILURE, not a pass - if the walk stops finding them the gate
has stopped measuring, which is the same class of silent no-op `suitefloor` guards against for tests.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

#: Directories whose `subworkflows[].source` values are schema fixtures rather than dependencies.
FIXTURE_DIRS = ("platform/lib/wfdsl/examples/",)

#: Below this, assume the walk broke rather than that the corpus shrank. 17 observed at 15cb70e3.
MIN_REFERENCES = 12


def tracked(repo: Path) -> set[str]:
    out = subprocess.run(
        ["git", "-C", str(repo), "ls-files"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return {line.strip() for line in out.splitlines() if line.strip()}


def _dirs_of(paths: set[str]) -> set[str]:
    """Directory prefixes, so a `source` naming a directory resolves as well as one naming a file."""
    out: set[str] = set()
    for path in paths:
        parts = path.split("/")
        for i in range(1, len(parts)):
            out.add("/".join(parts[:i]))
    return out


def _sources(node: object) -> list[tuple[str, str]]:
    """Every (declared_name, source) under any `subworkflows` container, dict or list form."""
    found: list[tuple[str, str]] = []
    if isinstance(node, dict):
        subs = node.get("subworkflows")
        specs: list[tuple[str, object]] = []
        if isinstance(subs, dict):
            specs = list(subs.items())
        elif isinstance(subs, list):
            specs = [
                (str(s.get("workflow_id", "?")), s) for s in subs if isinstance(s, dict)
            ]
        for name, spec in specs:
            if isinstance(spec, dict) and isinstance(spec.get("source"), str):
                found.append((name, spec["source"]))
        for value in node.values():
            found.extend(_sources(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_sources(item))
    return found


def scan(repo: Path | None = None) -> dict[str, object]:
    root = repo or REPO
    files = tracked(root)
    if not files:
        raise ValueError("git ls-files returned nothing (fail closed)")
    dirs = _dirs_of(files)

    checked = 0
    skipped_fixture = 0
    dangling: list[dict[str, str]] = []
    for rel in sorted(f for f in files if f.endswith(".json")):
        if rel.startswith(FIXTURE_DIRS):
            skipped_fixture += 1
            continue
        path = root / rel
        try:
            if path.stat().st_size > 4_000_000:
                continue
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError):
            continue
        for name, raw in _sources(doc):
            target = raw.replace("\\", "/")
            checked += 1
            if target not in files and target not in dirs:
                dangling.append(
                    {"referrer": rel, "declared_name": name, "source": target}
                )

    return {
        "references_checked": checked,
        "fixture_files_skipped": skipped_fixture,
        "dangling": dangling,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = scan()
    except ValueError as exc:
        print(f"FAILED:refcheck {exc}")
        return 1

    checked = int(report["references_checked"])
    dangling = report["dangling"]
    assert isinstance(dangling, list)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))

    # Fail closed on a collapsed walk BEFORE reporting success, so "0 dangling" can never come from
    # having found nothing to check.
    if checked < MIN_REFERENCES:
        print(
            f"FAILED:refcheck only {checked} subworkflows[].source reference(s) found, below the "
            f"floor of {MIN_REFERENCES}; the walk has probably broken rather than the corpus shrunk"
        )
        return 1

    for entry in dangling:
        print(
            f"  DANGLING {entry['source']}  <- {entry['referrer']} "
            f"(declared as {entry['declared_name']})"
        )
    if dangling:
        print(
            f"FAILED:refcheck {len(dangling)} of {checked} subworkflows[].source reference(s) do not "
            "resolve; a committed document depends on a path a fresh clone will not have"
        )
        return 1
    print(f"SUCCESS:refcheck {checked} subworkflows[].source reference(s) all resolve")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
