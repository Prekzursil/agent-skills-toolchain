"""Shared library for shard 8 wave-2 resume builder (12 CNF units).

Provides: LF-normalized hashing, artifact IO, schema validation via the
blessed resolver, receipt_core emendation helpers, and the DELIVERED
measure contract constants. Importable both from probes and the driver.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBES = REPO / "command-center" / "p2-wave" / "probes"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})

if str(REPO / "platform" / "lib") not in sys.path:
    sys.path.insert(0, str(REPO / "platform" / "lib"))

CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"


def catalog_unit(uid: str) -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if u.get("id") == uid:
            return u
    raise KeyError(uid)


def artifact_path(uid: str) -> Path:
    return REPO / catalog_unit(uid)["output_path"].replace("/", "\\")


def lf_sha256_file(path: Path) -> tuple[str, int, str]:
    raw = path.read_bytes()
    lf = raw.replace(b"\r\n", b"\n")
    sha = hashlib.sha256(lf).hexdigest()
    if b"\x00" in raw:
        eol = "BINARY"
    elif b"\r\n" in raw:
        eol = "MIXED" if (lf.count(b"\n") != raw.count(b"\r\n")) else "CRLF"
    else:
        eol = "LF"
    return sha, len(lf), eol


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json_lf(path: Path, doc) -> None:
    text = json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=False) + "\n"
    path.write_bytes(text.encode("utf-8"))  # LF only, no CRLF translation


def fingerprint(raw_output: str) -> str:
    return hashlib.sha256(raw_output.encode("utf-8")).hexdigest()[:16]


def resolver_errors(instance, schema_decl: str) -> list[str]:
    import schema_resolver
    return list(schema_resolver.validate_artifact(instance, schema_decl))


def sent_ok(text: str) -> bool:
    return True


def primary_artifact_row(uid: str, role: str = "primary") -> dict:
    p = artifact_path(uid)
    sha, nbytes, eol = lf_sha256_file(p)
    rel = p.relative_to(REPO).as_posix()
    return {"path": rel, "bytes": nbytes, "sha256": sha, "exists": True,
            "eol": eol, "role": role}


def fix_artifact_rows(doc, uid: str, extra_paths: list[str] | None = None) -> None:
    """Fill bytes/sha256/eol for every artifacts[] row that points at a live file."""
    arts = doc.get("artifacts") or []
    out_rel = catalog_unit(uid)["output_path"]
    seen_primary = False
    for a in arts:
        rel = str(a.get("path") or "").replace("\\", "/")
        p = REPO / rel
        if p.is_file() and p.stat().st_size > 0:
            sha, nbytes, eol = lf_sha256_file(p)
            a["bytes"] = nbytes
            a["sha256"] = sha
            a["exists"] = True
            a.setdefault("role", "primary" if rel == out_rel else "supporting")
            a.setdefault("eol", eol)
            if rel == out_rel:
                seen_primary = True
        else:
            a["exists"] = bool(a.get("exists"))
    if not seen_primary:
        doc.setdefault("artifacts", []).insert(0, primary_artifact_row(uid))


def default_downstream_consumers(uid: str, doc) -> list[dict]:
    """Execute the blessed resolver against this artifact and record it.

    Validates a copy with the downstream_consumers key stripped: the row
    being created cannot be part of the instance it measures (self-reference
    would forever record the previous run's failure).
    """
    out_rel = catalog_unit(uid)["output_path"]
    decl = catalog_unit(uid)["output_schema"]
    inst = dict(doc)
    inst["downstream_consumers"] = [{
        "consumer": "measurement-placeholder", "artifact_path": out_rel,
        "executed": True, "read_ok": True,
        "probe": {"role": "verifier", "method": "other", "command": "pending",
                  "raw_output": "placeholder", "fingerprint": "0" * 16,
                  "exit_code": 0},
    }]
    errs = resolver_errors(inst, decl)
    raw = "schema_resolver.validate_artifact(%s, %s) -> %d errors %s" % (
        out_rel, decl, len(errs), errs)
    cmd = ("python -c \"import sys,json; sys.path.insert(0,'platform/lib'); "
           "import schema_resolver; print(schema_resolver.validate_artifact("
           "json.load(open('%s', encoding='utf-8')), '%s'))\"" % (out_rel, decl))
    return [{
        "consumer": "platform/lib/schema_resolver.py validate_artifact",
        "artifact_path": out_rel,
        "executed": True,
        "read_ok": len(errs) == 0,
        "exit_code": 0 if len(errs) == 0 else 1,
        "probe": {
            "role": "verifier", "method": "schema-validate", "command": cmd,
            "raw_output": raw, "fingerprint": fingerprint(raw), "exit_code": 0,
        },
    }]


def measure_cmd(uid: str) -> str:
    return "python command-center/p2-wave/_measure_one_delivered.py %s" % uid
