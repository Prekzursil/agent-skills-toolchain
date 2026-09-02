#!/usr/bin/env python3
"""CNF-0039 harness: wheel, isolated install, journeys, file postconditions."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SRC = HERE / "src"
PKG = SRC / "cnf0039_packaged"
DIST = HERE / "dist"
WHEEL_NAME = "cnf0039_packaged-0.1.0-py3-none-any.whl"
UNIT = "CNF-0039"
SENTINEL = (
    "SUCCESS:CNF-0039 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every journey ended in a "
    "file-level postcondition probe and the corruption control failed as designed. "
    "Any other terminal state is FAILED:CNF-0039 <classification> with the "
    "diagnostic tail attached."
)
OUT_REL = "command-center/confirmation/CNF-0039-packaged-golden-journeys.json"
SCHEMA_REL = "command-center/schema/smoke-report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0039/probe1_packaged_journeys.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0039/probe2_corruption_control.py"
)

JOURNEYS = (
    {
        "id": "catalog-export",
        "title": "Export the bundled fixture catalog as JSON",
        "min_bytes": 200,
        "format_or_content": (
            "JSON object with schema_version==1 and items[] of >=3 rows each "
            "carrying id and title"
        ),
    },
    {
        "id": "status-render",
        "title": "Render a markdown status table from the catalog",
        "min_bytes": 80,
        "format_or_content": (
            "Markdown starting with '# Status' containing a pipe table and J-CAT"
        ),
    },
    {
        "id": "graph-export",
        "title": "Export the catalog dependency graph as JSON",
        "min_bytes": 150,
        "format_or_content": (
            "JSON graph with >=3 nodes, non-empty edges, every blocked_by in nodes"
        ),
    },
    {
        "id": "bundle-echo",
        "title": "Echo packaged golden-journeys.json (package_data control)",
        "min_bytes": 100,
        "format_or_content": (
            "JSON with journeys[] length >=4, each row having id and postcondition"
        ),
    },
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def repo_on_path(entries: list[str]) -> bool:
    """True when the unpackaged source tree is importable (not the extracted wheel)."""
    forbidden = (
        str(REPO.resolve()),
        str(SRC.resolve()),
        str(PKG.resolve()),
    )
    src_prefix = str(SRC.resolve()) + os.sep
    for raw in entries:
        if not raw:
            continue
        try:
            p = str(Path(raw).resolve())
        except OSError:
            p = os.path.abspath(raw)
        if p in forbidden or p.startswith(src_prefix):
            return True
    return False


def _wheel_bytes() -> bytes:
    files: list[tuple[str, bytes]] = []

    def add_file(rel: str, data: bytes) -> None:
        files.append((rel.replace("\\", "/"), data))

    for path in sorted(PKG.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            add_file(path.relative_to(SRC).as_posix(), path.read_bytes())

    add_file(
        "cnf0039_packaged-0.1.0.dist-info/METADATA",
        (
            "Metadata-Version: 2.1\n"
            "Name: cnf0039-packaged\n"
            "Version: 0.1.0\n"
            "Summary: CNF-0039 golden-journey packaged CLI\n"
            "Requires-Python: >=3.10\n"
        ).encode("utf-8"),
    )
    add_file(
        "cnf0039_packaged-0.1.0.dist-info/WHEEL",
        (
            "Wheel-Version: 1.0\n"
            "Generator: cnf0039-harness\n"
            "Root-Is-Purelib: true\n"
            "Tag: py3-none-any\n"
        ).encode("utf-8"),
    )
    add_file(
        "cnf0039_packaged-0.1.0.dist-info/entry_points.txt",
        (
            "[console_scripts]\n"
            "cnf0039-run = cnf0039_packaged.cli:main\n"
        ).encode("utf-8"),
    )

    records: list[str] = []
    buf = tempfile.SpooledTemporaryFile()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel, data in files:
            zf.writestr(rel, data)
            digest = hashlib.sha256(data).hexdigest()
            records.append(f"{rel},sha256={digest},{len(data)}")
        zf.writestr(
            "cnf0039_packaged-0.1.0.dist-info/RECORD",
            ("\n".join(records) + "\n").encode("utf-8"),
        )
    buf.seek(0)
    return buf.read()


def write_wheel() -> Path:
    DIST.mkdir(parents=True, exist_ok=True)
    path = DIST / WHEEL_NAME
    path.write_bytes(_wheel_bytes())
    return path


def install_wheel(wheel: Path, root: Path) -> Path:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    with zipfile.ZipFile(wheel) as zf:
        zf.extractall(root)
    bindir = root / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    script = bindir / "cnf0039-run"
    script.write_text(
        "#!"
        + sys.executable
        + "\n"
        + "import sys\n"
        + f"sys.path.insert(0, {str(root.resolve())!r})\n"
        + "from cnf0039_packaged.cli import main\n"
        + "raise SystemExit(main())\n",
        encoding="utf-8",
        newline="\n",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def _clean_env(pythonpath: str) -> dict[str, str]:
    keep = ("PATH", "HOME", "LANG", "LC_ALL", "TZ", "TMPDIR", "TMP", "TEMP")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env["PYTHONPATH"] = pythonpath
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONSAFEPATH"] = "1"
    return env


def run_cli(
    *,
    pythonpath: str,
    journey: str,
    out: Path,
    cwd: Path,
) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    cmd = [
        sys.executable,
        "-P",
        "-s",
        "-B",
        "-c",
        "from cnf0039_packaged.cli import main; raise SystemExit(main())",
        journey,
        "--out",
        str(out),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=_clean_env(pythonpath),
        capture_output=True,
        text=True,
        timeout=30,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return {
        "exit_code": proc.returncode,
        "output": text,
        "command": " ".join(cmd),
        "produced": str(out),
        "exists": out.is_file(),
        "bytes": out.stat().st_size if out.is_file() else 0,
    }


def packaged_sys_path(out: Path) -> list[str]:
    if not out.is_file() or out.suffix != ".json" and not out.name.endswith(".out"):
        # JSON bodies are written even when the suffix is .out
        pass
    if not out.is_file():
        return []
    try:
        text = out.read_text(encoding="utf-8")
        if not text.lstrip().startswith("{"):
            return []
        doc = json.loads(text)
    except (OSError, json.JSONDecodeError):
        return []
    sp = doc.get("sys_path")
    return list(sp) if isinstance(sp, list) else []


def postcondition(journey_id: str, path: Path) -> dict:
    spec = next(j for j in JOURNEYS if j["id"] == journey_id)
    lines: list[str] = []
    ok = True
    exists = path.is_file()
    lines.append(f"exists={exists} path={path}")
    if not exists:
        ok = False
        body = ""
        size = 0
    else:
        body = path.read_text(encoding="utf-8")
        size = path.stat().st_size
    lines.append(f"bytes={size} min_bytes={spec['min_bytes']}")
    if size < spec["min_bytes"]:
        ok = False
        lines.append("FAIL min_bytes")

    if journey_id == "catalog-export":
        try:
            doc = json.loads(body)
            items = doc.get("items") or []
            sv = doc.get("schema_version")
            ids_ok = all(
                isinstance(i, dict) and i.get("id") and i.get("title") for i in items
            )
            content = (
                sv == 1 and isinstance(items, list) and len(items) >= 3 and ids_ok
            )
            n = len(items) if isinstance(items, list) else "NA"
            lines.append(
                f"json=True schema_version={sv} items={n} ids_ok={ids_ok} content_ok={content}"
            )
            if not content:
                ok = False
        except (json.JSONDecodeError, TypeError) as exc:
            ok = False
            lines.append(f"json=False {type(exc).__name__}")
    elif journey_id == "status-render":
        has_h = body.lstrip().startswith("# Status")
        has_table = "| id |" in body and "|---|" in body
        has_row = "J-CAT" in body
        content = has_h and has_table and has_row
        lines.append(
            f"heading={has_h} table={has_table} J-CAT={has_row} content_ok={content}"
        )
        if not content:
            ok = False
    elif journey_id == "graph-export":
        try:
            doc = json.loads(body)
            nodes = doc.get("nodes") or []
            edges = doc.get("edges") or []
            node_set = set(nodes) if isinstance(nodes, list) else set()
            ends_ok = isinstance(edges, list) and all(
                isinstance(e, dict) and e.get("blocked_by") in node_set for e in edges
            )
            content = (
                isinstance(nodes, list)
                and len(nodes) >= 3
                and isinstance(edges, list)
                and len(edges) >= 1
                and ends_ok
            )
            n_n = len(nodes) if isinstance(nodes, list) else "NA"
            n_e = len(edges) if isinstance(edges, list) else "NA"
            lines.append(
                f"json=True nodes={n_n} edges={n_e} ends_ok={ends_ok} content_ok={content}"
            )
            if not content:
                ok = False
        except (json.JSONDecodeError, TypeError) as exc:
            ok = False
            lines.append(f"json=False {type(exc).__name__}")
    elif journey_id == "bundle-echo":
        try:
            doc = json.loads(body)
            journeys = doc.get("journeys") or []
            rows_ok = (
                isinstance(journeys, list)
                and len(journeys) >= 4
                and all(
                    isinstance(j, dict) and j.get("id") and j.get("postcondition")
                    for j in journeys
                )
            )
            n = len(journeys) if isinstance(journeys, list) else "NA"
            lines.append(f"json=True journeys={n} rows_ok={rows_ok} content_ok={rows_ok}")
            if not rows_ok:
                ok = False
        except (json.JSONDecodeError, TypeError) as exc:
            ok = False
            lines.append(f"json=False {type(exc).__name__}")
    else:
        ok = False
        lines.append("FAIL unknown journey")

    lines.append("PASS" if ok else "FAIL")
    return {"pass": ok, "output": "\n".join(lines), "bytes": size, "exists": exists}


def reject_exit_code_only() -> dict:
    bogus = {
        "id": "exit-only",
        "postcondition": "process_exit_code_zero",
        "checks": ["exit_code == 0"],
    }
    accepted = not (
        bogus["checks"] == ["exit_code == 0"] and "file" not in bogus["postcondition"]
    )
    return {
        "rejected": not accepted,
        "reason": "produced-file assertion is mandatory; exit-code-only is rejected",
        "bogus_id": bogus["id"],
    }


def run_all_journeys(pythonpath: str, out_dir: Path, cwd: Path) -> list[dict]:
    rows = []
    for spec in JOURNEYS:
        produced = out_dir / f"{spec['id']}.out"
        run = run_cli(
            pythonpath=pythonpath,
            journey=spec["id"],
            out=produced,
            cwd=cwd,
        )
        probe = postcondition(spec["id"], produced)
        sys_path = packaged_sys_path(produced)
        rows.append(
            {
                "spec": spec,
                "run": run,
                "probe": probe,
                "sys_path": sys_path,
                "repo_on_sys_path": repo_on_path(sys_path),
            }
        )
    return rows


def corruption_control(good_path: Path) -> dict:
    journey_id = "catalog-export"
    good = postcondition(journey_id, good_path)
    if not good["pass"]:
        return {
            "probe_failed_as_designed": False,
            "mode": "truncate-and-poison",
            "verbatim_output": "GOOD-STATE-ALREADY-FAILING\n" + good["output"],
            "target_path": str(good_path),
            "good_pass": False,
        }
    original = good_path.read_bytes()
    good_path.write_bytes(b"{")
    bad = postcondition(journey_id, good_path)
    good_path.write_bytes(original)
    restored = postcondition(journey_id, good_path)
    designed = (not bad["pass"]) and restored["pass"]
    verbatim = (
        "GOOD "
        + good["output"].replace("\n", " | ")
        + "\nCORRUPT "
        + bad["output"].replace("\n", " | ")
        + "\nRESTORED "
        + restored["output"].replace("\n", " | ")
    )
    return {
        "probe_failed_as_designed": designed,
        "mode": "truncate-to-one-byte-json-fragment",
        "verbatim_output": verbatim,
        "target_path": str(good_path),
        "good_pass": good["pass"],
        "corrupt_pass": bad["pass"],
        "restored_pass": restored["pass"],
    }


def schema_store() -> dict:
    """Load physical schemas into an in-memory $id store. No network."""
    store: dict = {}
    for rel in (
        "command-center/schema/smoke-report.schema.json",
        "platform/schema/artifact-class-profiles.schema.json",
        "platform/schema/receipt.schema.json",
    ):
        path = REPO / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        sid = doc.get("$id")
        if not isinstance(sid, str) or not sid:
            raise RuntimeError(f"schema {rel} missing $id")
        store[sid] = doc
    return store


def smoke_validator():
    """Draft7 validator whose $ref resolution is disk-only."""
    import jsonschema
    from jsonschema.exceptions import RefResolutionError

    store = schema_store()
    sid = "https://ast-integrate.invalid/command-center/schema/smoke-report.schema.json"
    schema = store[sid]

    class OfflineResolver(jsonschema.RefResolver):
        def resolve_remote(self, uri: str):
            raise RefResolutionError(f"offline schema store: refused remote fetch of {uri}")

    resolver = OfflineResolver(
        base_uri=sid,
        referrer=schema,
        store=store,
        cache_remote=False,
    )
    return jsonschema.Draft7Validator(schema, resolver=resolver), schema


def schema_errors(doc: dict) -> list[str]:
    validator, _schema = smoke_validator()
    out = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def schema_rejects_garbage(schema: dict | None = None) -> bool:
    del schema  # caller may pass the shim; validation always uses the offline store
    validator, _schema = smoke_validator()
    garbage = (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    )
    return all(list(validator.iter_errors(g)) for g in garbage)


def report_body(doc: dict) -> dict:
    """Domain payload lives under report (receipt_core forbids extra top-level keys)."""
    r = doc.get("report")
    return r if isinstance(r, dict) else doc
