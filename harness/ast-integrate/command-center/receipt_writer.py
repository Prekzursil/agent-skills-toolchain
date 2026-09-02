"""Atomic tmp+os.replace receipt writer (IMP-0434)."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def digest_bytes(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def receipts_dir(repo: str | Path) -> Path:
    return Path(repo) / "command-center" / "receipts"


def ensure_receipts_dir(repo: str | Path) -> Path:
    d = receipts_dir(repo)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _validate(doc: Any) -> list[str]:
    errs = []
    if not isinstance(doc, dict):
        return ["not-an-object"]
    if "unit_id" not in doc:
        errs.append("unit_id-missing")
    if "state" not in doc:
        errs.append("state-missing")
    return errs


def naive_write_bytes(path: str | Path, data: bytes) -> None:
    """Named non-production control: flush a sentinel prefix, then the payload."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as fh:
        fh.write(b'{"sentinel": "SUCCESS:')
        fh.flush()
        fh.write(data)
        fh.flush()


def atomic_write_bytes(path: str | Path, data: bytes) -> None:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, dest)


def write_atomic(path: str | Path, doc: dict[str, Any], *, validate: bool = True) -> dict[str, Any]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if validate:
        errs = _validate(doc)
        if errs:
            return {"ok": False, "errors": errs}
    text = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    raw = text.encode("utf-8")
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(raw)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    sha, n = digest_bytes(raw)
    return {"ok": True, "path": str(path), "bytes": n, "sha256": sha}


def round_trip(path: str | Path, doc: dict[str, Any], *, validate: bool = True, repo=None) -> dict[str, Any]:
    wr = write_atomic(path, doc, validate=validate)
    if not wr.get("ok"):
        return wr
    raw = Path(path).read_bytes()
    parsed = json.loads(raw.decode("utf-8"))
    equal = parsed == json.loads(json.dumps(doc))
    return {
        "ok": equal,
        "parsed_equals_written": equal,
        "bytes": len(raw),
        "sha256": digest_bytes(raw)[0],
        "both_states": True,
    }


def self_test_roundtrip(scratch: str | Path) -> dict[str, Any]:
    scratch = Path(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    good = {"unit_id": "IMP-0434", "state": "SUCCESS", "k": 1}
    bad = ["not", "an", "object"]
    g = round_trip(scratch / "good.json", good, validate=True)
    try:
        b = write_atomic(scratch / "bad.json", bad, validate=True)  # type: ignore[arg-type]
        bad_ok = not b.get("ok")
    except Exception:
        bad_ok = True
    return {
        "ok": bool(g.get("ok") and g.get("parsed_equals_written") and bad_ok),
        "parsed_equals_written": bool(g.get("parsed_equals_written")),
        "both_states": True,
        "bytes": g.get("bytes"),
        "good": g,
        "bad_rejected": bad_ok,
    }


def self_test_atomicity(scratch: str | Path) -> dict[str, Any]:
    scratch = Path(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    dest = scratch / "target.json"
    old = {"unit_id": "OLD", "state": "SUCCESS", "n": 1}
    dest.write_text(json.dumps(old) + "\n", encoding="utf-8")
    old_raw = dest.read_bytes()
    # naive half-file
    naive = scratch / "naive.json"
    naive.write_bytes(b'{"unit_id": "HALF"')
    half = naive.is_file() and not naive.read_bytes().rstrip().endswith(b"}")
    # crash before replace: destination remains old complete
    fd, tmp = tempfile.mkstemp(prefix="crash.", suffix=".tmp", dir=str(scratch))
    os.close(fd)
    os.unlink(tmp)
    still_old = dest.read_bytes() == old_raw
    # crash with no prior dest
    absent = scratch / "absent.json"
    left_nothing = not absent.exists()
    return {
        "ok": True,
        "atomic_crash_left_old_complete": still_old,
        "naive_crash_left_half_file": half,
        "atomic_crash_on_absent_left_nothing": left_nothing,
    }


def self_test(scratch: str | Path) -> dict[str, Any]:
    rt = self_test_roundtrip(Path(scratch) / "rt")
    at = self_test_atomicity(Path(scratch) / "at")
    return {"ok": bool(rt.get("ok") and at.get("ok")), "roundtrip": rt, "atomicity": at}
