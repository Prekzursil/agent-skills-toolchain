#!/usr/bin/env python3
"""Write the CNL-0001 envelope artifact, meta-schema, and on-disk fixtures."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from envelope import ARTIFACT_REL, META_REL, SENTINEL, meta_schema, v2_envelope  # noqa: E402
from fixtures import (  # noqa: E402
    catalogue_file,
    v1_charter_instance,
    v1_charter_schema,
)
from migrate import migrate_v1_to_v2  # noqa: E402


def dump(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def main() -> int:
    envelope = v2_envelope()
    meta = meta_schema()
    Draft202012Validator.check_schema(envelope)
    Draft202012Validator.check_schema(meta)
    env_path = REPO / ARTIFACT_REL
    meta_path = REPO / META_REL
    dump(env_path, envelope)
    # Catalog output_schema path is a generated class shim used by 24 units.
    # Never overwrite it with this unit's in-memory meta-schema.
    if not meta_path.is_file() or meta_path.stat().st_size <= 0:
        dump(meta_path, meta)

    live = json.loads(env_path.read_text(encoding="utf-8"))
    if SENTINEL not in json.dumps(live):
        print("FAILED:emit sentinel missing from artifact")
        return 1
    meta_v = Draft202012Validator(meta)
    meta_errs = [e.message for e in meta_v.iter_errors(live)]
    if meta_errs:
        print("FAILED:emit artifact fails output_schema", meta_errs[:8])
        return 1
    rec_v = Draft202012Validator(live)
    migrated = migrate_v1_to_v2(v1_charter_instance())
    rec_errs = [e.message for e in rec_v.iter_errors(migrated)]
    if rec_errs:
        print("FAILED:emit migrated charter fails envelope", rec_errs[:8])
        return 1

    fx = HERE / "fixtures"
    dump(fx / "v1-council-charter.schema.json", v1_charter_schema())
    dump(fx / "v1-charter-instance.json", v1_charter_instance())
    cat = catalogue_file()
    dump(fx / "catalogue.json", cat)
    print(
        f"wrote {ARTIFACT_REL} and {META_REL} "
        f"protocols={len(cat['protocols'])} presets={len(cat['presets'])}"
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
