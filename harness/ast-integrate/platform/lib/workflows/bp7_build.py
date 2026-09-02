"""Builder for blueprints 73-84 of 96 (unit blueprints/bp-7).

Emits one Workflow-DSL v1 JSON document per blueprint into ``platform/workflows/``.

    73  BP-DAT-02  bounded-corpus-distillation
    74  BP-DAT-03  measurement-instrument-validation
    75  BP-DAT-04  cheap-tier-first-campaign
    76  BP-DAT-05  hermetic-eval-registry-run
    77  BP-UX-01   design-studio-eight-gate-loop
    78  BP-UX-02   two-track-ui-audit-rubric-verdict
    79  BP-UX-03   per-surface-usability-source-audit
    80  BP-UX-04   code-to-canvas-mirror-round-trip
    81  BP-UX-05   design-first-ui-intake
    82  BP-DOC-01  pre-pr-knowledge-capture
    83  BP-DOC-02  rules-distill-sweep
    84  BP-DOC-03  ssot-documentation-reconcile

RANGE RESOLUTION - stated because it is an inference, not a given.
The library holds 108 cards while the spec asks for 96 built-ins, so "73-84 of 96" needs a
mapping. This unit uses the card's POSITION in document order: index 73 is the 73rd
``### `BP-...``` heading. Two sibling slices independently used the same mapping (bp-6 emitted
BP-SEC-01/02 as cards 61/62 with ids ``SEC-61xx``/``SEC-62xx``; bp-8 emitted BP-REL-01/02 as
cards 87/88 with ids ``BPW-87xx``/``BPW-88xx``), which corroborates the convention and confirms
73-84 does not overlap either neighbour.

GUARD: ``assert_tools_permitted`` fails the BUILD when any role, stage, or work unit requests a
tool token absent from that blueprint's hand-authored ``tool_policy.allow``. The allowlist is
therefore authored, never derived from the requests it exists to constrain - a policy computed
from its own inputs cannot deny anything.

Run::

    python platform/lib/workflows/bp7_build.py            # write the 12 documents
    python platform/lib/workflows/bp7_build.py --check     # assert the committed JSON matches
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Iterator

HERE = Path(__file__).resolve().parent
LIB_ROOT = HERE.parent
for _p in (str(HERE), str(LIB_ROOT)):
    if _p not in sys.path:  # pragma: no cover - import plumbing
        sys.path.insert(0, _p)

import bp7_dat  # noqa: E402
import bp7_doc  # noqa: E402
import bp7_ux  # noqa: E402
from bp7_common import WORKFLOW_DIR, write_blueprint  # noqa: E402

#: build order = card order, so the emitted set is auditable against the library headings
BUILDERS: list[Callable[[], dict[str, Any]]] = [
    *bp7_dat.BLUEPRINTS,
    *bp7_ux.BLUEPRINTS,
    *bp7_doc.BLUEPRINTS,
]

#: the 12 ids this unit owns. An explicit manifest, not a glob: siblings write into the same
#: directory, so a wildcard would silently pull their documents into this unit's checks.
EXPECTED_IDS: tuple[str, ...] = (
    "bounded-corpus-distillation",
    "measurement-instrument-validation",
    "cheap-tier-first-campaign",
    "hermetic-eval-registry-run",
    "design-studio-eight-gate-loop",
    "two-track-ui-audit-rubric-verdict",
    "per-surface-usability-source-audit",
    "code-to-canvas-mirror-round-trip",
    "design-first-ui-intake",
    "pre-pr-knowledge-capture",
    "rules-distill-sweep",
    "ssot-documentation-reconcile",
)


def iter_tool_requests(doc: dict[str, Any]) -> Iterator[tuple[str, str]]:
    """Every ``(where, tool_token)`` a role, stage, or embedded work unit asks for."""
    for name, spec in (doc.get("roles") or {}).items():
        for tok in (spec or {}).get("tool_permissions", []) or []:
            yield (f"roles/{name}", str(tok))

    def walk(node: Any, path: str) -> Iterator[tuple[str, str]]:
        if isinstance(node, dict):
            for tok in node.get("tool_permissions", []) or []:
                yield (path or "<root>", str(tok))
            for key, value in node.items():
                if key == "tool_permissions":
                    continue
                yield from walk(value, f"{path}/{key}")
        elif isinstance(node, list):
            for i, value in enumerate(node):
                yield from walk(value, f"{path}/{i}")

    yield from walk(doc.get("stages"), "/stages")


def assert_tools_permitted(doc: dict[str, Any]) -> list[str]:
    """Return the violations: a requested tool absent from allow, or present in deny."""
    policy = doc.get("tool_policy") or {}
    allow = set(policy.get("allow") or [])
    deny = set(policy.get("deny") or [])
    default_deny = str(policy.get("default", "deny")) == "deny"
    problems: list[str] = []
    for where, tok in iter_tool_requests(doc):
        if tok in deny:
            problems.append(
                f"{doc['id']}: {where} requests {tok!r} which tool_policy.deny forbids"
            )
        elif default_deny and tok not in allow:
            problems.append(
                f"{doc['id']}: {where} requests {tok!r} absent from tool_policy.allow"
            )
    return problems


def assert_dry_run_forbids_every_mutating_tool(doc: dict[str, Any]) -> list[str]:
    """A dry run that still permits a writing tool is not side-effect free.

    Scoped deliberately: the check fires on write/edit/git tokens, not on read-only ones, so it
    cannot be satisfied by listing every tool.
    """
    dry = doc.get("dry_run") or {}
    if dry.get("side_effect_free") is not True:
        return []
    forbidden = set(dry.get("forbid_tools") or [])
    mutating_prefixes = (
        "Write(",
        "Edit",
        "Bash:git",
        "mcp__figma__generate",
        "mcp__figma__create",
    )
    problems: list[str] = []
    for tok in set(doc.get("tool_policy", {}).get("allow") or []):
        if tok.startswith(mutating_prefixes) and tok not in forbidden:
            problems.append(
                f"{doc['id']}: dry_run claims side_effect_free but does not forbid the mutating tool {tok!r}"
            )
    return problems


def build_all() -> list[dict[str, Any]]:
    docs = [fn() for fn in BUILDERS]
    ids = [d["id"] for d in docs]
    if ids != list(EXPECTED_IDS):
        raise SystemExit(
            "FAILED:bp7-build id manifest drift\n"
            f"  built:    {ids}\n  expected: {list(EXPECTED_IDS)}"
        )
    problems: list[str] = []
    for d in docs:
        problems += assert_tools_permitted(d)
        problems += assert_dry_run_forbids_every_mutating_tool(d)
    if problems:
        raise SystemExit(
            "FAILED:bp7-build tool-policy guard\n  " + "\n  ".join(problems)
        )
    return docs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bp7_build")
    ap.add_argument(
        "--check",
        action="store_true",
        help="assert the committed JSON is byte-identical",
    )
    args = ap.parse_args(argv)

    docs = build_all()
    if args.check:
        drift: list[str] = []
        for d in docs:
            path = WORKFLOW_DIR / f"{d['id']}.json"
            want = json.dumps(d, indent=2, ensure_ascii=True) + "\n"
            if not path.is_file():
                drift.append(f"{path.name}: MISSING")
            elif path.read_text(encoding="utf-8") != want:
                drift.append(f"{path.name}: DIFFERS from the builder output")
        for line in drift:
            print("  " + line)
        print(f"documents={len(docs)} drift={len(drift)}")
        print("SUCCESS:bp7-build-check" if not drift else "FAILED:bp7-build-check")
        return 0 if not drift else 1

    for d in docs:
        path = write_blueprint(d)
        stages = len(d["stages"])
        print(
            f"wrote {path.name:<48} kind={d['kind']:<14} stages={stages:<3} flagship={d['flagship']}"
        )
    print(f"documents={len(docs)}")
    print("SUCCESS:bp7-build")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
