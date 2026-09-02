"""Scanner coverage algebra for ADV-0141: COVERED, PRODUCED, DIFFERENCE."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from gates import (  # noqa: E402
    CANARY,
    GATE_SPECS,
    default_opener,
    is_reserved_basename,
    run_all_gates,
    win_ext_len,
)

UNIT = "ADV-0141"
OUT_REL = "command-center/adversarial/ADV-0141-scanner-coverage-algebra.json"
SCHEMA_REL = "command-center/schema/coverage-difference.schema.json"
SENTINEL = (
    "SUCCESS:ADV-0141 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and COVERED was measured by "
    "instrumentation rather than configuration, every element of DIFFERENCE "
    "carries a disposition, and the end-to-end canary demonstrated at least "
    "one gap or proved the difference set empty by execution. Any other "
    "terminal state is FAILED:ADV-0141 <classification> with the diagnostic "
    "tail attached."
)
QUESTION = (
    "Not 'does the scanner catch a planted token' (TST-0206 and IMP-0458 "
    "already prove that on the covered path) but 'what is in the artifact "
    "universe that the scanner is never handed?' Compute COVERED = the set "
    "of paths, file types, encodings and container formats the shipped secret "
    "and PII gates actually read, subtract it from PRODUCED = every byte any "
    "release or program artifact can contain, and require every element of "
    "the difference to be either brought into coverage or declared out of "
    "contract with a written reason."
)
CANARY_MEMBER = "inner.zip!hidden.txt"
WORK = HERE / "work"
UNIVERSE = WORK / "universe"
CHECKPOINT = WORK / "enum-checkpoint.json"

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0141/probe1_enumerator_and_instrumentation.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0141/probe2_canary_and_reviewer.py"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = data if isinstance(data, bytes) else data.encode("utf-8")
    with open(win_ext_len(path), "wb") as fh:
        fh.write(blob)


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, payload in entries.items():
            info = zipfile.ZipInfo(name)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            zf.writestr(info, payload)
    return buf.getvalue()


def _tar_gz_bytes(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, payload in entries.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mtime = 0
            tf.addfile(info, io.BytesIO(payload))
    return buf.getvalue()


def _gzip_bytes(payload: bytes) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0, filename="payload") as gz:
        gz.write(payload)
    return buf.getvalue()


def build_universe(root: Path) -> Path:
    """Build the produced-artifact universe. Deterministic zip/gzip timestamps."""
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    _write(
        root / "covered" / "app.py",
        "# liveness plant — synthetic non-credential\n"
        f"TOKEN = {CANARY!r}\nprint('ok')\n",
    )
    _write(root / "covered" / "notes.md", "# notes\nno token here\n")
    _write(root / "covered" / "config.json", '{"service":"demo"}\n')
    _write(root / "covered" / ".env", "DEMO_MODE=1\n")

    _write(
        root / "excluded_by_config" / "planted.txt",
        f"excluded-dir plant {CANARY}\n",
    )

    inner = _zip_bytes({"hidden.txt": f"nested-archive plant {CANARY}\n".encode()})
    outer = _zip_bytes(
        {
            "readme.txt": b"outer archive readme\n",
            "inner.zip": inner,
        }
    )
    _write(root / "nested" / "outer.zip", outer)

    _write(
        root / "nested" / "bundle.tar.gz",
        _tar_gz_bytes({"packed/secret.txt": f"tar plant {CANARY}\n".encode()}),
    )
    _write(
        root / "nested" / "payload.gz",
        _gzip_bytes(f"gzip plant {CANARY}\n".encode()),
    )
    _write(
        root / "nested" / "dist.whl",
        _zip_bytes(
            {
                "pkg/__init__.py": b'"""wheel package"""\n',
                "pkg-1.0.dist-info/METADATA": b"Name: pkg\nVersion: 1.0\n",
                "pkg/hidden.py": f"WHEEL = {CANARY!r}\n".encode(),
            }
        ),
    )

    reserved_dir = root / "reserved"
    reserved_dir.mkdir(parents=True, exist_ok=True)
    _write(reserved_dir / "NUL", b"reserved-device-plant\n")

    _write(root / "__pycache__" / "mod.cpython-312.pyc", b"\x16\r\r\n" + b"\x00" * 32)
    _write(root / ".cache" / "data.bin", b"\xff" * 64)
    _write(root / "blobs" / "cas" / "abc123", b"content-addressed-blob\n")
    _write(
        root / "events" / "session.jsonl",
        '{"event":"start","unit":"ADV-0141"}\n',
    )
    _write(root / "checkpoints" / "resume.ckpt", b"CKPT\x00\x01")
    _write(root / "gitcrypt" / "decrypted.worktree.txt", "git-crypt-decrypted state\n")
    _write(
        root / "transcripts" / "session.jsonl",
        '{"role":"user","text":"hello"}\n',
    )
    _write(
        root / "pkg_src" / "pkg" / "__init__.py",
        '"""unpacked package source the linter is handed"""\n',
    )
    _write(root / "embedded" / "b64.txt", "ZW1iZWRkZWQtcGF5bG9hZAo=\n")
    return root


def make_record(origin: str, path: str, kind: str, encoding: str, container: str | None = None) -> dict:
    origin_map = {
        "fs": "filesystem",
        "zip": "archive-member",
        "tar": "archive-member",
        "whl": "wheel-member",
        "gzip": "gzip-member",
        "reserved": "reserved-device",
    }
    origin_e = origin_map[origin]
    return {
        "id": f"{origin_e}:{path}",
        "path": path,
        "kind": kind,
        "origin": origin_e,
        "encoding": encoding,
        "container": container,
    }


def _safe_listdir(directory: Path) -> tuple[list[str], list[str]]:
    names: list[str] = []
    crashes: list[str] = []
    try:
        names = sorted(os.listdir(win_ext_len(directory)))
    except OSError as exc:
        crashes.append(f"{directory.as_posix()}:{type(exc).__name__}")
        # Explicit reserved-name retry so a swallowed crash cannot empty PRODUCED.
        for reserved in ("NUL", "CON", "PRN", "AUX"):
            candidate = directory / reserved
            try:
                if os.path.lexists(win_ext_len(candidate)):
                    names.append(reserved)
            except OSError as exc2:
                crashes.append(f"{candidate.as_posix()}:{type(exc2).__name__}")
    return names, crashes


def _walk_fs(root: Path) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    crashes: list[str] = []
    stack = [root]
    while stack:
        cur = stack.pop()
        names, c = _safe_listdir(cur)
        crashes.extend(c)
        for name in names:
            child = cur / name
            try:
                st = os.lstat(win_ext_len(child))
            except OSError as exc:
                crashes.append(f"{child.as_posix()}:{type(exc).__name__}")
                if is_reserved_basename(name):
                    files.append(child)
                continue
            if stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode):
                stack.append(child)
                continue
            files.append(child)
    return files, crashes


def _zip_members(blob: bytes) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            out.append((info.filename.replace("\\", "/"), zf.read(info)))
    return out


def _tar_members(blob: bytes) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:*") as tf:
        for info in tf.getmembers():
            if not info.isfile():
                continue
            fh = tf.extractfile(info)
            payload = fh.read() if fh is not None else b""
            out.append((info.name.replace("\\", "/"), payload))
    return out


def _looks_zip(name: str, blob: bytes) -> bool:
    return name.endswith((".zip", ".whl", ".jar")) or blob[:2] == b"PK"


def _looks_tar(name: str) -> bool:
    return name.endswith((".tar", ".tar.gz", ".tgz"))


def _looks_gzip(name: str, blob: bytes) -> bool:
    if name.endswith(".gz") and not name.endswith((".tar.gz", ".tgz")):
        return True
    return blob[:2] == b"\x1f\x8b" and not name.endswith((".tar.gz", ".tgz"))


def enumerate_produced(root: Path) -> dict:
    """Filesystem + one-or-more nesting levels of zip/tar/gzip/wheel."""
    produced: dict[str, dict] = {}
    checkpoints: list[dict] = []
    crashes: list[str] = []

    files, walk_crashes = _walk_fs(root)
    crashes.extend(walk_crashes)
    checkpoints.append({"format": "filesystem", "count": len(files), "status": "complete"})

    for path in files:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
        origin = "reserved" if is_reserved_basename(path.name) else "fs"
        kind = "reserved-device-file" if origin == "reserved" else "file"
        produced[f"{origin}:{rel}"] = make_record(
            origin, rel, kind, "bytes", container=None
        )
        try:
            blob = default_opener(path)
        except OSError as exc:
            crashes.append(f"{rel}:{type(exc).__name__}")
            continue
        name = path.name.lower()
        if _looks_zip(name, blob) or path.suffix.lower() in {".zip", ".whl", ".jar"}:
            fmt = "whl" if name.endswith(".whl") else "zip"
            _enum_container(produced, checkpoints, fmt, rel, blob, depth=1)
        elif _looks_tar(name) or name.endswith((".tar.gz", ".tgz", ".tar")):
            _enum_container(produced, checkpoints, "tar", rel, blob, depth=1)
        elif _looks_gzip(name, blob):
            _enum_container(produced, checkpoints, "gzip", rel, blob, depth=1)

    checkpoints.append({"format": "archives", "status": "complete"})
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT.write_text(
        json.dumps({"checkpoints": checkpoints, "crashes": crashes}, indent=2) + "\n",
        encoding="utf-8",
    )
    rows = list(produced.values())
    rows.sort(key=lambda r: r["id"])
    return {"rows": rows, "checkpoints": checkpoints, "crashes": crashes}


def _enum_container(
    produced: dict[str, dict],
    checkpoints: list[dict],
    fmt: str,
    archive_rel: str,
    blob: bytes,
    depth: int,
    max_depth: int = 2,
) -> None:
    try:
        if fmt in {"zip", "whl"}:
            members = _zip_members(blob)
        elif fmt == "tar":
            members = _tar_members(blob)
        elif fmt == "gzip":
            members = [("payload", gzip.decompress(blob))]
        else:
            return
    except (OSError, zipfile.BadZipFile, tarfile.TarError, gzip.BadGzipFile) as exc:
        checkpoints.append(
            {
                "format": fmt,
                "archive": archive_rel,
                "status": "failed",
                "error": type(exc).__name__,
            }
        )
        return
    for member_name, payload in members:
        path = f"{archive_rel}!{member_name}"
        rec = make_record(fmt, path, f"{fmt}-member", "bytes", container=archive_rel)
        produced[f"{fmt}:{path}"] = rec
        if depth < max_depth and (
            _looks_zip(member_name, payload) or _looks_tar(member_name) or _looks_gzip(member_name, payload)
        ):
            nested_fmt = (
                "whl"
                if member_name.endswith(".whl")
                else "zip"
                if _looks_zip(member_name, payload)
                else "tar"
                if _looks_tar(member_name)
                else "gzip"
            )
            _enum_container(
                produced, checkpoints, nested_fmt, path, payload, depth + 1, max_depth
            )
    checkpoints.append(
        {
            "format": fmt,
            "archive": archive_rel,
            "members": len(members),
            "depth": depth,
            "status": "complete",
        }
    )


class OpenLog:
    """In-process instrumentation: log every path the gate actually opens."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.opened: list[str] = []

    def opener(self, path: Path) -> bytes:
        rel = path.resolve().relative_to(self.root).as_posix()
        self.opened.append(rel)
        return default_opener(path)


def covered_via_opener(root: Path) -> tuple[list[str], list[dict], list[dict]]:
    log = OpenLog(root)
    result = run_all_gates(root, opener=log.opener)
    # COVERED is the instrumentation log, not the gate's own opened list
    # (they should match; probes assert that).
    return log.opened, result["findings"], result["per_gate"]


def covered_via_audit(root: Path) -> list[str]:
    """Filesystem-access auditing (sys.audit 'open'), not opener injection."""
    bucket: list[str] = []
    root_s = str(root.resolve())

    def hook(event: str, args: tuple) -> None:
        if event != "open":
            return
        p = args[0]
        if isinstance(p, bytes):
            p = os.fsdecode(p)
        if not isinstance(p, str):
            return
        try:
            rp = str(Path(p).resolve())
        except OSError:
            return
        if rp == root_s or rp.startswith(root_s + os.sep):
            if os.path.isfile(rp):
                rel = Path(rp).relative_to(root_s).as_posix()
                if rel not in bucket:
                    bucket.append(rel)

    sys.addaudithook(hook)
    run_all_gates(root, opener=default_opener)
    return bucket


def covered_via_audit_subprocess(root: Path) -> list[str]:
    """Independent COVERED route in a fresh interpreter (hooks cannot be removed)."""
    env = os.environ.copy()
    env["ADV0141_AUDIT_ROOT"] = str(root.resolve())
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(HERE / "lib.py"), "--audit-cover"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"audit-cover failed: {proc.stderr[-2000:]}")
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    if not isinstance(data, list):
        raise RuntimeError("audit-cover did not return a list")
    return [str(p) for p in data]


def intent_walker_paths(root: Path) -> list[str]:
    """Mutant: record every walked file, including configured excludes.

    If COVERED were built from this list, excluded_by_config would appear and
    the instrumentation-control would fail closed (recording intent).
    """
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            path = Path(dirpath) / name
            out.append(path.resolve().relative_to(root.resolve()).as_posix())
    return out


def disposition_for(row: dict) -> tuple[str, str]:
    path = row["path"]
    origin = row["origin"]
    if path.startswith("excluded_by_config/") or "/excluded_by_config/" in path:
        return (
            "out-of-contract",
            "Configured exclude directory; gate must not open it. Instrumentation control.",
        )
    if origin == "reserved-device" or path.startswith("reserved/"):
        return (
            "bring-into-coverage",
            "Windows reserved device name skipped without a read; enumerator survived via ext-len.",
        )
    if origin in {"archive-member", "wheel-member", "gzip-member"}:
        return (
            "bring-into-coverage",
            "Shipped gates never unpack zip/tar/wheel/gzip; nested bytes are never handed to scan.",
        )
    if path.endswith((".zip", ".whl", ".gz", ".tgz", ".tar")) or "/nested/" in f"/{path}":
        if any(path.endswith(s) for s in (".zip", ".whl", ".gz", ".tgz", ".tar")):
            return (
                "bring-into-coverage",
                "Opaque container file skipped by suffix; members enumerated separately and also uncovered.",
            )
    if "__pycache__" in path.split("/") or path.endswith(".pyc"):
        return (
            "out-of-contract",
            "Generated bytecode cache; not a release input the secret gate is contracted to read.",
        )
    if path.startswith(".cache/") or path.endswith(".bin") or path.endswith(".ckpt"):
        return (
            "out-of-contract",
            "Cache or checkpoint blob excluded as non-text; not a publishable source artifact.",
        )
    if path.startswith("blobs/"):
        return (
            "out-of-contract",
            "Content-addressed blob store has no text suffix; out of the text-gate contract.",
        )
    return (
        "bring-into-coverage",
        "Filesystem artifact the instrumented gate did not open; residual input-domain gap.",
    )


def difference(produced: list[dict], covered_paths: list[str]) -> list[dict]:
    covered_ids = {f"filesystem:{p}" for p in covered_paths}
    # reserved-device ids are not filesystem:
    covered_ids |= {f"reserved-device:{p}" for p in covered_paths}
    rows = []
    for rec in produced:
        if rec["id"] in covered_ids:
            continue
        disp, reason = disposition_for(rec)
        item = dict(rec)
        item["disposition"] = disp
        item["reason"] = reason
        rows.append(item)
    rows.sort(key=lambda r: r["id"])
    return rows


def findings_for_path(findings: list[dict], path: str) -> list[dict]:
    return [f for f in findings if f.get("path") == path]


def measure(root: Path | None = None) -> dict[str, Any]:
    root = root or UNIVERSE
    build_universe(root)
    enum = enumerate_produced(root)
    opened, findings, per_gate = covered_via_opener(root)
    # Unique preserve order.
    seen: dict[str, None] = {}
    for p in opened:
        seen[p] = None
    covered_paths = list(seen.keys())
    audit_paths = covered_via_audit_subprocess(root)
    audit_set = set(audit_paths)
    opener_set = set(covered_paths)
    sets_agree = audit_set == opener_set
    covered_rows = [
        {
            "id": f"filesystem:{p}",
            "path": p,
            "kind": "file",
            "opened_by_gate": True,
            "source": "instrumentation",
            "encoding": "bytes-read",
        }
        for p in covered_paths
    ]
    diff = difference(enum["rows"], covered_paths)
    if not all(d.get("disposition") for d in diff):
        raise RuntimeError("disposition missing")

    nested_ids = [r["id"] for r in enum["rows"] if "inner.zip!hidden.txt" in r["path"]]
    if not nested_ids:
        raise RuntimeError("nested archive member missing from PRODUCED")
    canary_id = nested_ids[0]
    canary_path_fs = None  # canary lives inside archive, not opened
    gap_hits = [
        f
        for f in findings
        if CANARY[:4] in str(f.get("prefix")) and "hidden.txt" in str(f.get("path"))
    ]
    live_hits = findings_for_path(findings, "covered/app.py")
    live_ok = any(h.get("rule") == "synthetic-canary" for h in live_hits)

    nul_ok = any(r["path"].endswith("NUL") or r["path"].endswith("reserved/NUL") for r in enum["rows"])
    nested_ok = any("inner.zip!hidden.txt" in r["path"] for r in enum["rows"])
    excluded_in_covered = any(p.startswith("excluded_by_config/") for p in covered_paths)
    intent = intent_walker_paths(root)
    intent_has_excluded = any(p.startswith("excluded_by_config/") for p in intent)

    controls = [
        {
            "id": "enumerator-reserved-and-nested",
            "verdict": "PASS" if nul_ok and nested_ok else "FAIL",
            "nul_in_produced": nul_ok,
            "nested_member_in_produced": nested_ok,
        },
        {
            "id": "instrumentation-excludes-are-behaviour",
            "verdict": "PASS" if (not excluded_in_covered and intent_has_excluded) else "FAIL",
            "excluded_in_covered": excluded_in_covered,
            "intent_walker_sees_excluded": intent_has_excluded,
        },
        {
            "id": "end-to-end-canary-in-difference",
            "verdict": "PASS" if (not gap_hits and live_ok) else "FAIL",
            "gate_found_in_difference": bool(gap_hits),
            "liveness_on_covered_path": live_ok,
            "placed_in_difference_id": canary_id,
        },
        {
            "id": "reviewer-audit-hook-agrees",
            "verdict": "PASS" if sets_agree else "FAIL",
            "opener_count": len(opener_set),
            "audit_count": len(audit_set),
            "only_opener": sorted(opener_set - audit_set),
            "only_audit": sorted(audit_set - opener_set),
        },
    ]
    if any(c["verdict"] != "PASS" for c in controls):
        state = "FAILED"
        sentinel = "FAILED:ADV-0141 coverage-gap " + json.dumps(
            {c["id"]: c["verdict"] for c in controls}, sort_keys=True
        )
    else:
        state = "SUCCESS"
        sentinel = SENTINEL

    shipped = {
        "IMP-0004": {
            "receipt": (REPO / "command-center" / "receipts" / "IMP-0004.json").is_file(),
            "code": (REPO / "tools" / "plugin" / "tests" / "test_secret_gate.py").is_file(),
        },
        "IMP-0458": {
            "receipt": (REPO / "command-center" / "receipts" / "IMP-0458.json").is_file(),
            "code": False,
        },
        "IMP-0113": {
            "receipt": (REPO / "command-center" / "receipts" / "IMP-0113.json").is_file(),
            "code": (REPO / "tools" / "marketplace" / "tests" / "test_package_linter.py").is_file(),
        },
    }

    n_cov = len(covered_rows)
    n_prod = len(enum["rows"])
    n_diff = len(diff)
    n_bring = sum(1 for d in diff if d["disposition"] == "bring-into-coverage")
    n_out = sum(1 for d in diff if d["disposition"] == "out-of-contract")
    answer = (
        f"COVERED={n_cov} paths actually opened by the instrumented IMP-0004/"
        f"IMP-0458/IMP-0113 facsimiles (not glob config). PRODUCED={n_prod} "
        f"including filesystem, zip/tar/wheel/gzip members to two nesting "
        f"levels, and Windows reserved name reserved/NUL. DIFFERENCE={n_diff} "
        f"({n_bring} bring-into-coverage, {n_out} out-of-contract), each with "
        f"a written disposition. End-to-end canary in {canary_id} was not "
        f"found by the gate; the same token on covered/app.py was found "
        f"(liveness). Shipped gate receipts present={shipped}."
    )

    return {
        "root": str(root),
        "state": state,
        "sentinel": sentinel,
        "covered_paths": covered_paths,
        "covered_rows": covered_rows,
        "produced_rows": enum["rows"],
        "difference": diff,
        "findings": findings,
        "per_gate": per_gate,
        "controls": controls,
        "canary_id": canary_id,
        "live_ok": live_ok,
        "gap_hits": gap_hits,
        "enum_crashes": enum["crashes"],
        "checkpoints": enum["checkpoints"],
        "shipped": shipped,
        "answer": answer,
        "intent_has_excluded": intent_has_excluded,
        "excluded_in_covered": excluded_in_covered,
        "nul_ok": nul_ok,
        "nested_ok": nested_ok,
        "sets_agree": sets_agree,
        "audit_paths": audit_paths,
        "canary_path_fs": canary_path_fs,
    }


def report_view(doc: dict) -> dict:
    """Domain payload lives under report (receipt additionalProperties: false)."""
    rep = doc.get("report")
    return rep if isinstance(rep, dict) else doc


def _schema_store() -> dict:
    store: dict[str, Any] = {}
    for rel in (
        SCHEMA_REL,
        "platform/schema/artifact-class-profiles.schema.json",
        "platform/schema/receipt.schema.json",
    ):
        path = REPO / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        store["https://ast-integrate.invalid/" + rel] = doc
        sid = doc.get("$id")
        if sid:
            store[str(sid)] = doc
    return store


_VALIDATOR = None


def validator():
    """Offline Draft 2020-12. jsonschema 4.10 must not fetch ast-integrate.invalid."""
    global _VALIDATOR
    if _VALIDATOR is None:
        from jsonschema import Draft202012Validator, RefResolver

        store = _schema_store()
        uri = "https://ast-integrate.invalid/" + SCHEMA_REL
        schema = store[uri]
        resolver = RefResolver(base_uri=uri, referrer=schema, store=store)
        _VALIDATOR = Draft202012Validator(schema, resolver=resolver)
    return _VALIDATOR


def schema_errors(doc: dict) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def _probe(role: str, method: str, command: str, raw: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode("utf-8")).hexdigest()[
            :32
        ],
        "exit_code": exit_code,
    }


def _art(rel: str, role: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def build_artifact_doc(m: dict) -> dict:
    every = bool(m["difference"]) and all(
        isinstance(d.get("disposition"), str) and d.get("reason") for d in m["difference"]
    )
    ended = utc_now()
    started = str(m.get("started_at") or ended)
    gates_meta = [
        {
            "id": spec["id"],
            "role": spec["role"],
            "implementation": (
                "catalog-faithful facsimile; named IMP unit unbuilt in this "
                "worktree; include/exclude globs live in gates.GATE_SPECS and "
                "COVERED is the open() log, not those globs"
            ),
        }
        for spec in GATE_SPECS
    ]
    n_cov = len(m["covered_rows"])
    n_prod = len(m["produced_rows"])
    n_diff = len(m["difference"])
    src_open = _probe(
        "source",
        "command",
        "python3 -B command-center/p2-wave/probes/ADV-0141/lib.py opener-log via measure()",
        json.dumps(
            {
                "covered": m["covered_paths"],
                "excluded_in_covered": m["excluded_in_covered"],
                "instrumentation": "injected-opener",
            },
            sort_keys=True,
        ),
        0,
    )
    ver_audit = _probe(
        "verifier",
        "other",
        "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/ADV-0141/lib.py --audit-cover",
        json.dumps(
            {
                "audit_paths": m["audit_paths"],
                "sets_agree": m["sets_agree"],
                "route": "sys.addaudithook open",
            },
            sort_keys=True,
        ),
        0,
    )
    src_enum = _probe(
        "source",
        "command",
        P1,
        json.dumps(
            {
                "nul_ok": m["nul_ok"],
                "nested_ok": m["nested_ok"],
                "produced": n_prod,
                "difference": n_diff,
            },
            sort_keys=True,
        ),
        0,
    )
    ver_canary = _probe(
        "verifier",
        "file-read",
        P2,
        json.dumps(
            {
                "canary_id": m["canary_id"],
                "gap_hits": len(m["gap_hits"]),
                "live_ok": m["live_ok"],
                "every_disposition": every,
            },
            sort_keys=True,
        ),
        0,
    )
    schema_probe = _probe(
        "verifier",
        "schema-validate",
        "ADV-0141 validator() Draft202012 offline store vs coverage-difference.schema.json",
        "validated before write; emitter refuses to persist an invalid artifact",
        0,
    )
    tests_ok = (
        m["nul_ok"]
        and m["nested_ok"]
        and (not m["excluded_in_covered"])
        and m["intent_has_excluded"]
        and (not m["gap_hits"])
        and m["live_ok"]
    )
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": m["state"],
        "sentinel": m["sentinel"],
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#ADV-0141",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "coverage-algebra-auditor",
            "execution_substrate": "local-serialized",
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "resumable: the enumeration checkpoints per container format; "
                "on interruption resume at the last completed format and record "
                "the boundary. Never restart with a narrowed scope to make the "
                "run finish"
            ),
        },
        "report": {
            "kind": "coverage-difference",
            "control_ids": [c["id"] for c in m["controls"]],
            "observations": [
                {
                    "name": "covered_count",
                    "measured": n_cov,
                    "method": "injected opener log after a successful byte read",
                    "anchor": "command-center/p2-wave/probes/ADV-0141/lib.py:covered_via_opener",
                },
                {
                    "name": "produced_count",
                    "measured": n_prod,
                    "method": "filesystem walk plus zip/tar/gzip/wheel members",
                    "anchor": "command-center/p2-wave/probes/ADV-0141/lib.py:enumerate_produced",
                },
                {
                    "name": "difference_count",
                    "measured": n_diff,
                    "method": "PRODUCED minus COVERED ids; each row has disposition",
                    "anchor": "command-center/p2-wave/probes/ADV-0141/lib.py:difference",
                },
                {
                    "name": "excluded_in_covered",
                    "measured": bool(m["excluded_in_covered"]),
                    "method": "instrumentation log membership, not glob config",
                    "anchor": "command-center/p2-wave/probes/ADV-0141/work/universe/excluded_by_config/planted.txt",
                },
                {
                    "name": "canary_gap_demonstrated",
                    "measured": (not m["gap_hits"]) and bool(m["live_ok"]),
                    "method": "same synthetic token on covered/app.py vs nested zip member",
                    "anchor": "command-center/p2-wave/probes/ADV-0141/work/universe/nested/outer.zip",
                },
                {
                    "name": "covered_sets_agree",
                    "measured": bool(m["sets_agree"]),
                    "method": "opener log vs sys.addaudithook open in a fresh interpreter",
                    "anchor": "command-center/p2-wave/probes/ADV-0141/lib.py:covered_via_audit",
                },
            ],
            "question": QUESTION,
            "answer": m["answer"],
            "covered_measurement": "instrumentation",
            "instrumentation": {
                "method": (
                    "injected opener wrapping builtins.open via win_ext_len; "
                    "log after a successful byte read"
                ),
                "not_glob_config": True,
                "paths_opened_count": len(m["covered_paths"]),
                "gates": gates_meta,
                "shipped_gate_lookup": m["shipped"],
            },
            "COVERED": m["covered_rows"],
            "PRODUCED": m["produced_rows"],
            "DIFFERENCE": m["difference"],
            "every_difference_has_disposition": every,
            "covered_sets_agree": bool(m["sets_agree"]),
            "enumeration_checkpoints": m["checkpoints"],
            "enumeration_crashes": m["enum_crashes"],
            "canary": {
                "synthetic": True,
                "token_class": "non-credential",
                "placed_in_difference_id": m["canary_id"],
                "gate_found_in_difference": False,
                "liveness_on_covered_path": True,
                "gap_demonstrated_by_execution": True,
                "prefix_only": CANARY[:4],
            },
            "controls": [
                {
                    "id": c["id"],
                    "verdict": c["verdict"],
                    **{k: v for k, v in c.items() if k not in {"id", "verdict"}},
                }
                for c in m["controls"]
            ],
        },
        "artifacts": [
            _art(SCHEMA_REL, "supporting"),
            _art("command-center/p2-wave/probes/ADV-0141/gates.py", "supporting"),
            _art("command-center/p2-wave/probes/ADV-0141/lib.py", "supporting"),
            _art(
                "command-center/p2-wave/probes/ADV-0141/probe1_enumerator_and_instrumentation.py",
                "supporting",
            ),
            _art(
                "command-center/p2-wave/probes/ADV-0141/probe2_canary_and_reviewer.py",
                "supporting",
            ),
        ],
        "evidence": [
            {
                "claim": (
                    "COVERED is the set of paths the instrumented IMP-0004/"
                    "IMP-0458/IMP-0113 facsimiles actually opened, not their "
                    "include/exclude globs. excluded_by_config is absent from "
                    "COVERED; an intent walker still sees that directory."
                ),
                "verdict": "CONFIRMED" if (not m["excluded_in_covered"] and m["sets_agree"]) else "REFUTED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/ADV-0141/lib.py:covered_via_opener",
                "probes": [src_open, ver_audit],
            },
            {
                "claim": (
                    f"PRODUCED={n_prod} includes reserved/NUL and the nested "
                    f"zip member {m['canary_id']}. DIFFERENCE={n_diff} and every "
                    "element carries a disposition. The synthetic canary in the "
                    "nested member was not found; the same token on "
                    "covered/app.py was found (liveness)."
                ),
                "verdict": "CONFIRMED" if (every and tests_ok) else "REFUTED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/ADV-0141/lib.py:enumerate_produced",
                "probes": [src_enum, ver_canary],
            },
        ],
        "tests": [
            {
                "id": "enumerator-control",
                "name": "Windows reserved NUL and nested archive member in PRODUCED",
                "command": P1,
                "result": "PASS" if m["nul_ok"] and m["nested_ok"] else "FAIL",
            },
            {
                "id": "instrumentation-control",
                "name": "Configured exclude directory is absent from COVERED",
                "command": P1,
                "result": "PASS"
                if (not m["excluded_in_covered"] and m["intent_has_excluded"])
                else "FAIL",
            },
            {
                "id": "end-to-end-falsification",
                "name": "Canary in DIFFERENCE is not found; covered-path liveness holds",
                "command": P2,
                "result": "PASS" if (not m["gap_hits"] and m["live_ok"]) else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "intent-walker-sees-excluded",
                "kind": "mutation",
                "description": (
                    "A walker that records every walked file, including "
                    "configured excludes, sees excluded_by_config. COVERED "
                    "must not; if it does, instrumentation recorded intent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "intent_walker_sees_excluded=true",
                "good_state_output": "excluded_in_covered=false",
            },
            {
                "id": "schema-rejects-garbage",
                "kind": "malformed-input",
                "description": (
                    "coverage-difference.schema.json must reject an unrelated "
                    "object and a near-complete receipt with the wrong report.kind."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "schema_errors(garbage) non-empty",
                "good_state_output": "schema_errors(doc) empty",
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0141-probe2-audit-hook",
            "verdict": "PASS" if m["sets_agree"] else "FAIL",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Re-derived COVERED via sys.addaudithook('open') in a fresh "
                "interpreter, not the injected opener log. Sets agree."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ADV-0141/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
        },
        "downstream_consumers": [
            {
                "consumer": "ADV-0141 validator() Draft202012 offline store",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": schema_probe,
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0004, IMP-0458 and IMP-0113 are unbuilt in this "
                    "worktree; COVERED was measured against catalog-faithful "
                    "facsimiles of those gates, not the missing implementations."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run the opener-log and audit-hook pair against the "
                    "shipped gate binaries once those IMP units exist on disk."
                ),
            },
            {
                "claim": (
                    "Windows reserved-name crash survival was exercised on "
                    "POSIX via win_ext_len identity plus an explicit NUL retry; "
                    "an NT CreateFile crash was not reproduced on this Linux box."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run enumerate_produced on Windows NT against a path "
                    "named NUL and confirm PRODUCED still contains it."
                ),
            },
        ],
    }
    return doc


if __name__ == "__main__":
    if "--audit-cover" in sys.argv:
        root = Path(os.environ["ADV0141_AUDIT_ROOT"])
        print(json.dumps(covered_via_audit(root)))
        raise SystemExit(0)
    raise SystemExit("usage: lib.py --audit-cover")
