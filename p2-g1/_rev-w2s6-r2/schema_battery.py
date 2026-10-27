#!/usr/bin/env python3
"""Independent reviewer battery for wave-2 shard-6 (12 units).

Instruments, run per unit:
  A. artifact at catalog output_path: exists, non-empty, json parses,
     state not self-declared BLOCKED/FAILED/SEVERED/TIMEOUT,
     catalog completion_sentinel string present in receipt text.
  B. sha256 over CRLF-normalized (LF) bytes vs
     probes/<id>/UNIT-ARTIFACT-MANIFEST.json primary row.
  C. receipt reviewer block: verdict PASS + independent true.
  D. output_schema validation, TWO instruments:
     D1 sanctioned platform/lib/schema_resolver.validate_artifact
     D2 independent jsonschema Draft2020-12 with file:// source-ref remap
        into THIS repo root (no reliance on resolver internals).
Probes are run separately (probes_battery.py) so heavy units get full timeout.

Usage: python schema_battery.py  ->  writes schema_battery_out.json
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
sys.path.insert(0, str(REPO / "platform" / "lib"))

UNITS = [
    "BLD-0016", "BLD-0023", "BLD-0024", "BLD-0027", "BLD-0028",
    "BLD-0031", "BLD-0032", "BLD-0033", "BLD-0035", "BLD-0037",
    "BLD-0040", "BLD-0042",
]
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
_SCHEMA_TAIL = re.compile(r"/(platform/schema/|command-center/schema/)(.+)$")


def catalog_map() -> dict[str, dict]:
    cat = json.loads(
        (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    return {u["id"]: u for u in cat["work_units"] if isinstance(u, dict) and u.get("id")}


def digest_lf(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def remap_uri(uri: str) -> str:
    """Remap absolute file:// refs baked into $id/$ref to this repo root."""
    m = _SCHEMA_TAIL.search(uri.split("#", 1)[0].replace("\\", "/"))
    if not m:
        return uri
    frag = uri.split("#", 1)[1] if "#" in uri else ""
    local = (REPO / (m.group(1) + m.group(2))).resolve().as_uri()
    return local + ("#" + frag if frag else "")


def instrument_d2(artifact: dict, schema_decl: str) -> tuple[int, list[str], str]:
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT202012

    shim_path = REPO / schema_decl.replace("\\", "/")
    shim = json.loads(shim_path.read_text(encoding="utf-8"))

    resources: dict[str, Resource] = {}

    def walk(node: Any) -> None:  # noqa: ANN401
        if isinstance(node, dict):
            for key in ("$id", "$ref"):
                v = node.get(key)
                if isinstance(v, str) and v.startswith("file:"):
                    node[key] = remap_uri(v)
                    if key == "$id":
                        p = Path(node[key].split("#", 1)[0].removeprefix("file:///"))
                        try:
                            body = json.loads(p.read_text(encoding="utf-8"))
                            resources[node[key]] = Resource.from_contents(
                                body, default_specification=DRAFT202012
                            )
                        except OSError:
                            pass
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    from typing import Any  # noqa: PLC0415

    walk(shim)
    registry = Registry().with_resources(resources.items())
    validator = Draft202012Validator(shim, registry=registry)
    errs = sorted(validator.iter_errors(artifact), key=lambda e: list(e.absolute_path))
    msgs = []
    for e in errs[:8]:
        loc = "/".join(str(p) for p in e.absolute_path) or "<root>"
        msgs.append(f"{loc}: {e.message[:220]}")
    return len(errs), msgs, "draft2020-12+remap"


def main() -> int:
    from schema_resolver import validate_artifact  # noqa: PLC0415 (sanctioned resolver)

    cat = catalog_map()
    out: dict[str, dict] = {}
    for uid in UNITS:
        u = cat.get(uid)
        row: dict = {"in_catalog": u is not None}
        if u is None:
            out[uid] = row
            continue
        row["output_path"] = u.get("output_path")
        row["output_schema"] = u.get("output_schema")
        op = REPO / str(u["output_path"]).replace("\\", "/")
        row["exists_nonempty"] = op.is_file() and op.stat().st_size > 0
        try:
            text = op.read_text(encoding="utf-8")
            doc = json.loads(text)
            row["parses"] = True
        except Exception as exc:  # noqa: BLE001
            row["parses"] = False
            row["parse_error"] = repr(exc)[:200]
            out[uid] = row
            continue
        st = str(doc.get("state") or "").upper() if isinstance(doc, dict) else ""
        row["state"] = st
        row["state_not_self_blocked"] = st not in NOT_DELIVERING
        sent = str(u.get("completion_sentinel") or "")
        row["catalog_sentinel_in_text"] = bool(sent) and (sent in text)
        # informational: which prefix the receipt's own sentinel field carries
        if isinstance(doc, dict):
            rs = str(doc.get("sentinel") or "")
            row["receipt_sentinel_prefix"] = rs.split(":")[0] if rs else None
        # B: manifest sha (LF-normalized)
        man_p = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        try:
            man = json.loads(man_p.read_text(encoding="utf-8"))
            live_sha, live_n = digest_lf(op)
            out_rel = str(u["output_path"]).replace("\\", "/")
            rows = [
                a for a in (man.get("artifacts") or [])
                if isinstance(a, dict)
                and str(a.get("path") or "").replace("\\", "/") == out_rel
            ]
            match = [a for a in rows if a.get("sha256") == live_sha and a.get("present") is True]
            row["manifest_rows_for_path"] = len(rows)
            row["sha_lf"] = live_sha
            row["sha_manifest_match"] = bool(match)
        except Exception as exc:  # noqa: BLE001
            row["sha_manifest_match"] = False
            row["sha_error"] = repr(exc)[:200]
        # C: receipt reviewer block
        rev = doc.get("reviewer") or {}
        row["receipt_reviewer"] = {
            "verdict": rev.get("verdict"),
            "independent": rev.get("independent"),
            "reviewer_id": str(rev.get("reviewer_id"))[:80],
        }
        row["receipt_core_ok"] = (
            st == "SUCCESS"
            and str(rev.get("verdict") or "").upper() == "PASS"
            and rev.get("independent") is True
        )
        # D1: sanctioned resolver
        try:
            errs1 = validate_artifact(doc, str(u["output_schema"]))
            row["d1_resolver_errors"] = len(errs1)
            row["d1_first"] = [e[:200] for e in errs1[:4]]
        except Exception as exc:  # noqa: BLE001
            row["d1_resolver_errors"] = None
            row["d1_error"] = repr(exc)[:300]
        # D2: independent jsonschema
        try:
            n2, msgs2, how = instrument_d2(doc, str(u["output_schema"]))
            row["d2_jsonschema_errors"] = n2
            row["d2_first"] = msgs2
            row["d2_method"] = how
        except Exception as exc:  # noqa: BLE001
            row["d2_jsonschema_errors"] = None
            row["d2_error"] = repr(exc)[:300]
        out[uid] = row
    dst = Path(__file__).with_name("schema_battery_out.json")
    dst.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for uid, row in out.items():
        print(uid,
              "exists=%s parses=%s state=%s sha_ok=%s core_ok=%s d1=%s d2=%s" % (
                  row.get("exists_nonempty"), row.get("parses"), row.get("state"),
                  row.get("sha_manifest_match"), row.get("receipt_core_ok"),
                  row.get("d1_resolver_errors"), row.get("d2_jsonschema_errors")))
    print("WROTE", dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
