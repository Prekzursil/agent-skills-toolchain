"""Every committed copy of a vendored package must match its single CI-gated source of truth.

THE HOLE THIS CLOSES, measured 2026-08-12 at 4d421333. `monitorcore` is VENDORED: consuming
skills carry a committed copy because `sync-skills.ps1` deploys committed skill dirs wholesale,
so a skill cannot `pip install` its way to the package. Three copies are tracked today:

    tools/monitorcore/monitorcore              37 files   <- the CI-gated source of truth
    skills/workflow-monitor/monitorcore        37 files
    .agents/skills/workflow-monitor/monitorcore 37 files

`.github/workflows/quality.yml` diffs exactly ONE pair (`tools/...` against
`skills/workflow-monitor/...`, at the `monitorcore vendor-drift` step). The `.agents` copy is
named in NO workflow. Detector control for that absence, run with a positive control so the
silence means something: `grep -c "skills/workflow-monitor/monitorcore" quality.yml` = 1 (the
matcher fires) and `grep -c "\\.agents/skills/workflow-monitor" quality.yml` = 0. So a change
landing in `tools/` + `skills/` passes CI while the `.agents` copy silently rots.

Hardcoding the second path would close today's hole and leave tomorrow's: a FOURTH copy would
arrive equally ungated. This DISCOVERS copies instead - every tracked `*/<package>/__init__.py`
is a copy and must match - so the gate cannot fall behind the tree.

WHY INDEX OIDs AND NOT `diff -r`. `diff -r` compares WORKING-TREE bytes. On this box the working
tree is CRLF and the committed blob is LF (`blobread.py` documents the measurement), so a
worktree comparison answers a question CI never asks. `git ls-files -s` hands back the blob OID
git actually stored, which is exactly what a fresh clone materialises. Equal OID is a proof of
byte-identity that costs one git call for the whole tree; no file is read unless its OID already
differs.

THE TRAP AVOIDED IN THE CONTENT PATH: having discovered a difference from the INDEX, it would be
natural to fetch the bytes with `git cat-file -p HEAD:<path>` - and that mixes two states. A path
can be staged and not yet committed, so it appears in `ls-files -s` and is absent from `HEAD:`;
worse, a modified-and-staged file would be classified from STALE committed bytes and could be
reported as identical when the index says otherwise. Blobs are therefore read BY OID, the same
state the discovery used.

CRLF-ONLY DRIFT IS STILL DRIFT, and is reported as its own class rather than exempted. Two
committed blobs that differ only in line endings really are different bytes in a fresh Linux
clone; the class exists so the fixer knows to reach for `.gitattributes` rather than hunt a
logic change.

FAIL CLOSED, three ways: an empty `git ls-files`, a source of truth with zero files, and zero
vendored copies discovered all FAIL. "0 drift" must never be reachable by having found nothing
to compare - the silent-no-op shape `suitefloor.py` and `refcheck.py` guard against for tests
and for document references.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from blobread import lf_normalised

REPO = Path(__file__).resolve().parents[2]

#: The vendored package this gate ships configured for.
DEFAULT_PACKAGE = "monitorcore"

#: The one copy CI type-checks and covers; every other copy is measured against it.
DEFAULT_SOURCE = "tools/monitorcore/monitorcore"

#: Below this, assume discovery broke rather than that the vendoring was undone. 2 observed at
#: 4d421333, so the floor carries one copy of margin - a floor set to the exact current count is a
#: nuisance gate that fails the moment a copy is legitimately retired, and a nuisance gate gets
#: deleted.
MIN_COPIES = 1


class VendorDriftError(RuntimeError):
    """Discovery collapsed: the gate cannot honestly report anything."""


def index_oids(repo: Path) -> dict[str, str]:
    """Every tracked path mapped to the blob OID git stored for it.

    `-z` rather than plain `-s`: without it git applies `core.quotePath` and wraps any path with
    a non-ASCII or unusual byte in quotes, which would silently drop that file from the walk.
    """
    proc = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-s", "-z"],
        capture_output=True,
        check=False,
    )
    oids: dict[str, str] = {}
    for record in proc.stdout.decode("utf-8", "surrogateescape").split("\0"):
        meta, tab, path = record.partition("\t")
        if not tab:
            continue
        fields = meta.split()
        if len(fields) == 3:
            oids[path] = fields[1]
    return oids


def read_oid(repo: Path, oid: str) -> bytes | None:
    """The stored bytes of a blob, addressed by OID. None if git refuses.

    Deliberately NOT `blobread.read_blob`, which addresses `<rev>:<path>` and so answers about a
    COMMIT. This gate discovered the difference in the INDEX and must read the same state back or
    the two halves can disagree.
    """
    proc = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-p", oid],
        capture_output=True,
        check=False,
    )
    return proc.stdout if proc.returncode == 0 else None


def find_copies(paths: set[str], package: str, source: str) -> list[str]:
    """Every tracked directory that is a copy of `package`, excluding the source of truth."""
    leaf = f"{package}/__init__.py"
    roots: set[str] = set()
    for path in paths:
        if path == leaf or path.endswith("/" + leaf):
            roots.add(path[: -len("/__init__.py")])
    roots.discard(source)
    return sorted(roots)


def _members(oids: dict[str, str], root: str) -> dict[str, str]:
    prefix = root + "/"
    return {p[len(prefix) :]: o for p, o in oids.items() if p.startswith(prefix)}


def compare(
    repo: Path, oids: dict[str, str], source: str, copy: str
) -> dict[str, object]:
    """One copy against the source of truth, splitting real drift from a line-ending phantom."""
    src = _members(oids, source)
    got = _members(oids, copy)

    crlf_only: list[str] = []
    content: list[str] = []
    for rel in sorted(set(src) & set(got)):
        if src[rel] == got[rel]:
            continue
        left = read_oid(repo, src[rel])
        right = read_oid(repo, got[rel])
        if (
            left is not None
            and right is not None
            and lf_normalised(left) == lf_normalised(right)
        ):
            crlf_only.append(rel)
        else:
            # An unreadable blob lands here on purpose: "we could not prove it is only line
            # endings" must degrade to the LOUDER class, never to the quieter one.
            content.append(rel)

    return {
        "path": copy,
        "files": len(got),
        "missing": sorted(set(src) - set(got)),
        "extra": sorted(set(got) - set(src)),
        "crlf_only": crlf_only,
        "content": content,
    }


def _drift_count(entry: dict[str, object]) -> int:
    total = 0
    for key in ("missing", "extra", "crlf_only", "content"):
        value = entry[key]
        assert isinstance(value, list)
        total += len(value)
    return total


def scan(
    repo: Path | None = None,
    package: str = DEFAULT_PACKAGE,
    source: str = DEFAULT_SOURCE,
) -> dict[str, object]:
    root = repo or REPO
    oids = index_oids(root)
    if not oids:
        raise VendorDriftError("git ls-files returned nothing (fail closed)")

    src = _members(oids, source)
    if not src:
        raise VendorDriftError(
            f"source of truth {source!r} has no tracked files (fail closed)"
        )

    copies = find_copies(set(oids), package, source)
    if len(copies) < MIN_COPIES:
        raise VendorDriftError(
            f"discovered {len(copies)} vendored copy/copies of {package!r}, below the floor of "
            f"{MIN_COPIES}; discovery has probably broken rather than the vendoring been undone"
        )

    entries = [compare(root, oids, source, copy) for copy in copies]
    return {
        "package": package,
        "source": source,
        "source_files": len(src),
        "copies": entries,
        "total_drift": sum(_drift_count(e) for e in entries),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--package", default=DEFAULT_PACKAGE)
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = scan(package=args.package, source=args.source)
    except VendorDriftError as exc:
        print(f"FAILED:vendordrift {exc}")
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))

    copies = report["copies"]
    assert isinstance(copies, list)
    drifted = 0
    for entry in copies:
        count = _drift_count(entry)
        if not count:
            continue
        drifted += 1
        for key, label in (
            ("missing", "MISSING  (in source, absent from copy)"),
            ("extra", "EXTRA    (in copy, absent from source)"),
            ("crlf_only", "CRLF-ONLY(line endings differ in the committed blob)"),
            ("content", "CONTENT  (the committed bytes really differ)"),
        ):
            for rel in entry[key]:
                print(f"  {label}  {entry['path']}/{rel}")

    if drifted:
        print(
            f"FAILED:vendordrift {report['total_drift']} drifted path(s) across {drifted} of "
            f"{len(copies)} vendored copy/copies of {report['package']!r}; a consumer ships bytes "
            f"that {report['source']} no longer has"
        )
        return 1

    print(
        f"SUCCESS:vendordrift {len(copies)} vendored copy/copies of {report['package']!r} match "
        f"{report['source']} ({report['source_files']} files each)"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
