"""Fixture oracle for :mod:`plugin.three_way_merge` (IMP-0031 signal 1).

Every fixture is a *triple* ``(base, ours, theirs)`` plus a hand-authored
expectation: the exact merged bytes for a clean merge, the exact bytes and
the conflict regions for a conflicting merge, or ``refused`` for binary
content.  :func:`run_all` merges each triple with the production entry point
:func:`plugin.three_way_merge.merge_bytes` and compares byte-for-byte, so a
merger that silently overwrites, reorders, drops a comment or hides a conflict
fails the oracle.

The seven built-in triples cover the strategies the unit promises: JSON
structural (additive keys; nested disjoint edits plus a same-key conflict; the
reviewer's key-reorder-with-leading-comment triple), TOML structural, markdown
line diff3 (additive and conflicting) and binary refuse-with-report.  When a
fixture tree exists at ``tests/fixtures/three_way/manifest.json`` it is used
instead (see :func:`load_fixtures`), and :func:`write_fixture_tree` can
materialise the built-in set there for hand inspection.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from plugin.three_way_merge import MergeResult, merge_bytes

__all__ = [
    "FIXTURE_ROOT",
    "FixtureTriple",
    "MANIFEST_NAME",
    "builtin_fixtures",
    "check_fixture",
    "load_fixtures",
    "main",
    "run_all",
    "write_fixture_tree",
]

FIXTURE_ROOT = Path(__file__).resolve().parent / "tests" / "fixtures" / "three_way"
MANIFEST_NAME = "manifest.json"
_SIDES = ("base", "ours", "theirs")


@dataclass(frozen=True)
class FixtureTriple:
    """One hand-authored merge case."""

    name: str
    path: str
    base: bytes
    ours: bytes
    theirs: bytes
    expected_status: str
    expected_strategy: str
    expected: bytes | None = None
    conflict_regions: tuple[str, ...] = ()
    note: str = ""

    def to_manifest_row(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "expected_status": self.expected_status,
            "expected_strategy": self.expected_strategy,
            "conflict_regions": list(self.conflict_regions),
            "note": self.note,
        }


def _b(text: str) -> bytes:
    return text.encode("utf-8")


def builtin_fixtures() -> list[FixtureTriple]:
    """The seven hand-authored triples shipped with the oracle."""
    fixtures: list[FixtureTriple] = []

    # 1. JSON structural: each side adds its own key; nothing is lost, ours order first.
    fixtures.append(
        FixtureTriple(
            name="json-additive-keys",
            path="settings.json",
            base=_b('{\n  "alpha": 1,\n  "beta": 2\n}\n'),
            ours=_b('{\n  "alpha": 1,\n  "beta": 2,\n  "timeout": 30\n}\n'),
            theirs=_b('{\n  "alpha": 1,\n  "beta": 2,\n  "gamma": 3\n}\n'),
            expected_status="merged",
            expected_strategy="json",
            expected=_b(
                '{\n  "alpha": 1,\n  "beta": 2,\n  "timeout": 30,\n  "gamma": 3\n}\n'
            ),
            note="user-added timeout and shipped gamma both survive",
        )
    )

    # 2. JSON structural: disjoint nested edits merge; the same-key edit conflicts
    #    and the merge keeps ours while recording the region.
    fixtures.append(
        FixtureTriple(
            name="json-nested-disjoint-plus-conflict",
            path="config.json",
            base=_b(
                '{\n  "server": {\n    "host": "localhost",\n    "port": 8080\n  },\n'
                '  "debug": false,\n  "level": "info"\n}\n'
            ),
            ours=_b(
                '{\n  "server": {\n    "host": "localhost",\n    "port": 9090\n  },\n'
                '  "debug": false,\n  "level": "debug"\n}\n'
            ),
            theirs=_b(
                '{\n  "server": {\n    "host": "0.0.0.0",\n    "port": 8080\n  },\n'
                '  "debug": true,\n  "level": "warn"\n}\n'
            ),
            expected_status="conflict",
            expected_strategy="json",
            expected=_b(
                '{\n  "server": {\n    "host": "0.0.0.0",\n    "port": 9090\n  },\n'
                '  "debug": true,\n  "level": "debug"\n}\n'
            ),
            conflict_regions=("level",),
            note="host<-theirs, port<-ours, debug<-theirs; level edited on both sides",
        )
    )

    # 3. Reviewer adversarial triple: key reorder + leading // comment on ours.
    fixtures.append(
        FixtureTriple(
            name="json-reorder-comment-reviewer",
            path="settings.json",
            base=_b('{\n  "alpha": 1,\n  "beta": 2\n}\n'),
            ours=_b(
                "// owner: keep local timeout\n"
                '{\n  "beta": 2,\n  "alpha": 1,\n  "timeout": 30\n}\n'
            ),
            theirs=_b('{\n  "alpha": 1,\n  "beta": 2,\n  "gamma": 3\n}\n'),
            expected_status="merged",
            expected_strategy="json",
            expected=_b(
                "// owner: keep local timeout\n"
                '{\n  "beta": 2,\n  "alpha": 1,\n  "timeout": 30,\n  "gamma": 3\n}\n'
            ),
            note="reorder is not a conflict; comment and timeout survive, gamma arrives",
        )
    )

    # 4. TOML structural: ours adds a top-level scalar, theirs adds a table key.
    fixtures.append(
        FixtureTriple(
            name="toml-additive",
            path="config.toml",
            base=_b('name = "demo"\n\n[server]\nport = 8080\n'),
            ours=_b('name = "demo"\nverbose = true\n\n[server]\nport = 8080\n'),
            theirs=_b('name = "demo"\n\n[server]\nport = 8080\nhost = "127.0.0.1"\n'),
            expected_status="merged",
            expected_strategy="toml",
            expected=_b(
                'name = "demo"\nverbose = true\n\n[server]\nport = 8080\nhost = "127.0.0.1"\n'
            ),
            note="scalar added by ours and table key added by theirs both survive",
        )
    )

    # 5. Markdown line diff3: ours inserts a note near the top, theirs appends a section.
    base_md = "# Demo Plugin\n\nInstalls the demo skill.\n\n## Usage\n\nRun `demo`.\n"
    fixtures.append(
        FixtureTriple(
            name="markdown-line-additive",
            path="README.md",
            base=_b(base_md),
            ours=_b(
                "# Demo Plugin\n\nInstalls the demo skill.\nLocal note: pinned to v1.\n\n"
                "## Usage\n\nRun `demo`.\n"
            ),
            theirs=_b(base_md + "\n## Changelog\n\n- 1.1.0: added gamma.\n"),
            expected_status="merged",
            expected_strategy="line",
            expected=_b(
                "# Demo Plugin\n\nInstalls the demo skill.\nLocal note: pinned to v1.\n\n"
                "## Usage\n\nRun `demo`.\n\n## Changelog\n\n- 1.1.0: added gamma.\n"
            ),
            note="edits in different regions merge without markers",
        )
    )

    # 6. Markdown line diff3: both sides rewrite the same line -> conflict markers.
    fixtures.append(
        FixtureTriple(
            name="markdown-line-conflict",
            path="NOTES.md",
            base=_b("line A\nline B\nline C\n"),
            ours=_b("line A\nline B (ours)\nline C\n"),
            theirs=_b("line A\nline B (theirs)\nline C\n"),
            expected_status="conflict",
            expected_strategy="line",
            expected=_b(
                "line A\n<<<<<<< ours\nline B (ours)\n=======\nline B (theirs)\n>>>>>>> theirs\nline C\n"
            ),
            conflict_regions=("lines 2-2",),
            note="same line edited on both sides is surfaced, never silently overwritten",
        )
    )

    # 7. Binary: PNG-like blobs with NUL bytes are refused with a report.
    png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    fixtures.append(
        FixtureTriple(
            name="binary-refuse",
            path="icon.png",
            base=png + b"\x00\x01\x02\x03",
            ours=png + b"\x00\x01\x02\x04",
            theirs=png + b"\x00\x01\x02\x05",
            expected_status="refused",
            expected_strategy="binary",
            expected=None,
            note="binary content is refused with a size report, no bytes are invented",
        )
    )
    return fixtures


def _read_manifest(root: Path) -> list[FixtureTriple]:
    manifest = json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"))
    rows = manifest["fixtures"] if isinstance(manifest, dict) else manifest
    out: list[FixtureTriple] = []
    for row in rows:
        folder = root / str(row.get("dir") or row["name"])
        sides = {side: (folder / side).read_bytes() for side in _SIDES}
        expected_file = folder / "expected"
        expected = expected_file.read_bytes() if expected_file.is_file() else None
        out.append(
            FixtureTriple(
                name=str(row["name"]),
                path=str(row["path"]),
                base=sides["base"],
                ours=sides["ours"],
                theirs=sides["theirs"],
                expected_status=str(row["expected_status"]),
                expected_strategy=str(row["expected_strategy"]),
                expected=expected,
                conflict_regions=tuple(
                    str(r) for r in row.get("conflict_regions") or ()
                ),
                note=str(row.get("note") or ""),
            )
        )
    return out


def load_fixtures(root: str | Path | None = None) -> tuple[list[FixtureTriple], str]:
    """Return ``(fixtures, source)``; ``source`` is the manifest path or ``"builtin"``."""
    base = Path(root) if root is not None else FIXTURE_ROOT
    manifest = base / MANIFEST_NAME
    if manifest.is_file():
        return _read_manifest(base), str(manifest)
    return builtin_fixtures(), "builtin"


def write_fixture_tree(
    root: str | Path, fixtures: list[FixtureTriple] | None = None
) -> Path:
    """Materialise ``fixtures`` (default: built-in) as ``<root>/<name>/{base,ours,theirs,expected}``."""
    target = Path(root)
    target.mkdir(parents=True, exist_ok=True)
    rows = []
    for fx in fixtures or builtin_fixtures():
        folder = target / fx.name
        folder.mkdir(parents=True, exist_ok=True)
        for side in _SIDES:
            (folder / side).write_bytes(getattr(fx, side))
        if fx.expected is not None:
            (folder / "expected").write_bytes(fx.expected)
        rows.append(dict(fx.to_manifest_row(), dir=fx.name))
    (target / MANIFEST_NAME).write_text(
        json.dumps({"fixtures": rows}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target / MANIFEST_NAME


def _diff(expected: bytes, actual: bytes) -> str:
    exp = expected.decode("utf-8", "replace").splitlines(keepends=True)
    act = actual.decode("utf-8", "replace").splitlines(keepends=True)
    return "".join(difflib.unified_diff(exp, act, "expected", "actual"))[:2000]


def check_fixture(fx: FixtureTriple) -> dict[str, Any]:
    """Merge one triple and compare it with the hand-authored expectation."""
    result: MergeResult = merge_bytes(fx.base, fx.ours, fx.theirs, path=fx.path)
    reasons: list[str] = []
    if result.status != fx.expected_status:
        reasons.append(f"status {result.status!r} != {fx.expected_status!r}")
    if result.strategy != fx.expected_strategy:
        reasons.append(f"strategy {result.strategy!r} != {fx.expected_strategy!r}")
    regions = tuple(c.region for c in result.conflicts)
    if fx.expected_status == "conflict" and regions != fx.conflict_regions:
        reasons.append(
            f"conflict regions {list(regions)} != {list(fx.conflict_regions)}"
        )
    if fx.expected_status != "conflict" and result.conflicts:
        reasons.append(f"unexpected conflicts {list(regions)}")
    diff = ""
    if fx.expected is None:
        if result.data is not None or result.text is not None:
            reasons.append("refused merge produced output bytes")
        if not (result.report or {}).get("reason"):
            reasons.append("refusal carries no report reason")
    else:
        actual = (
            result.data
            if result.data is not None
            else (result.text or "").encode("utf-8")
        )
        if actual != fx.expected:
            reasons.append(
                f"merged bytes differ ({len(actual)} vs {len(fx.expected)} bytes)"
            )
            diff = _diff(fx.expected, actual)
    return {
        "name": fx.name,
        "path": fx.path,
        "strategy": result.strategy,
        "status": result.status,
        "expected_status": fx.expected_status,
        "conflict_regions": list(regions),
        "ok": not reasons,
        "reasons": reasons,
        "diff": diff,
        "note": fx.note,
    }


def run_all(
    fixtures: list[FixtureTriple] | None = None, root: str | Path | None = None
) -> dict[str, Any]:
    """Run every fixture; ``ok`` is True only when all of them pass byte-for-byte."""
    if fixtures is None:
        fixtures, source = load_fixtures(root)
    else:
        source = "explicit"
    rows = [check_fixture(fx) for fx in fixtures]
    failed = [row["name"] for row in rows if not row["ok"]]
    return {
        "fixtures": len(rows),
        "passed": len(rows) - len(failed),
        "failed": failed,
        "ok": not failed and bool(rows),
        "source": source,
        "strategies": sorted({row["strategy"] for row in rows}),
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="three-way merge fixture oracle")
    parser.add_argument("--root", help="fixture tree root (default: built-in set)")
    parser.add_argument(
        "--write", metavar="DIR", help="materialise the built-in fixtures to DIR"
    )
    args = parser.parse_args(argv)
    if args.write:
        print(write_fixture_tree(args.write))
        return 0
    report = run_all(root=args.root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
