"""Corpus-level index of workflow document ids under ``platform/workflows/``.

Why this exists as its own module, and what invariant it owns
-------------------------------------------------------------
``platform/lib/foundry/test_foundry.py`` already ships a D4 gate, and that gate is sound as far
as it goes: it fires when one id resolves to two documents whose **content differs**
(``divergent_ids``). It is silent when one id resolves to two paths holding the **same** bytes,
because a content-addressed id is *supposed* to be stable under a pure re-run.

That blind spot is exactly what the shipped corpus violated. ``forge fuse --strategy
best-of-breed`` and ``forge tournament`` over the same source pair both emit the winning
document, the tournament's winner *was* best-of-breed, so two paths carried one byte-identical
document -- and therefore one id. The content-level gate could not see it, and
``platform/routing/index.py`` absorbed it with a silent ``continue`` on an already-seen id.

So this module owns the stricter, structural invariant:

    an id must resolve to EXACTLY ONE path.

That is what any loader keyed on id actually needs. Two paths for one id make id -> path
resolution ambiguous no matter how equal the bytes are today, and it sets up the divergent case
for the moment somebody edits one of them.

Assert the positive, never "nothing blocking"
---------------------------------------------
:func:`scan_workflow_ids` reports ``workflow_documents`` and ``distinct_ids`` so a caller can
assert ``distinct_ids == workflow_documents`` -- an exact N-of-N equality. A caller that only
checked "``ids_at_multiple_paths`` is empty" would also pass on a tree where the walk matched
nothing, which is a detector failure dressed as a green. Every failure mode here is fail-closed:
an empty walk and an unparsable file are both violations, not passes.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

#: ``platform/workflows`` relative to this file (``platform/lib/workflows/``).
DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "workflows"


def is_workflow_doc(doc: object) -> bool:
    """True for a workflow DSL document, False for a report/status/validation sidecar.

    Shape, not file name. The corpus is full of ``*-STATUS.json`` / ``*REPORT.json`` sidecars
    that describe blueprints without being one, and a name filter would let a renamed sidecar
    through while excluding a legitimately-named document. A workflow document is identified by
    carrying a non-empty string ``id`` plus the two DSL-mandatory keys.
    """
    return (
        isinstance(doc, dict)
        and isinstance(doc.get("id"), str)
        and bool(doc["id"])
        and "dsl_version" in doc
        and "stages" in doc
    )


def canonical_digest(doc: Any) -> str:
    """sha256 over the key-sorted canonical JSON of a parsed document.

    Over the PARSED document, deliberately: hashing the raw file bytes would make the digest
    line-ending dependent, and git stores LF while Windows checks out CRLF, so a byte hash of a
    working-tree file answers a different question on each platform.
    """
    return hashlib.sha256(
        json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def scan_workflow_ids(root: Path) -> dict[str, Any]:
    """Walk ``root`` recursively and index every workflow document by its id.

    ``rglob``, not a depth-1 glob: the forged artifacts live in a ``forged/`` subdirectory and a
    depth-1 walk reports a clean tree while a collision is live in the subdirectory.

    Returns a report with:

    ``workflow_documents``
        how many documents the walk actually matched. 0 means the detector measured nothing.
    ``distinct_ids``
        how many distinct ids those documents carry. Equal to ``workflow_documents`` iff the
        id -> path mapping is one-to-one.
    ``ids_at_multiple_paths``
        every id carried by more than one path, mapped to those paths and their content digests.
        Equal digests mean the duplicate is a redundant copy; unequal digests mean one id
        resolves to genuinely different documents, which is the more dangerous case.
    ``unparsable``
        files that failed to parse. Reported, never skipped silently.
    """
    by_id: dict[str, list[dict[str, str]]] = {}
    docs = 0
    unparsable: list[str] = []
    for path in sorted(root.rglob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            unparsable.append(f"{path.name}: {type(exc).__name__}: {exc}")
            continue
        if not is_workflow_doc(doc):
            continue
        docs += 1
        by_id.setdefault(str(doc["id"]), []).append(
            {
                "path": path.relative_to(root).as_posix(),
                "digest": canonical_digest(doc),
            }
        )
    return {
        "root": root.as_posix(),
        "workflow_documents": docs,
        "distinct_ids": len(by_id),
        "ids_at_multiple_paths": {
            wid: entries for wid, entries in sorted(by_id.items()) if len(entries) > 1
        },
        "unparsable": unparsable,
    }


def violations(report: dict[str, Any]) -> list[str]:
    """Turn a scan report into an explicit violation list. Fail-closed on an empty walk."""
    out: list[str] = []
    if report["unparsable"]:
        out.append(f"unparsable workflow json: {report['unparsable']}")
    if report["workflow_documents"] == 0:
        out.append(
            "the walk matched NO workflow document, so this gate measured nothing -- "
            "an empty walk is a detector failure, never a pass"
        )
    for wid, entries in report["ids_at_multiple_paths"].items():
        paths = [e["path"] for e in entries]
        digests = {e["digest"] for e in entries}
        shape = (
            "byte-identical copies of one document"
            if len(digests) == 1
            else "GENUINELY DIFFERENT documents"
        )
        out.append(
            f"workflow id {wid!r} resolves to {len(entries)} paths ({shape}), so id -> path "
            f"resolution is ambiguous: {paths}"
        )
    if (
        report["workflow_documents"]
        and report["distinct_ids"] != report["workflow_documents"]
    ):
        out.append(
            f"expected exactly one id per document: {report['workflow_documents']} documents "
            f"carry only {report['distinct_ids']} distinct ids"
        )
    return out


def main(argv: list[str] | None = None) -> int:
    root = Path(argv[0]).resolve() if argv else DEFAULT_ROOT
    if not root.is_dir():
        print(f"FAILED:workflow-id-uniqueness root is not a directory: {root}")
        return 1
    report = scan_workflow_ids(root)
    bad = violations(report)
    print(json.dumps(report, indent=2))
    for v in bad:
        print(f"VIOLATION: {v}")
    print(
        f"{'SUCCESS' if not bad else 'FAILED'}:workflow-id-uniqueness "
        f"documents={report['workflow_documents']} distinct_ids={report['distinct_ids']} "
        f"violations={len(bad)}"
    )
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
