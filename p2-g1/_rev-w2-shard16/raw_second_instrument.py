#!/usr/bin/env python3
"""Shard-16 independent reviewer, second-instrument schema check.

Raw jsonschema validation with the SAME repo-root confinement rule the
resolver documents, but written independently (no schema_resolver import for
the validation path). Compares error counts with schema_resolver itself.
Also runs the both-states mutation control on a known-passing receipt.
"""
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

REPO = Path.home() / "p2-g1"

UNITS = ["IMP-0470", "IMP-0478", "REL-0001", "REL-0006", "REL-0014", "REL-0017",
         "REL-0020", "REL-0021", "REL-0022", "RES-0004", "RES-0009", "RES-0011"]
CONTROL_PASS = "CC-0003"


def retrieve(uri):
    raw = str(uri).split("#", 1)[0]
    posix = raw.replace("file:///", "").replace("file://", "").replace("\\", "/")
    for marker in ("/platform/schema/", "/command-center/schema/"):
        i = posix.find(marker)
        if i >= 0:
            posix = str(REPO).replace("\\", "/") + posix[i:]
            break
    p = Path(posix)
    if not p.is_file():
        raise LookupError("no file on disk: %s" % uri)
    return Resource.from_contents(
        json.loads(p.read_bytes().decode("utf-8")), default_specification=DRAFT202012
    )


def raw_validate(doc, physical_path, fragment):
    phys = json.loads(Path(physical_path).read_bytes().decode("utf-8"))
    uri = Path(physical_path).resolve().as_uri()
    registry = Registry(retrieve=retrieve).with_resource(
        uri, Resource.from_contents(phys, default_specification=DRAFT202012)
    )
    v = Draft202012Validator({"$ref": uri + (fragment or "")}, registry=registry)
    return [
        "%s: %s" % ("/".join(str(p) for p in e.absolute_path) or "<root>", e.message)
        for e in v.iter_errors(doc)
    ]


def main():
    sys.path.insert(0, str(REPO / "platform" / "lib"))
    import schema_resolver as res

    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_bytes().decode("utf-8"))
    by = {u["id"]: u for u in cat["work_units"]}

    agree = diverge = 0
    for uid in UNITS + [CONTROL_PASS]:
        u = by[uid]
        decl = u["output_schema"]
        rs = res.resolve(decl)
        doc = json.loads((REPO / u["output_path"]).read_bytes().decode("utf-8"))
        raw_errs = raw_validate(doc, str(REPO / rs.physical_path), rs.physical_fragment)
        res_errs = res.validate_artifact(doc, decl)
        status = "AGREE" if len(raw_errs) == len(res_errs) else "DIVERGE"
        if len(raw_errs) == len(res_errs):
            agree += 1
        else:
            diverge += 1
        print("%s raw=%d resolver=%d %s" % (uid, len(raw_errs), len(res_errs), status))

    # Both-states mutation control: take the passing control receipt, delete a
    # required core field, and require BOTH instruments to start failing it.
    u = by[CONTROL_PASS]
    doc = json.loads((REPO / u["output_path"]).read_bytes().decode("utf-8"))
    rs = res.resolve(u["output_schema"])
    base_raw = len(raw_validate(doc, str(REPO / rs.physical_path), rs.physical_fragment))
    base_res = len(res.validate_artifact(doc, u["output_schema"]))
    mutated = json.loads(json.dumps(doc))
    for key in ("downstream_consumers", "manifest_registration", "artifacts"):
        if key in mutated:
            del mutated[key]
            break
    mut_raw = len(raw_validate(mutated, str(REPO / rs.physical_path), rs.physical_fragment))
    mut_res = len(res.validate_artifact(mutated, u["output_schema"]))
    print("control %s base raw=%d res=%d | mutated raw=%d res=%d -> %s" % (
        CONTROL_PASS, base_raw, base_res, mut_raw, mut_res,
        "BOTH-STATES-OK" if (base_raw == 0 and base_res == 0 and mut_raw > 0 and mut_res > 0) else "BOTH-STATES-BROKEN"))
    print("SUMMARY agree=%d diverge=%d" % (agree, diverge))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
