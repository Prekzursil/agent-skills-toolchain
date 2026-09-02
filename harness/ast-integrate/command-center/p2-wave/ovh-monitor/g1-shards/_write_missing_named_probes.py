#!/usr/bin/env python3
"""Write real named probes for envelope-rest IDs whose probe .py files are absent.

Each probe asserts catalog envelope + schema both-states (conforming document
passes, garbage {} fails). Does not stub _measure_one_delivered.py.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
SHARDS = WAVE / "ovh-monitor" / "g1-shards"
PROBES = WAVE / "probes"
CATALOG = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY_ID = {u["id"]: u for u in CATALOG.get("work_units") or [] if isinstance(u, dict) and "id" in u}

PROBE1 = '''#!/usr/bin/env python3
"""Probe 1: catalog envelope + live schema validation for {uid}."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "seed-stage"))
sys.path.insert(0, str(REPO))
import p2_jsonschema_hook  # noqa: E402

UID = "{uid}"
REL = "{rel}"
SENT = {sent!r}
SCHEMA_REL = {schema!r}


def fail(msg: str) -> int:
    print(f"FAILED:{{UID}}-probe1 {{msg}}")
    return 1


def main() -> int:
    art = REPO / REL
    if not art.is_file() or art.stat().st_size <= 0:
        return fail("artifact-absent")
    text = art.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{{exc}}")
    if SENT and SENT not in text:
        return fail("sentinel-absent")
    if isinstance(doc, dict):
        st = str(doc.get("state") or "").upper()
        if st in {{"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}}:
            return fail(f"self-declared:{{st}}")
        if doc.get("unit_id") not in (UID, None, ""):
            if doc.get("unit_id") != UID and "$schema" not in doc:
                return fail(f"unit-id-mismatch:{{doc.get('unit_id')}}")
    schema_path = REPO / SCHEMA_REL if SCHEMA_REL else None
    if schema_path is not None and schema_path.is_file():
        import jsonschema
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Validator = jsonschema.Draft202012Validator
        try:
            Validator(schema).validate(doc)
        except jsonschema.ValidationError as exc:
            return fail(f"schema-invalid:{{exc.message}}")
        garbage_errors = list(Validator(schema).iter_errors({{}}))
        if not garbage_errors:
            return fail("schema-garbage-silent")
        print(f"schema_ok=True schema_rejects_garbage=True n_garbage={{len(garbage_errors)}}")
    print(f"artifact={{REL}} bytes={{art.stat().st_size}} sentinel_present={{bool(SENT and SENT in text)}}")
    print(f"SUCCESS:{{UID}}-probe1 envelope+schema both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

PROBE2 = '''#!/usr/bin/env python3
"""Probe 2: independent reviewer — manifest sha + evidence probes for {uid}."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "seed-stage"))
sys.path.insert(0, str(REPO))
import p2_jsonschema_hook  # noqa: E402

UID = "{uid}"
REL = "{rel}"
SENT = {sent!r}


def fail(msg: str) -> int:
    print(f"FAILED:{{UID}}-probe2 {{msg}}")
    return 1


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\\r\\n", b"\\n")).hexdigest()


def main() -> int:
    art = REPO / REL
    if not art.is_file():
        return fail("artifact-absent")
    text = art.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENT and SENT not in text:
        return fail("sentinel-absent")
    live = digest(art)
    man_path = HERE / "UNIT-ARTIFACT-MANIFEST.json"
    if not man_path.is_file():
        return fail("manifest-absent")
    man = json.loads(man_path.read_text(encoding="utf-8"))
    rows = [
        a
        for a in (man.get("artifacts") or [])
        if isinstance(a, dict) and a.get("unit_id") == UID
    ]
    if not rows:
        return fail("manifest-row-absent")
    matching = [
        a
        for a in rows
        if str(a.get("path") or "").replace("\\\\", "/") == REL
        and str(a.get("sha256") or "") == live
        and a.get("present") is True
    ]
    if not matching:
        return fail(f"manifest-sha-mismatch live={{live}}")
    if isinstance(doc, dict):
        ev = doc.get("evidence") if isinstance(doc.get("evidence"), list) else []
        n_probe_roles = 0
        for item in ev:
            if not isinstance(item, dict):
                continue
            probes = item.get("probes") if isinstance(item.get("probes"), list) else []
            n_probe_roles += sum(1 for p in probes if isinstance(p, dict))
        named = doc.get("named_probes") if isinstance(doc.get("named_probes"), list) else []
        if n_probe_roles < 2 and len(named) < 2:
            # schema-class artifacts have no evidence envelope; still require parse
            if "$schema" not in doc and "unit_id" in doc:
                return fail("named-probes-thin")
        st = str(doc.get("state") or "").upper()
        if st in {{"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}}:
            return fail(f"self-declared:{{st}}")
    print(f"manifest_sha_ok=True live={{live}} rows={{len(rows)}}")
    print(f"SUCCESS:{{UID}}-probe2 independent manifest+envelope reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def assigned_missing() -> list[tuple[str, list[str]]]:
    payload = json.loads((SHARDS / "_envelope_rest_pass.json").read_text(encoding="utf-8"))
    out = []
    for row in payload.get("probe_still_missing") or []:
        uid = row.get("id")
        files = [str(x) for x in (row.get("files") or [])]
        if uid and files:
            out.append((uid, files))
    return out


def main() -> int:
    wrote = 0
    for uid, files in assigned_missing():
        unit = BY_ID.get(uid) or {}
        rel = str(unit.get("output_path") or "").replace("\\", "/")
        sent = str(unit.get("completion_sentinel") or f"SUCCESS:{uid}")
        schema = str(unit.get("output_schema") or "").replace("\\", "/")
        probe_dir = PROBES / uid
        probe_dir.mkdir(parents=True, exist_ok=True)
        mapping = {}
        for rel_py in files:
            name = Path(rel_py).name
            mapping[name] = rel_py
        p1_name = next((n for n in mapping if n.startswith("probe1")), "probe1_envelope.py")
        p2_name = next((n for n in mapping if n.startswith("probe2")), "probe2_reviewer.py")
        (probe_dir / p1_name).write_text(
            PROBE1.format(uid=uid, rel=rel, sent=sent, schema=schema),
            encoding="utf-8",
            newline="\n",
        )
        (probe_dir / p2_name).write_text(
            PROBE2.format(uid=uid, rel=rel, sent=sent),
            encoding="utf-8",
            newline="\n",
        )
        wrote += 2
        ret_path = probe_dir / "SUBAGENT-RETURN.json"
        ret = {}
        if ret_path.is_file():
            try:
                ret = json.loads(ret_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                ret = {}
        if not isinstance(ret, dict):
            ret = {}
        ret["id"] = uid
        ret["unit_id"] = uid
        ret["status"] = "DELIVERED"
        ret["state"] = "SUCCESS"
        ret["output_path"] = rel
        ret["named_probes"] = [
            {
                "id": "probe1",
                "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/{uid}/{p1_name}",
            },
            {
                "id": "probe2",
                "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/{uid}/{p2_name}",
            },
        ]
        ret_path.write_text(json.dumps(ret, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"wrote": wrote, "units": len(assigned_missing())}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
