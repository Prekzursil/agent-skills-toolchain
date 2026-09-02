#!/usr/bin/env python3
"""Named probe 1: incident table, two-rail evidence, mechanism mapping."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:RES-0055-probe1 {msg}")
    return 1


def main() -> int:
    artifact_path = C.REPO / C.OUT_REL
    if not artifact_path.is_file():
        return fail(f"missing artifact {C.OUT_REL}")
    text = artifact_path.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{exc}")
    if not isinstance(doc, dict):
        return fail("artifact is not an object")
    if C.SENTINEL not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    schema_path = C.REPO / C.SCHEMA_REL
    if schema_path.is_file():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        try:
            import jsonschema
        except ImportError:
            jsonschema = None  # type: ignore
        if jsonschema is not None:
            jsonschema.validate(instance=doc, schema=schema)

    table = doc.get("incident_table")
    if not isinstance(table, list) or len(table) < 3:
        return fail("incident_table missing or too small")
    index = C.load_index()
    specs = {s["incident_id"]: s for s in C.incident_specs()}
    seen_classes: set[str] = set()
    na_rows = 0
    measured_ok = 0

    for row in table:
        if not isinstance(row, dict):
            return fail("incident row not object")
        iid = str(row.get("incident_id") or "")
        spec = specs.get(iid)
        if spec is None:
            return fail(f"unknown incident_id {iid}")
        if row.get("applicability_verdict") not in {"applicable", "not-applicable"}:
            return fail(f"{iid} missing applicability_verdict")
        if row.get("applicability_verdict") == "not-applicable":
            na_rows += 1
            if len(str(row.get("applicability_reason") or "")) < 32:
                return fail(f"{iid} N/A reason too thin")
        seen_classes.add(str(row.get("mechanism_class") or ""))
        for extra in row.get("also_classes") or []:
            seen_classes.add(str(extra))
        sources = row.get("primary_sources") or []
        if not isinstance(sources, list) or len(sources) < 2:
            return fail(f"{iid} needs two primary_sources")
        kinds = {str(s.get("rail") or "") for s in sources if isinstance(s, dict)}
        if "R1-api" not in kinds or "R2-prose" not in kinds:
            return fail(f"{iid} rails must include R1-api and R2-prose")
        rails = []
        for src in sources:
            cid = str(src.get("capture_id") or "")
            rail = C.verified_rail(index, cid)
            if str(src.get("sha256") or "") != rail["sha256"]:
                return fail(f"{iid} sha256 mismatch for {cid}")
            if str(src.get("permalink") or "") != rail["permalink"]:
                return fail(f"{iid} permalink mismatch for {cid}")
            if int(src.get("http_status") or 0) != rail["http_status"]:
                return fail(f"{iid} http_status mismatch for {cid}")
            rails.append(rail)
        C.require_needles(rails[0], list(spec["r1"]["needles"]))
        C.require_needles(rails[1], list(spec["r2"]["needles"]))
        grades = spec.get("evidence_grade") or {}
        if "measured" in grades.values():
            if rails[0]["http_status"] != 200 or rails[1]["http_status"] != 200:
                return fail(f"{iid} measured claim needs HTTP 200 on both rails")
            measured_ok += 1
        for rel_fn in spec.get("local_anchors") or []:
            rel = str(rel_fn).split(":")[0]
            if not (C.REPO / rel).is_file():
                return fail(f"{iid} missing local anchor {rel}")

    missing = [m for m in C.NAMED_MECHANISMS if m not in seen_classes]
    if missing:
        return fail(f"mechanism classes not covered: {missing}")
    if na_rows < 1:
        return fail("control: need at least one not-applicable mechanism")
    if measured_ok < 3:
        return fail("need at least three incidents with a measured (API+prose) claim")

    mmap = doc.get("mechanism_map")
    if not isinstance(mmap, list) or len(mmap) < 4:
        return fail("mechanism_map missing")
    if not any(
        isinstance(r, dict) and r.get("applicability_verdict") == "not-applicable"
        for r in mmap
    ):
        return fail("mechanism_map has no not-applicable row")
    payloads = doc.get("payload_types") or []
    if not isinstance(payloads, list) or len(payloads) < 3:
        return fail("payload_types missing")
    payload_text = (C.REPO / "tools/plugin/payloadutil.py").read_text(encoding="utf-8")
    for item in payloads:
        rel = str((item or {}).get("path") or "")
        if rel and rel not in payload_text:
            return fail(f"payload path {rel} not in payloadutil.py")

    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe1-incident-table",
                "unit_id": C.UNIT,
                "incidents": len(table),
                "not_applicable_rows": na_rows,
                "measured_incidents": measured_ok,
                "mechanism_classes": sorted(seen_classes),
            }
        )
    )
    print(
        f"incidents={len(table)} n/a={na_rows} measured={measured_ok} "
        f"classes={sorted(seen_classes)}"
    )
    print("SUCCESS:RES-0055-probe1 incident table two-rail mapping")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
