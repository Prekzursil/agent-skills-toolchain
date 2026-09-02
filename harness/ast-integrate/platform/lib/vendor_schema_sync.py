"""Keep the SCHEMA layer's vendor vocabulary generated from the registry, never hand-typed.

DEFECT D1 had two layers. ``vendor_identity.py`` fixed the predicate layer (canonical comparison);
this fixes the schema layer, where ``receipt.schema.json`` typed both ``produced_by.vendor`` and
``reviewer.vendor`` as a bare ``{"type":"string","maxLength":64}`` with ZERO enum - so a garbage
vendor string was structurally valid and then read as "a different vendor" by the predicate.

The enum is DERIVED from ``platform/registry/VENDOR-REGISTRY.json`` rather than written by hand,
because two hand-maintained copies of one vocabulary drift. ``--check`` is the permanent guard and
runs inside ``test_vendor_identity.py``; ``--emit`` prints the blocks to paste after editing the
registry.

Two vocabularies are emitted, and the difference is the point:

  ``vendor_id``            every recognized token (canonical ids AND aliases). Used by the two
                           receipt vendor fields. Accepting ``claude`` at the wire is safe because
                           the predicate folds it to ``anthropic`` before comparing; accepting
                           ``acme-ai`` is NOT safe, and this enum is what rejects it.
  ``vendor_id_canonical``  canonical ids only. Referenced by ``vendor_id``'s own description as
                           the preferred form and available to a future strict receipt profile,
                           mirroring the structural/normative/strict layering the work-unit
                           schemas already use.

Run:
    python platform/lib/vendor_schema_sync.py --check
    python platform/lib/vendor_schema_sync.py --emit
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vendor_identity import REGISTRY_PATH, load_registry  # noqa: E402

RECEIPT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1] / "schema" / "receipt.schema.json"
)

#: Canonical spelling is preferred but aliases are accepted at the wire; the resolver folds them.
VENDOR_ID_DEF = "vendor_id"
VENDOR_ID_CANONICAL_DEF = "vendor_id_canonical"

#: The pattern's job is to reject the D1 leak vectors - uppercase, leading/trailing and internal
#: whitespace, and control characters - not to police punctuation. Punctuation that appears in real
#: recognized tokens ('n/a', 'anthropic+openai', 'x.ai') is therefore allowed, and
#: test_vendor_identity.py asserts EVERY enum member matches this pattern so the two constraints
#: can never contradict each other (an enum member that fails the pattern is an unsatisfiable
#: branch: it looks permitted and validates nothing).
_PATTERN = "^[a-z0-9][a-z0-9+./_-]{0,63}$"


def build_defs(registry_path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Build the two ``$defs`` blocks from the registry. Pure - reads only the registry."""
    reg = load_registry(registry_path or REGISTRY_PATH)
    recognized = sorted(reg.recognized_tokens)
    canonical = sorted(reg.canonical_ids)
    capable = sorted(reg.distinctness_capable_ids)
    return {
        VENDOR_ID_DEF: {
            "type": "string",
            "description": (
                "A vendor identity token recognized by platform/registry/VENDOR-REGISTRY.json. "
                "GENERATED - do not hand-edit; run platform/lib/vendor_schema_sync.py --emit. "
                "This enum exists because DEFECT D1 was a false green: with vendor typed as a "
                "bare string, an unrecognized value was structurally valid and the completion "
                "predicate then read it as 'a different vendor' purely because it differed, so "
                "10/10 same-vendor alias pairs passed the cross-vendor gate. Canonical ids are "
                f"preferred ({VENDOR_ID_CANONICAL_DEF}); aliases are accepted here because "
                "platform/lib/vendor_identity.py folds them to a canonical id before any "
                "distinctness comparison. Only the "
                f"{len(capable)} identities with establishes_distinctness=true can form a "
                "cross-vendor pair - a hosting plane (bedrock, vertex, azure) or a placeholder "
                "(any, mixed, unassigned, other) resolves to NOT-COMPUTABLE, never to SATISFIED."
            ),
            "pattern": _PATTERN,
            "maxLength": 64,
            "enum": recognized,
            "x-generated-by": "platform/lib/vendor_schema_sync.py",
            "x-registry": "platform/registry/VENDOR-REGISTRY.json",
            "x-canonical-ids": canonical,
            "x-establishes-distinctness": capable,
        },
        VENDOR_ID_CANONICAL_DEF: {
            "type": "string",
            "description": (
                "Canonical vendor ids only - the preferred wire form, and the vocabulary a strict "
                "receipt profile should require. GENERATED from "
                "platform/registry/VENDOR-REGISTRY.json."
            ),
            "pattern": _PATTERN,
            "maxLength": 64,
            "enum": canonical,
            "x-generated-by": "platform/lib/vendor_schema_sync.py",
        },
    }


def _vendor_field_sites(schema: dict[str, Any]) -> list[dict[str, Any]]:
    """The two receipt fields that carry a vendor. Located structurally, not by line number."""
    defs = schema["$defs"]
    sites: list[dict[str, Any]] = []
    reviewer = defs.get("reviewer", {}).get("properties", {})
    if "vendor" in reviewer:
        sites.append(reviewer)
    produced = (
        defs.get("receipt_core", {})
        .get("properties", {})
        .get("produced_by", {})
        .get("properties", {})
    )
    if "vendor" in produced:
        sites.append(produced)
    return sites


def compute(
    schema: dict[str, Any], registry_path: Path | None = None
) -> dict[str, Any]:
    """Return the schema as it SHOULD be. Does not mutate the input."""
    out = json.loads(json.dumps(schema))
    for name, block in build_defs(registry_path).items():
        out["$defs"][name] = block
    for site in _vendor_field_sites(out):
        site["vendor"] = {"$ref": f"#/$defs/{VENDOR_ID_DEF}"}
    return out


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def check(
    schema_path: Path | None = None, registry_path: Path | None = None
) -> list[str]:
    """Return a list of drift descriptions. Empty means the schema matches the registry."""
    p = schema_path or RECEIPT_SCHEMA_PATH
    live = _load(p)
    want = compute(live, registry_path)
    problems: list[str] = []
    for name in (VENDOR_ID_DEF, VENDOR_ID_CANONICAL_DEF):
        if live.get("$defs", {}).get(name) != want["$defs"][name]:
            problems.append(
                f"{p.name} $defs.{name} does not match "
                f"{(registry_path or REGISTRY_PATH).name}; run vendor_schema_sync.py --emit "
                "and replace the block"
            )
    sites = _vendor_field_sites(live)
    if len(sites) != 2:
        problems.append(
            f"expected 2 vendor field sites in {p.name}, located {len(sites)}"
        )
    for site in sites:
        if site.get("vendor") != {"$ref": f"#/$defs/{VENDOR_ID_DEF}"}:
            problems.append(
                f"a vendor field in {p.name} is not a $ref to #/$defs/{VENDOR_ID_DEF}: "
                f"{site.get('vendor')!r}. A bare string here is DEFECT D1."
            )
    return problems


def emit(registry_path: Path | None = None) -> str:
    """Serialize the two generated ``$defs`` blocks for insertion into the schema.

    Deliberately NOT a whole-file rewriter. ``receipt.schema.json`` is the declared
    ``output_schema`` of 674 catalogue units and is hand-formatted (small objects on one line);
    re-emitting it through ``json.dumps`` would reformat all ~500 lines and bury a two-field
    change in noise. The permanent guard is :func:`check`, which compares PARSED structure and
    is therefore indifferent to formatting.
    """
    blocks = build_defs(registry_path)
    return json.dumps(blocks, indent=2, ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    ap.add_argument(
        "--emit",
        action="store_true",
        help="print the generated $defs blocks to insert into receipt.schema.json",
    )
    ns = ap.parse_args(argv)
    if ns.emit:
        print(emit())
        return 0
    problems = check()
    if problems:
        for pr in problems:
            print(f"DRIFT: {pr}")
        print("FAILED:vendor-schema-sync")
        return 1
    print("SUCCESS:vendor-schema-sync (receipt schema matches the vendor registry)")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
