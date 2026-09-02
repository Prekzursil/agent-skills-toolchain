"""Filesystem enumeration and clean-temp smoke-run for CNF-0077.

The live library list is built ONLY from paths that exist on disk. The catalog
claim is read afterwards, never used as the member list. A blueprint that loads
and runs but writes no artifact is a failure, not executable.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE_LIB = HERE / "fixtures" / "library"
FIXTURE_SCRIPTS = HERE / "fixtures" / "scripts"
CATALOG_CLAIM_FILE = HERE / "fixtures" / "catalog_claim.json"

LIVE_LIBRARY_FILES = (
    "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/sources/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
)
LIVE_LIBRARY_DIRS = (
    "platform/workflows",
    "workflows",
)

PLACEHOLDER_KEYS = ("discovery_only", "placeholder", "is_placeholder")
BLUEPRINT_KINDS = frozenset(
    {
        "workflow_blueprint",
        "blueprint",
        "workflow",
        "subworkflow",
        "meta-workflow",
    }
)
UNSUPPORTED_STAGE_KINDS = frozenset(
    {
        "static-scan",
        "write-config",
        "agent",
        "llm",
        "task",
        "gate",
        "fanout",
        "barrier",
        "human_checkpoint",
        "subworkflow",
        "loop",
        "condition",
    }
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def looks_like_blueprint(doc: Any) -> bool:
    if not isinstance(doc, dict):
        return False
    kind = str(doc.get("kind") or doc.get("artifact_class") or "")
    if kind in BLUEPRINT_KINDS:
        return True
    stages = doc.get("stages")
    if isinstance(stages, list) and ("id" in doc or "name" in doc):
        return True
    return False


def is_enumerable_library_path(path: Path) -> bool:
    """Keep unparseable files and blueprint-shaped docs; drop status/report JSON."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return True
    if looks_like_blueprint(doc):
        return True
    if isinstance(doc, list):
        return any(isinstance(x, dict) and looks_like_blueprint(x) for x in doc)
    if isinstance(doc, dict):
        for key in ("blueprints", "entries", "items", "workflows", "library"):
            val = doc.get(key)
            if isinstance(val, list) and any(
                isinstance(x, dict) and looks_like_blueprint(x) for x in val
            ):
                return True
    return False


def row(
    *,
    bid: str,
    path: str,
    invocation: str,
    exit_code: int,
    classification: str,
    artifact_path: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": bid,
        "path": path,
        "invocation": invocation,
        "exit_code": int(exit_code),
        "classification": classification,
    }
    if artifact_path:
        out["artifact_path"] = artifact_path
    if error:
        out["error"] = error
    if not artifact_path and not error:
        out["error"] = "missing-artifact-and-error"
    return out


def expand_library_file(path: Path, rel: str) -> list[tuple[str, Path, dict | None, str | None]]:
    """Return (id, path, parsed_doc_or_None, load_error)."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [(path.stem, path, None, f"load-error:{type(exc).__name__}:{exc}")]

    # A single workflow/blueprint document is never exploded via a sibling
    # "workflows" status array.
    if looks_like_blueprint(doc):
        return [(str(doc.get("id") or path.stem), path, doc, None)]

    members: list[Any] = []
    if isinstance(doc, list):
        members = doc
    elif isinstance(doc, dict):
        for key in ("blueprints", "entries", "items", "workflows", "library"):
            val = doc.get(key)
            if isinstance(val, list) and val:
                members = val
                break
        if not members:
            return [
                (
                    str(doc.get("id") or path.stem),
                    path,
                    None,
                    "load-error:library-file-has-no-blueprint-members",
                )
            ]
    else:
        return [(path.stem, path, None, "load-error:library-file-not-object-or-array")]

    out: list[tuple[str, Path, dict | None, str | None]] = []
    for i, item in enumerate(members):
        if not isinstance(item, dict):
            out.append((f"{path.stem}[{i}]", path, None, "load-error:member-not-object"))
            continue
        if item.get("kind") in {"workflow_catalog", "council_catalog", "council_preset"}:
            continue
        if not looks_like_blueprint(item):
            continue
        bid = str(item.get("id") or item.get("name") or f"{path.stem}[{i}]")
        out.append((bid, path, item, None))
    if not out:
        return [
            (
                str(doc.get("id") if isinstance(doc, dict) else path.stem),
                path,
                None,
                "load-error:library-file-has-no-blueprint-members",
            )
        ]
    return out


def scan_live_roots(repo: Path) -> list[dict[str, Any]]:
    roots: list[dict[str, Any]] = []
    for rel in LIVE_LIBRARY_FILES:
        p = repo / rel
        roots.append({"path": rel, "exists": p.is_file(), "kind": "file"})
    for rel in LIVE_LIBRARY_DIRS:
        p = repo / rel
        roots.append({"path": rel, "exists": p.is_dir(), "kind": "directory"})
    return roots


def enumerate_live_paths(repo: Path) -> list[tuple[str, Path]]:
    """Filesystem members of the live blueprint library. Not a catalog list."""
    found: list[tuple[str, Path]] = []
    seen: set[str] = set()

    def add(rel: str, path: Path) -> None:
        key = rel.replace("\\", "/")
        if key in seen:
            return
        seen.add(key)
        found.append((key, path))

    for rel in LIVE_LIBRARY_FILES:
        p = repo / rel
        if p.is_file():
            add(rel, p)
    for rel in LIVE_LIBRARY_DIRS:
        d = repo / rel
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.json")):
            if p.name.startswith("_"):
                continue
            if not is_enumerable_library_path(p):
                continue
            add(p.relative_to(repo).as_posix(), p)
    found.sort(key=lambda t: t[0])
    return found


def enumerate_fixture_paths() -> list[tuple[str, Path]]:
    rows: list[tuple[str, Path]] = []
    if not FIXTURE_LIB.is_dir():
        return rows
    for p in sorted(FIXTURE_LIB.glob("*.json")):
        rel = p.relative_to(REPO).as_posix()
        rows.append((rel, p))
    return rows


def is_placeholder(doc: dict) -> bool:
    for key in PLACEHOLDER_KEYS:
        if doc.get(key) is True:
            return True
    status = str(doc.get("status") or "").lower()
    if "placeholder" in status or status.startswith("discovery"):
        return True
    return False


def declared_outputs(doc: dict) -> list[str]:
    outs: list[str] = []
    for stage in doc.get("stages") or []:
        if not isinstance(stage, dict):
            continue
        for item in stage.get("outputs") or []:
            if isinstance(item, str) and item.strip():
                outs.append(item.strip())
    for item in doc.get("outputs") or []:
        if isinstance(item, str) and item.strip():
            outs.append(item.strip())
    # unique, stable
    seen: set[str] = set()
    uniq: list[str] = []
    for o in outs:
        if o not in seen:
            seen.add(o)
            uniq.append(o)
    return uniq


def _run_python_stage(script: Path, work: Path, timeout: int = 30) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["CNF0077_OUT"] = str(work)
    env["CNF0077_REPO"] = str(REPO)
    copied = work / script.name
    if script.resolve() != copied.resolve():
        shutil.copy2(script, copied)
    try:
        proc = subprocess.run(
            ["python3", "-B", str(copied)],
            cwd=str(work),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except OSError as exc:
        return 127, f"{type(exc).__name__}:{exc}"
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text[-2000:]


def smoke_doc(
    *,
    bid: str,
    rel: str,
    doc: dict,
    source_path: Path,
    clean_root: Path,
) -> dict[str, Any]:
    invocation_base = (
        f"clean-temp python3 -B smoke id={bid} src={rel}"
    )
    if is_placeholder(doc):
        return row(
            bid=bid,
            path=rel,
            invocation="NOT-INVOKED:placeholder-blueprint",
            exit_code=0,
            classification="placeholder-blueprint",
            error="placeholder-blueprint: discovery_only/placeholder flag; not executable",
        )
    stages = doc.get("stages")
    if not isinstance(stages, list) or not stages:
        return row(
            bid=bid,
            path=rel,
            invocation="LOAD",
            exit_code=2,
            classification="load-error",
            error="load-error:missing-or-empty-stages",
        )
    outputs = declared_outputs(doc)
    work = Path(clean_root) / hashlib.sha256(rel.encode()).hexdigest()[:16]
    work.mkdir(parents=True, exist_ok=True)
    last_code = 0
    last_tail = ""
    ran_any = False
    for stage in stages:
        if not isinstance(stage, dict):
            return row(
                bid=bid,
                path=rel,
                invocation=invocation_base,
                exit_code=2,
                classification="load-error",
                error="load-error:stage-not-object",
            )
        kind = str(stage.get("kind") or "")
        script_rel = stage.get("script")
        if kind == "python" and isinstance(script_rel, str) and script_rel:
            script = (source_path.parent / script_rel).resolve()
            if not script.is_file():
                return row(
                    bid=bid,
                    path=rel,
                    invocation=invocation_base,
                    exit_code=2,
                    classification="load-error",
                    error=f"load-error:script-missing:{script_rel}",
                )
            ran_any = True
            last_code, last_tail = _run_python_stage(script, work)
            if last_code != 0:
                err = f"stage-exit:{last_code}"
                if last_tail:
                    err += f":{last_tail[:400]}"
                return row(
                    bid=bid,
                    path=rel,
                    invocation=invocation_base + f" script={script_rel}",
                    exit_code=last_code,
                    classification="failure",
                    error=err,
                )
        elif kind in UNSUPPORTED_STAGE_KINDS:
            return row(
                bid=bid,
                path=rel,
                invocation=invocation_base,
                exit_code=1,
                classification="failure",
                error=f"unsupported-stage-kind:{kind}:no-runner-for-this-kind",
            )
        else:
            return row(
                bid=bid,
                path=rel,
                invocation=invocation_base,
                exit_code=2,
                classification="load-error",
                error=f"load-error:unrecognized-stage-kind:{kind or '<empty>'}",
            )
    if not ran_any:
        return row(
            bid=bid,
            path=rel,
            invocation=invocation_base,
            exit_code=2,
            classification="load-error",
            error="load-error:no-runnable-stage",
        )
    produced: list[str] = []
    for name in outputs:
        dest = work / name
        if dest.is_file() and dest.stat().st_size > 0:
            produced.append(name)
    if not outputs:
        # A run that declares no output cannot be counted executable.
        return row(
            bid=bid,
            path=rel,
            invocation=invocation_base,
            exit_code=last_code,
            classification="failure",
            error="loaded-but-no-declared-artifact",
        )
    if not produced:
        return row(
            bid=bid,
            path=rel,
            invocation=invocation_base,
            exit_code=last_code,
            classification="failure",
            error="loaded-but-no-artifact",
        )
    return row(
        bid=bid,
        path=rel,
        invocation=invocation_base,
        exit_code=last_code,
        classification="executable",
        artifact_path=produced[0],
    )


def smoke_path(rel: str, path: Path, clean_root: Path) -> list[dict[str, Any]]:
    expanded = expand_library_file(path, rel)
    rows: list[dict[str, Any]] = []
    for bid, src, doc, err in expanded:
        if err or doc is None:
            rows.append(
                row(
                    bid=bid,
                    path=rel,
                    invocation="LOAD",
                    exit_code=2,
                    classification="load-error",
                    error=err or "load-error:unparsed",
                )
            )
            continue
        rows.append(
            smoke_doc(
                bid=bid,
                rel=rel if src == path else f"{rel}#{bid}",
                doc=doc,
                source_path=src,
                clean_root=clean_root,
            )
        )
    return rows


def sweep_paths(pairs: list[tuple[str, Path]], *, prefix: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=prefix) as tmp:
        clean = Path(tmp)
        rows: list[dict[str, Any]] = []
        for rel, path in pairs:
            rows.extend(smoke_path(rel, path, clean))
        measured = sum(1 for r in rows if r["classification"] == "executable")
        fingerprint = sha256_bytes(
            json.dumps(rows, sort_keys=True, ensure_ascii=True).encode("utf-8")
        )
        return {
            "blueprints": rows,
            "measured_executable_count": measured,
            "pre_claim_fingerprint": fingerprint,
            "clean_env": f"tempfile.TemporaryDirectory(prefix={prefix!r})",
        }


def sweep_live(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or REPO
    pairs = enumerate_live_paths(repo)
    result = sweep_paths(pairs, prefix="cnf0077-live-")
    result["scanned_roots"] = scan_live_roots(repo)
    result["enumerated_from"] = "filesystem"
    result["member_paths"] = [rel for rel, _ in pairs]
    return result


def sweep_fixtures() -> dict[str, Any]:
    pairs = enumerate_fixture_paths()
    result = sweep_paths(pairs, prefix="cnf0077-fx-")
    result["enumerated_from"] = "filesystem"
    result["member_paths"] = [rel for rel, _ in pairs]
    return result


def read_catalog_claim(repo: Path | None = None) -> dict[str, Any]:
    """Read the catalog CLAIM only. Never used as the blueprint member list."""
    repo = repo or REPO
    catalog_path = repo / "command-center" / "WORK-UNIT-CATALOG.json"
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    units = data.get("work_units") or []
    items = data.get("items") or []
    # R-A08 lives in items[] (register), not work_units[]. The claim number
    # is read AFTER the filesystem sweep and is never used as a member list.
    ra08 = next((u for u in items if isinstance(u, dict) and u.get("id") == "R-A08"), None)
    cnf = next((u for u in units if isinstance(u, dict) and u.get("id") == "CNF-0077"), None)
    if not isinstance(ra08, dict) or not isinstance(cnf, dict):
        raise RuntimeError("catalog missing R-A08 (items) or CNF-0077 (work_units)")
    evidence = str(ra08.get("evidence") or "")
    claim_m = re.search(r"\u2192\s*(\d+)\s+blueprints", evidence)
    if claim_m is None:
        claim_m = re.search(r"->\s*(\d+)\s+blueprints", evidence)
    if claim_m is None:
        raise RuntimeError("R-A08 evidence has no blueprint count")
    target = str(ra08.get("target") or "")
    floor_m = re.search(r"(?:≥|>=)\s*(\d+)", target)
    if floor_m is None:
        raise RuntimeError("R-A08 target has no floor")
    return {
        "catalog_claim": int(claim_m.group(1)),
        "declared_floor": int(floor_m.group(1)),
        "claim_source": "command-center/WORK-UNIT-CATALOG.json#R-A08.evidence",
        "floor_source": "command-center/WORK-UNIT-CATALOG.json#R-A08.target",
        "completion_sentinel": str(cnf.get("completion_sentinel") or ""),
        "question": str(cnf.get("question_or_target") or ""),
        "title": str(cnf.get("title") or ""),
    }


def load_fixture_catalog_claim() -> dict[str, Any]:
    return json.loads(CATALOG_CLAIM_FILE.read_text(encoding="utf-8"))


def detector_controls() -> dict[str, Any]:
    """Known-broken fixture library. Reviewer job is to re-run this."""
    fx = sweep_fixtures()
    rows = fx["blueprints"]
    by_id = {r["id"]: r for r in rows}
    want_ids = {
        "bp.ok.write-artifact",
        "bp.ok.catalog-omitted",
        "bp.fail.no-artifact",
        "bp.placeholder.discovery-only",
        "bp.load-error.missing-stages",
    }
    missing = sorted(want_ids - set(by_id))
    extra_ok = by_id.get("bp.ok.write-artifact", {})
    omitted = by_id.get("bp.ok.catalog-omitted", {})
    no_art = by_id.get("bp.fail.no-artifact", {})
    placeholder = by_id.get("bp.placeholder.discovery-only", {})
    load_err = by_id.get("bp.load-error.missing-stages", {})

    catalog = load_fixture_catalog_claim()
    catalog_names = [str(x) for x in catalog.get("blueprints") or []]
    fs_names = [Path(p).name for p in fx["member_paths"]]

    no_art_not_exec = no_art.get("classification") == "failure" and "no-artifact" in str(
        no_art.get("error") or ""
    )
    placeholder_ok = placeholder.get("classification") == "placeholder-blueprint"
    load_ok = load_err.get("classification") == "load-error"
    exec_ok = extra_ok.get("classification") == "executable" and extra_ok.get("artifact_path")
    omitted_ok = omitted.get("classification") == "executable"
    omitted_on_disk = "bp.ok.catalog-omitted.json" in fs_names
    omitted_not_in_catalog = "bp.ok.catalog-omitted.json" not in catalog_names
    missing_listed = "bp.missing-not-on-disk.json" in catalog_names
    missing_not_on_fs = "bp.missing-not-on-disk.json" not in fs_names

    measured = fx["measured_executable_count"]
    # Catalog claims 4 executable names including a missing file and a no-artifact.
    # Filesystem truth: exactly the two write-artifact blueprints.
    catalog_claimed_exec = int(catalog.get("claimed_executable_count") or 0)

    good_count_first = measured == 2
    mutant_would_pass = (
        sum(
            1
            for r in rows
            if r["classification"] in {"executable", "failure", "placeholder-blueprint"}
        )
        == 2
    )
    # The mutant that counts no-artifact as executable must NOT match measured==2
    mutant_count = sum(
        1
        for r in rows
        if r["classification"] in {"executable", "failure"}
        and r["id"] in {"bp.ok.write-artifact", "bp.ok.catalog-omitted", "bp.fail.no-artifact"}
    )

    fired_no_artifact = no_art_not_exec and mutant_count != measured
    fired_fs_vs_catalog = omitted_on_disk and omitted_not_in_catalog and missing_listed and missing_not_on_fs
    silent_on_good = bool(exec_ok) and bool(omitted_ok) and good_count_first

    pass_all = (
        not missing
        and no_art_not_exec
        and placeholder_ok
        and load_ok
        and bool(exec_ok)
        and bool(omitted_ok)
        and fired_fs_vs_catalog
        and silent_on_good
        and fired_no_artifact
        and measured == 2
        and catalog_claimed_exec > measured
    )
    return {
        "pass": pass_all,
        "missing_ids": missing,
        "fixture_measured_executable_count": measured,
        "fixture_catalog_claim": catalog_claimed_exec,
        "rows": rows,
        "member_paths": fx["member_paths"],
        "pre_claim_fingerprint": fx["pre_claim_fingerprint"],
        "no_artifact_classified_failure": no_art_not_exec,
        "placeholder_classified": placeholder_ok,
        "load_error_classified": load_ok,
        "good_executable": bool(exec_ok),
        "catalog_omitted_still_enumerated": bool(omitted_ok) and omitted_on_disk,
        "missing_catalog_file_not_invented": missing_not_on_fs and missing_listed,
        "mutant_no_artifact_as_executable_count": mutant_count,
        "fired_on_bad_state": fired_no_artifact and fired_fs_vs_catalog,
        "silent_on_good_state": silent_on_good,
    }


def every_row_complete(rows: list[dict[str, Any]]) -> bool:
    for r in rows:
        if "exit_code" not in r:
            return False
        if not r.get("artifact_path") and not r.get("error"):
            return False
    return True
