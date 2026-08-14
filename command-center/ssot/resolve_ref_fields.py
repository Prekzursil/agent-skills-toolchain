"""Resolve every inbound reference to the exact CONFIG KEY, for all three referenced checkouts.

Round 2 scored DoD item 3 "PASS with a named residual": three checkouts are named by
executable config, the field was resolved BY HAND for two of them, and `Documents/Playground`
was left as "6 hits, not re-resolved". A file-level hit is not a dependency -- this lane's own
`lookup()` docstring records the 3x over-count that came from treating an extension as
evidence, and the estate rule is "count the FIELD, not the document". A residual that says
"we did not look at the field" on 1 of 3 rows is the same gap in miniature.

This resolves all three mechanically, so no row rests on hand-reading.

WHAT COUNTS AS A FIELD. A path can reach a config three ways, and they are not equivalent:
    value        a string (or list element) whose value IS or is UNDER the checkout
    table-key    a TOML table whose NAME is the path, e.g. [projects."C:\\...\\x"] -- a
                 registration, which is how Codex records a trusted project root
    prose        anywhere inside a .md/.txt/.log -- a MENTION, never a dependency

REDACTION. These files sit next to live credentials, and one of them is read by a tool that
stores API keys. Nothing here prints or stores a VALUE: a hit records the key path, the kind,
and which checkout it resolved to. Values are matched in memory and never emitted.

CONTROLS, both states:
  parser    a key known to exist in the parsed document must be found, and a fabricated key
            must not -- proving the walker actually descends the tree rather than reporting
            an empty result for every document.
  matcher   the real checkout path must match, and a fabricated path must not.

Read-only. Writes one JSON report.
"""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "ref-fields-resolved.json"
CLASSIFIED = HERE / "population-classified.json"

FABRICATED = "c:/users/prekzursil/source/this-path-does-not-exist-92f1a"


def norm(p: str) -> str:
    return p.replace("\\\\", "/").replace("\\", "/").rstrip("/").lower()


def is_under(value: str, target: str) -> bool:
    v = norm(value)
    return v == target or v.startswith(target + "/")


def walk(node: object, target: str, trail: tuple[str, ...] = ()) -> list[dict]:
    """Every key path whose NAME or VALUE resolves to `target`. Values never recorded."""
    out: list[dict] = []
    if isinstance(node, dict):
        for k, v in node.items():
            here = trail + (str(k),)
            if isinstance(k, str) and is_under(k, target):
                out.append({"key": ".".join(here), "kind": "table-key"})
            out.extend(walk(v, target, here))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out.extend(walk(v, target, trail + (f"[{i}]",)))
    elif isinstance(node, str):
        if is_under(node, target):
            out.append({"key": ".".join(trail), "kind": "value"})
    return out


def load(fp: Path) -> object | None:
    try:
        if fp.suffix.lower() == ".toml":
            return tomllib.loads(fp.read_text(encoding="utf-8", errors="replace"))
        if fp.suffix.lower() == ".json":
            return json.loads(fp.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError, tomllib.TOMLDecodeError):
        return None
    return None


def main() -> int:
    classified = json.loads(CLASSIFIED.read_text(encoding="utf-8"))
    referenced = classified["referenced_by_exec_config"]
    print(f"referenced checkouts to resolve: {len(referenced)}")

    # ---------------------------------------------------------------- CONTROLS
    ctl_doc = {
        "projects": {
            "C:\\Users\\Prekzursil\\source\\ast-integrate": {"trust_level": "trusted"},
            "other": {"rootPaths": ["C:/Users/Prekzursil/source/ast-integrate/sub"]},
        },
        "unrelated": {"note": "no path here"},
    }
    ctl_target = "c:/users/prekzursil/source/ast-integrate"
    hits_pos = walk(ctl_doc, ctl_target)
    hits_neg = walk(ctl_doc, FABRICATED)
    kinds = {h["kind"] for h in hits_pos}
    parser_ok = len(hits_pos) == 2 and kinds == {"table-key", "value"} and not hits_neg
    print(
        f"CONTROL walker on a synthetic doc: {len(hits_pos)} hit(s) kinds={sorted(kinds)}"
    )
    print(f"CONTROL walker on a fabricated path: {len(hits_neg)} hit(s)")
    print(f"  discriminates: {parser_ok}")
    if not parser_ok:
        print("FAILED:resolve-ref-fields walker control did not discriminate")
        return 3

    results = []
    for row in referenced:
        target = norm(row["path"])
        print(f"\n{row['path']}   ({row['refs']} file-level hit(s))")
        fields, unparsed = [], []
        for f in row["files"]:
            fp = Path(f)
            if not fp.exists():
                unparsed.append({"file": f, "why": "does not exist"})
                continue
            doc = load(fp)
            if doc is None:
                unparsed.append(
                    {"file": f, "why": f"unparsed ({fp.suffix or 'no ext'})"}
                )
                continue
            found = walk(doc, target)
            if not found:
                unparsed.append({"file": f, "why": "parsed, no field resolves to it"})
                continue
            live = ".codex\\backups" not in f and "/backups/" not in f.replace(
                "\\", "/"
            )
            for h in found:
                fields.append(
                    {"file": f, "key": h["key"], "kind": h["kind"], "live": live}
                )

        for h in fields:
            tag = "LIVE  " if h["live"] else "backup"
            print(f"    {tag} {h['kind']:<9} {h['key']}")
            print(f"           in {h['file']}")
        for u in unparsed:
            print(f"    ----- {u['why']:<34} {u['file']}")

        live_fields = [h for h in fields if h["live"]]
        results.append(
            {
                "path": row["path"],
                "file_level_hits": row["refs"],
                "fields_resolved": fields,
                "live_field_count": len(live_fields),
                "unresolved_files": unparsed,
            }
        )

    report = {
        "walker_control": {
            "positive_hits": len(hits_pos),
            "positive_kinds": sorted(kinds),
            "fabricated_hits": len(hits_neg),
            "discriminates": parser_ok,
        },
        "referenced": results,
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, indent=2)
    print(f"\nwrote {OUT}")

    total_live = sum(r["live_field_count"] for r in results)
    unresolved = sum(len(r["unresolved_files"]) for r in results)
    print(
        f"SUCCESS:resolve-ref-fields checkouts={len(results)} "
        f"live_fields={total_live} files_unresolved={unresolved}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
