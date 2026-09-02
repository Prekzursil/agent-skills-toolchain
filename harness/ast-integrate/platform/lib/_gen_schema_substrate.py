#!/usr/bin/env python3
"""Generate the output_schema substrate that closes the P1 dangling-reference defect.

WHAT THIS BUILDS
  1. platform/schema/artifact-class-profiles.schema.json
     The PHYSICAL definition of every logical artifact class the catalog names.
     Each class is  allOf[ receipt.schema.json#/$defs/generic_report , report.kind const ].
     generic_report already allOf's receipt_core, so a class adds exactly ONE
     constraint of its own -- the kind pin that makes classes mutually
     discriminating -- and duplicates nothing.

  2. command-center/schema/**.schema.json  (+ the wfa pack)
     One GENERATED SHIM per logical id the catalog declares, so the declared path
     literally resolves on disk. A shim carries no constraints: its body is a
     single $ref into (1). Files that are referenced by JSON pointer also carry a
     local $defs table so 'X.schema.json#/$defs/Y' resolves inside the shim.

  3. platform/schema/ARTIFACT-CLASS-REGISTRY.json
     The logical-id -> physical-target map as DATA, so the mapping is inspectable
     without reading resolver code.

WHAT IT DOES NOT DO
  It does not modify WORK-UNIT-CATALOG.json (2007 units, committed, shared git
  index) and it does not modify receipt.schema.json (59 tests + a 22-mutation
  battery pinned to it). Both stay byte-identical.

Rerunnable and deterministic: no timestamps, no randomness, sorted keys, LF only.

WHERE IT WRITES
  Inputs are always read from REPO (derived from this file's location, so the generator
  is not pinned to one absolute path). Outputs go to OUT_ROOT, which defaults to REPO but
  is redirectable with --out-root. That seam exists because a TEST must be able to
  generate into a temp dir and diff, rather than regenerating over the real tree: an
  in-place regeneration silently REVERTS a hand-edit to any of the 236 outputs, which
  turns the determinism check into a repair job that reports green
  (see platform/DEFECT-D3-TEST-MUTATES-TREE.md). cwd is NOT that seam and never was --
  nothing here reads cwd.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict

#: Input root: this file is <REPO>/platform/lib/_gen_schema_substrate.py.
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#: Output root. Defaults to REPO; --out-root redirects every write (and only writes).
OUT_ROOT = REPO
sys.path.insert(0, os.path.join(REPO, "platform", "lib"))
from receipt_schema_gate import parse_schema_ref  # noqa: E402  repo-owned splitter

CATALOG = os.path.join(REPO, "command-center", "WORK-UNIT-CATALOG.json")
BASE = "https://ast-integrate.invalid/"
RECEIPT_ID = BASE + "platform/schema/receipt.schema.json"
PROFILES_REL = "platform/schema/artifact-class-profiles.schema.json"
PROFILES_ID = BASE + PROFILES_REL
REGISTRY_REL = "platform/schema/ARTIFACT-CLASS-REGISTRY.json"
META_URL = "https://json-schema.org/draft/2020-12/schema"

#: catalog ids that are the draft-2020-12 meta-schema, not a receipt class
META_MIRRORS = {
    "command-center/schema/_meta/json-schema-2020-12.json",
    "command-center/schema/meta/json-schema-draft.json",
}
#: the canonical receipt: NOT kind-pinned, because 546 units use it as the
#: general receipt with 30 different routing profiles.
CANONICAL_RECEIPT = "command-center/schema/receipt.schema.json"


#: --force: overwrite a hand-authored file that sits on a generated path.
FORCE = False
#: outputs skipped because a unit hand-authored real constraints at that path.
PRESERVED: list[str] = []


def _generator_owned(text: str, rel: str) -> bool:
    """True when the bytes at a generated path were written by this generator.

    Every output carries one of these markers (shims: x-generated-by; profiles and
    registry: a GENERATED $comment naming this file; the meta alias: x-alias-of; the
    meta mirror: its path). A catalog-declared path whose file carries none was
    hand-authored by a unit (measured 2026-09-02: claim-record CC-0017,
    discrepancy-record CNF-0001, wfa-schema-pack WFA-0001) and a blind regen would
    silently revert that unit's constraints -- the exact defect the docstring warns
    about. Such files are preserved unless --force is given.
    """
    return (
        rel in META_MIRRORS
        or "x-generated-by" in text
        or "_gen_schema_substrate.py" in text
        or "x-alias-of" in text
    )


def write_json(rel: str, obj) -> int:
    path = os.path.join(OUT_ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = json.dumps(obj, indent=2, sort_keys=False, ensure_ascii=False) + "\n"
    if not FORCE and os.path.isfile(path):
        with open(path, "rb") as fh:
            existing = fh.read().decode("utf-8", "replace")
        if existing != text and not _generator_owned(existing, rel):
            PRESERVED.append(rel)
            return 0
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return len(text.encode("utf-8"))


_PHYS_RECEIPT_CACHE: dict | None = None


def _physical_pins_kind(frag: str) -> bool:
    """True when receipt.schema.json's own $defs[frag] already pins report.kind.

    Measured, not assumed: 3 of the 14 (benchmark_result, predicate_report,
    security_report) carry a kind const; the other 11 are bare aliases of
    generic_report. Only the unpinned ones get a pin added at the shim layer, so a
    physical const can never be contradicted by a second, different const.
    """
    global _PHYS_RECEIPT_CACHE
    if _PHYS_RECEIPT_CACHE is None:
        path = os.path.join(REPO, "platform", "schema", "receipt.schema.json")
        with open(path, "rb") as fh:
            _PHYS_RECEIPT_CACHE = json.loads(fh.read().decode("utf-8"))
    node = _PHYS_RECEIPT_CACHE.get("$defs", {}).get(frag)
    if node is None:
        return False
    text = json.dumps(node)
    return '"kind"' in text and '"const"' in text


def _self_contained_meta(meta: dict) -> dict:
    """Inline the draft-2020-12 vocabulary meta-schemas so the mirror has no
    relative $refs left.

    The library's META_SCHEMA is `allOf: [{$ref: meta/core}, ...]`. Each vocabulary
    document loses its own $id/$schema/$dynamicAnchor/$vocabulary (the mirror root
    keeps `$dynamicAnchor: meta`, which is what their `$dynamicRef: #meta` binds to)
    and its $defs are merged into the root $defs, where their `#/$defs/<name>`
    pointers now land. Names are disjoint across the seven vocabularies; a collision
    fails loud rather than silently shadowing one definition with another.
    """
    from jsonschema_specifications import REGISTRY as SPECS

    base = META_URL.rsplit("/", 1)[0] + "/"
    defs: dict = dict(meta.get("$defs") or {})
    inlined: list = []
    for item in meta.get("allOf") or []:
        ref = item.get("$ref") if isinstance(item, dict) else None
        if not ref:
            inlined.append(item)
            continue
        vocab = dict(SPECS.contents(base + ref))
        for key in ("$schema", "$id", "$dynamicAnchor", "$vocabulary", "title"):
            vocab.pop(key, None)
        for name, body in (vocab.pop("$defs", None) or {}).items():
            if name in defs and defs[name] != body:
                raise RuntimeError(f"meta-schema $defs collision on {name!r} from {ref}")
            defs[name] = body
        vocab["$comment"] = f"inlined from {base}{ref}"
        inlined.append(vocab)
    meta["allOf"] = inlined
    if defs:
        meta["$defs"] = defs
    return meta


def class_id_for_file(rel: str) -> str:
    base = os.path.basename(rel)
    for suf in (".schema.json", ".json"):
        if base.endswith(suf):
            return base[: -len(suf)]
    return base


def survey():
    """-> (file_refcount, frags_per_file, units_per_file, annotations_per_file)"""
    with open(CATALOG, "r", encoding="utf-8") as fh:
        wus = json.load(fh)["work_units"]
    refcount = Counter()
    frags = defaultdict(Counter)
    units = defaultdict(list)
    profiles = defaultdict(Counter)
    meta_url_units = []
    for wu in wus:
        raw = wu["output_schema"]
        uid = wu.get("id", "<no-id>")
        f, frag = parse_schema_ref(raw)
        if f.startswith("http"):
            meta_url_units.append(uid)
            continue
        f = f.replace("\\", "/")
        refcount[f] += 1
        units[f].append(uid)
        if frag:
            frags[f][frag.lstrip("#").split("/")[-1]] += 1
        if " profile=" in raw:
            profiles[f][raw.split(" profile=", 1)[1].split()[0]] += 1
    return refcount, frags, units, profiles, meta_url_units


def build_profiles(refcount, frags, units):
    """The physical class definitions. One $ref + one kind pin per class."""
    defs: dict[str, dict] = {}

    def add_class(cid: str, comment: str) -> None:
        if cid in defs:
            return
        defs[cid] = {
            "$comment": comment,
            "allOf": [
                {"$ref": RECEIPT_ID + "#/$defs/generic_report"},
                {
                    "properties": {
                        "report": {
                            "required": ["kind"],
                            "properties": {"kind": {"const": cid}},
                        }
                    }
                },
            ],
        }

    for rel, n in sorted(refcount.items()):
        if rel in META_MIRRORS:
            continue
        if rel == CANONICAL_RECEIPT:
            # The canonical receipt's own root stays receipt_core (not a class), but its
            # 14 pointer-referenced $defs are routed through here so the kind pin lives
            # in the physical control plane -- NOT in the shim, which is pure delegation
            # and which the resolver deliberately does not read constraints from.
            for frag, fn in sorted(frags.get(rel, {}).items()):
                if frag in defs:
                    continue
                base = {"$ref": RECEIPT_ID + f"#/$defs/{frag}"}
                if _physical_pins_kind(frag):
                    defs[frag] = {
                        "$comment": (
                            f"{fn} unit(s) declare {rel}#/$defs/{frag}. The physical $defs "
                            "entry already pins report.kind, so this is pure delegation."
                        ),
                        "allOf": [base],
                    }
                else:
                    defs[frag] = {
                        "$comment": (
                            f"{fn} unit(s) declare {rel}#/$defs/{frag}. MEASURED: 11 of the 14 "
                            "pre-existing $defs in receipt.schema.json are bare aliases of "
                            "generic_report, so without this pin a cache_report receipt "
                            "validates as a shell_report and the fragment name discriminates "
                            "nothing. The pin is added here rather than in receipt.schema.json "
                            "so that file stays byte-identical (59 tests + a 22-mutation "
                            "battery are pinned to it)."
                        ),
                        "allOf": [
                            base,
                            {
                                "properties": {
                                    "report": {
                                        "required": ["kind"],
                                        "properties": {"kind": {"const": frag}},
                                    }
                                }
                            },
                        ],
                    }
            continue
        cid = class_id_for_file(rel)
        sample = ", ".join(sorted(units[rel])[:3])
        add_class(
            cid,
            f"Logical artifact class declared by {n} unit(s) as {rel} (e.g. {sample}).",
        )
        for frag, fn in sorted(frags.get(rel, {}).items()):
            add_class(
                frag, f"Fragment class: {fn} unit(s) declare {rel}#/$defs/{frag}."
            )

    return {
        "$schema": META_URL,
        "$id": PROFILES_ID,
        "title": "Artifact-class profiles",
        "description": (
            "Physical definition of every logical artifact class named by "
            "command-center/WORK-UNIT-CATALOG.json work_units[].output_schema. A class "
            "is generic_report (which already carries receipt_core plus the "
            "kind/observations/control_ids payload discipline) narrowed by a const pin "
            "on report.kind. The pin is what makes two classes non-interchangeable: an "
            "audit-finding receipt cannot validate as a refutation-record. No constraint "
            "defined in receipt.schema.json is restated here -- this file only references "
            "it, so there is one control plane, not two."
        ),
        "$comment": (
            "GENERATED by platform/lib/_gen_schema_substrate.py. Edit the generator or "
            "receipt.schema.json, never this file."
        ),
        "$defs": {k: defs[k] for k in sorted(defs)},
    }


def main(argv: list[str] | None = None) -> int:
    global OUT_ROOT
    import argparse

    ap = argparse.ArgumentParser(description="Generate the output_schema substrate.")
    ap.add_argument(
        "--out-root",
        default=None,
        help=(
            "Directory to write the substrate into (default: the repo this file lives in). "
            "Point it at a temp dir to diff the generator's output WITHOUT regenerating "
            "over -- and thereby silently repairing -- the real tree."
        ),
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help=(
            "Overwrite a hand-authored file that sits on a generated path. Default: such "
            "files are preserved and listed, so a regen cannot silently revert a unit's "
            "constraints."
        ),
    )
    ns = ap.parse_args(sys.argv[1:] if argv is None else argv)
    OUT_ROOT = os.path.abspath(ns.out_root) if ns.out_root else REPO
    global FORCE
    FORCE = bool(ns.force)
    PRESERVED.clear()

    if not os.path.isfile(
        CATALOG
    ):  # fail closed: no catalog => nothing to generate from
        print(f"FAILED:gen-substrate catalog absent at {CATALOG}", file=sys.stderr)
        return 2

    refcount, frags, units, profiles, meta_url_units = survey()
    written: list[tuple[str, int]] = []

    # ---- 1. physical class definitions -----------------------------------
    prof = build_profiles(refcount, frags, units)
    written.append((PROFILES_REL, write_json(PROFILES_REL, prof)))
    class_names = set(prof["$defs"])

    # ---- 2. the meta-schema mirror (offline, from the installed library) ---
    from jsonschema.validators import Draft202012Validator

    meta = _self_contained_meta(dict(Draft202012Validator.META_SCHEMA))
    primary_meta = "command-center/schema/_meta/json-schema-2020-12.json"
    alias_meta = "command-center/schema/meta/json-schema-draft.json"
    meta["$comment"] = (
        "Local mirror of the draft-2020-12 meta-schema, emitted from the installed "
        "jsonschema package (no network fetch). Declared as output_schema by units whose "
        "output IS a JSON Schema. SELF-CONTAINED: the seven vocabulary meta-schemas "
        "(meta/core ...) are inlined into allOf and their $defs merged here, because a "
        "relative `meta/core` $ref only resolves through the library's bundled registry -- "
        "measured 2026-09-02: reached via a $ref (the meta alias or this file's own id) "
        "the relative ref was re-based onto the retrieving URI and died on "
        "<base>/_meta/meta/core. schema_resolver.validator_for() still returns the "
        "library's own meta-schema validator for this id so resolution never touches the "
        "network."
    )
    written.append((primary_meta, write_json(primary_meta, meta)))
    written.append(
        (
            alias_meta,
            write_json(
                alias_meta,
                {
                    "$schema": META_URL,
                    "$id": BASE + alias_meta,
                    "title": "draft-2020-12 meta-schema (alias)",
                    "$comment": (
                        "The catalog names the meta-schema under two paths. This one is an ALIAS so the "
                        "document is stored once; see x-alias-of."
                    ),
                    "x-alias-of": primary_meta,
                    "$ref": BASE + primary_meta,
                },
            ),
        )
    )

    # ---- 3. one shim per logical id ---------------------------------------
    for rel, n in sorted(refcount.items()):
        if rel in META_MIRRORS:
            continue
        cid = class_id_for_file(rel)
        shim: dict = {
            "$schema": META_URL,
            "$id": BASE + rel,
            "title": f"{cid} receipt (logical artifact class)",
            "$comment": (
                "GENERATED SHIM -- carries NO constraints of its own. The catalog declares "
                f"this path in output_schema for {n} unit(s); this file exists so the declared "
                "path resolves on disk, and delegates by $ref to the single physical control "
                "plane. Do not add rules here: edit "
                "platform/schema/artifact-class-profiles.schema.json (or receipt.schema.json) "
                "and re-run platform/lib/_gen_schema_substrate.py."
            ),
            "x-generated-by": "platform/lib/_gen_schema_substrate.py",
            "x-artifact-class": cid,
            "x-catalog-reference-count": n,
            "x-catalog-sample-units": sorted(units[rel])[:5],
        }
        if profiles.get(rel):
            shim["x-catalog-routing-profiles"] = dict(sorted(profiles[rel].items()))

        if rel == CANONICAL_RECEIPT:
            shim["x-physical-definition"] = (
                "platform/schema/receipt.schema.json#/$defs/receipt_core"
            )
            shim["$ref"] = RECEIPT_ID + "#/$defs/receipt_core"
            shim["$comment"] += (
                " This id is the GENERAL receipt and is deliberately NOT kind-pinned: 546 units "
                "use it as the plain receipt across 30 routing profiles."
            )
        else:
            shim["x-physical-definition"] = f"{PROFILES_REL}#/$defs/{cid}"
            shim["$ref"] = f"{PROFILES_ID}#/$defs/{cid}"

        # A file referenced by JSON pointer needs those names to resolve LOCALLY.
        # Every fragment -- including the canonical receipt's 14 -- delegates to the
        # profiles file, which is the single place a class constraint may live.
        if frags.get(rel):
            shim["$defs"] = {
                frag: {
                    "$comment": f"{fn} unit(s) declare {rel}#/$defs/{frag}.",
                    "$ref": f"{PROFILES_ID}#/$defs/{frag}",
                }
                for frag, fn in sorted(frags[rel].items())
            }
        written.append((rel, write_json(rel, shim)))

    # ---- 4. the mapping as inspectable data -------------------------------
    entries = {}
    for rel, n in sorted(refcount.items()):
        if rel in META_MIRRORS:
            entries[rel] = {
                "kind": "meta-schema-mirror",
                "physical_path": primary_meta if rel == primary_meta else primary_meta,
                "fragment": None,
                "reference_count": n,
                "sample_units": sorted(units[rel])[:5],
            }
            continue
        cid = class_id_for_file(rel)
        entries[rel] = {
            "kind": "canonical-receipt"
            if rel == CANONICAL_RECEIPT
            else "artifact-class",
            "shim_path": rel,
            "physical_path": (
                "platform/schema/receipt.schema.json"
                if rel == CANONICAL_RECEIPT
                else PROFILES_REL
            ),
            "physical_fragment": (
                "#/$defs/receipt_core" if rel == CANONICAL_RECEIPT else f"#/$defs/{cid}"
            ),
            "artifact_class": cid,
            "report_kind_pinned": rel != CANONICAL_RECEIPT,
            "reference_count": n,
            "sample_units": sorted(units[rel])[:5],
            "fragments": {
                f: {
                    "reference_count": c,
                    # Always the profiles file: that is where a class constraint (the
                    # report.kind pin) lives, so resolving a fragment straight to
                    # receipt.schema.json would silently bypass the pin.
                    "physical_path": PROFILES_REL,
                    "physical_fragment": f"#/$defs/{f}",
                    "physical": f"{PROFILES_REL}#/$defs/{f}",
                }
                for f, c in sorted(frags.get(rel, {}).items())
            },
        }
    registry = {
        "title": "Artifact-class registry (logical output_schema id -> physical schema)",
        "$comment": (
            "GENERATED by platform/lib/_gen_schema_substrate.py. The authoritative mapping "
            "consumed by platform/lib/schema_resolver.py. Kept as data so the mapping is "
            "inspectable without reading resolver code."
        ),
        "source_catalog": "command-center/WORK-UNIT-CATALOG.json work_units[]",
        "meta_schema_url_alias": {
            "id": META_URL,
            "reference_count": len(meta_url_units),
            "physical_path": primary_meta,
            "sample_units": sorted(meta_url_units)[:5],
        },
        "counts": {
            "logical_ids": len(entries),
            "artifact_classes_defined": len(class_names),
            "total_path_references": sum(refcount.values()),
            "total_meta_url_references": len(meta_url_units),
        },
        "entries": entries,
    }
    written.append((REGISTRY_REL, write_json(REGISTRY_REL, registry)))

    written = [(rel, b) for rel, b in written if rel not in PRESERVED]
    print(f"generated {len(written)} files")
    if PRESERVED:
        print(
            f"  preserved (hand-authored)  : {len(PRESERVED)} -- "
            + ", ".join(PRESERVED)
            + "  (pass --force to overwrite)"
        )
    print(f"  out root                   : {OUT_ROOT}")
    print(f"  physical class definitions : {len(class_names)}")
    print(f"  logical ids (shims+mirrors): {len(entries)}")
    print(f"  bytes total                : {sum(b for _, b in written)}")
    for rel, b in written[:6]:
        print(f"    {rel}  {b}B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
