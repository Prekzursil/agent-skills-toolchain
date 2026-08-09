"""Self-check probe: is receipt.schema.json a valid JSON Schema, and do all
fragments referenced by the work-unit catalog actually resolve?

Detector control included: we deliberately look up a fragment we KNOW is absent
and require the lookup to FAIL, so a "all fragments resolve" result cannot be a
vacuous green from a lookup that never fails.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.validators import validator_for
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

REPO = Path(__file__).resolve().parents[2]
SCHEMA = REPO / "platform" / "schema" / "receipt.schema.json"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

FAIL = []


def check(label: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {label}" + (f" :: {detail}" if detail else ""))
    if not ok:
        FAIL.append(label)


def main() -> int:
    raw = SCHEMA.read_bytes()
    print(f"schema bytes={len(raw)}")
    schema = json.loads(raw.decode("utf-8"))

    # 1. the schema must itself be a valid JSON Schema (metaschema validation)
    cls = validator_for(schema)
    check("validator_for resolves Draft202012", cls is Draft202012Validator, cls.__name__)
    try:
        cls.check_schema(schema)
        check("schema is metaschema-valid", True)
    except Exception as exc:  # noqa: BLE001
        check("schema is metaschema-valid", False, str(exc)[:400])
        return 1

    # 2. every $defs fragment referenced by the catalog must resolve
    cat = json.loads(CATALOG.read_bytes().decode("utf-8"))
    units = cat["work_units"]
    frags = set()
    for u in units:
        os_ = u.get("output_schema") or ""
        if "receipt.schema.json#" in os_:
            m = re.search(r"receipt\.schema\.json#(/\S*)", os_)
            if m:
                frags.add(m.group(1))
    print(f"catalog-referenced fragments: {len(frags)} -> {sorted(frags)}")

    registry = Registry().with_resource(
        schema["$id"], Resource.from_contents(schema, default_specification=DRAFT202012)
    )
    resolver = registry.resolver_with_root(
        Resource.from_contents(schema, default_specification=DRAFT202012)
    )

    unresolved = []
    for frag in sorted(frags):
        try:
            resolved = resolver.lookup("#" + frag)
            if not isinstance(resolved.contents, dict) or not resolved.contents:
                unresolved.append((frag, "resolved to empty/non-object"))
        except Exception as exc:  # noqa: BLE001
            unresolved.append((frag, type(exc).__name__))
    check(
        f"all {len(frags)} catalog fragments resolve",
        not unresolved,
        json.dumps(unresolved)[:400],
    )

    # 2b. DETECTOR CONTROL: a fragment that does not exist MUST fail to resolve.
    # Without this, "all resolve" could be a vacuous green.
    control_absent = "/$defs/this_fragment_does_not_exist_control"
    try:
        resolver.lookup("#" + control_absent)
        control_fired = False
    except Exception:  # noqa: BLE001
        control_fired = True
    check(
        "DETECTOR CONTROL: absent fragment fails to resolve",
        control_fired,
        f"looked up {control_absent}",
    )

    # 3. each fragment must be USABLE as a standalone validator
    unusable = []
    for frag in sorted(frags):
        sub = {"$ref": schema["$id"] + "#" + frag}
        try:
            Draft202012Validator(sub, registry=registry).is_valid({})
        except Exception as exc:  # noqa: BLE001
            unusable.append((frag, f"{type(exc).__name__}: {exc}"[:160]))
    check("every fragment is usable as a standalone validator", not unusable, json.dumps(unusable)[:600])

    print()
    print(f"FAILURES: {len(FAIL)} {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
