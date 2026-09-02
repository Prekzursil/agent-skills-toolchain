"""Filesystem enumeration, IR load, smoke, e2e, flag cross-check for WFA-0124.

Live members come ONLY from paths that exist on disk. The catalog claim is
read afterwards and is never the member list. A NATIVE self-declaration that
fails IR load is a contradiction, not averaged into the executable count.
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

import ir_load as IR
import remaining_work as RW

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE_LIB = HERE / "fixtures" / "library"
CATALOG_CLAIM_FILE = HERE / "fixtures" / "catalog_claim.json"

LIVE_LIBRARY_FILES = (
    "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/sources/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/wfa/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
)
LIVE_LIBRARY_DIRS = (
    "platform/workflows",
    "workflows",
)

WFA_0044 = "command-center/wfa/WFA-0044-workflow-ir-spec.json"
SCHEMA_PACK = "command-center/wfa/schema/wfa-schema-pack.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def looks_like_blueprint(doc: Any) -> bool:
    if not isinstance(doc, dict):
        return False
    kind = str(doc.get("kind") or doc.get("artifact_class") or "")
    if kind in {"workflow_blueprint", "blueprint"}:
        return True
    if "stages" in doc and ("id" in doc or "name" in doc):
        return True
    return False


def expand_library_file(
    path: Path, rel: str
) -> list[tuple[str, Path, dict | None, str | None]]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [(path.stem, path, None, f"load-error:{type(exc).__name__}:{exc}")]

    members: list[Any] = []
    if isinstance(doc, list):
        members = doc
    elif isinstance(doc, dict):
        for key in ("blueprints", "entries", "items", "workflows", "library"):
            val = doc.get(key)
            if isinstance(val, list) and val:
                members = val
                break
        if not members and looks_like_blueprint(doc):
            return [(str(doc.get("id") or path.stem), path, doc, None)]
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
        if not looks_like_blueprint(item) and item.get("kind") not in {None, ""}:
            continue
        bid = str(item.get("id") or item.get("name") or f"{path.stem}[{i}]")
        out.append((bid, path, item, None))
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
            add(p.relative_to(repo).as_posix(), p)
    found.sort(key=lambda t: t[0])
    return found


def enumerate_fixture_paths() -> list[tuple[str, Path]]:
    rows: list[tuple[str, Path]] = []
    if not FIXTURE_LIB.is_dir():
        return rows
    for p in sorted(FIXTURE_LIB.glob("*.json")):
        rows.append((p.relative_to(REPO).as_posix(), p))
    return rows


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
    seen: set[str] = set()
    uniq: list[str] = []
    for o in outs:
        if o not in seen:
            seen.add(o)
            uniq.append(o)
    return uniq


def _run_python(script: Path, work: Path, timeout: int = 30) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["WFA0124_OUT"] = str(work)
    env["WFA0124_REPO"] = str(REPO)
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


def smoke_after_ir(
    *,
    bid: str,
    rel: str,
    doc: dict,
    source_path: Path,
    work: Path,
) -> dict[str, Any]:
    invocation = f"clean-temp python3 -B smoke id={bid} src={rel}"
    stages = doc.get("stages")
    if not isinstance(stages, list) or not stages:
        return {
            "ok": False,
            "exit_code": 2,
            "invocation": "SMOKE",
            "artifact_path": None,
            "error": "smoke-not-run:missing-or-empty-stages",
        }
    outputs = declared_outputs(doc)
    last_code = 0
    last_tail = ""
    ran_any = False
    for stage in stages:
        if not isinstance(stage, dict):
            return {
                "ok": False,
                "exit_code": 2,
                "invocation": invocation,
                "artifact_path": None,
                "error": "smoke-not-run:stage-not-object",
            }
        kind = str(stage.get("kind") or "")
        script_rel = stage.get("script")
        if kind == "python" and isinstance(script_rel, str) and script_rel:
            script = (source_path.parent / script_rel).resolve()
            if not script.is_file():
                return {
                    "ok": False,
                    "exit_code": 2,
                    "invocation": invocation,
                    "artifact_path": None,
                    "error": f"smoke-not-run:script-missing:{script_rel}",
                }
            ran_any = True
            last_code, last_tail = _run_python(script, work)
            if last_code != 0:
                err = f"stage-exit:{last_code}"
                if last_tail:
                    err += f":{last_tail[:400]}"
                return {
                    "ok": False,
                    "exit_code": last_code,
                    "invocation": invocation + f" script={script_rel}",
                    "artifact_path": None,
                    "error": err,
                }
        elif kind in {"static-scan", "write-config", "agent", "llm", "discovery"}:
            return {
                "ok": False,
                "exit_code": 1,
                "invocation": invocation,
                "artifact_path": None,
                "error": f"unsupported-stage-kind:{kind}:no-runner-for-this-kind",
            }
        else:
            return {
                "ok": False,
                "exit_code": 2,
                "invocation": invocation,
                "artifact_path": None,
                "error": f"smoke-not-run:unrecognized-stage-kind:{kind or '<empty>'}",
            }
    if not ran_any:
        return {
            "ok": False,
            "exit_code": 2,
            "invocation": invocation,
            "artifact_path": None,
            "error": "smoke-not-run:no-runnable-stage",
        }
    produced: list[str] = []
    for name in outputs:
        dest = work / name
        if dest.is_file() and dest.stat().st_size > 0:
            produced.append(name)
    if not outputs:
        return {
            "ok": False,
            "exit_code": last_code,
            "invocation": invocation,
            "artifact_path": None,
            "error": "loaded-but-no-declared-artifact",
        }
    if not produced:
        return {
            "ok": False,
            "exit_code": last_code,
            "invocation": invocation,
            "artifact_path": None,
            "error": "loaded-but-no-artifact",
        }
    return {
        "ok": True,
        "exit_code": last_code,
        "invocation": invocation,
        "artifact_path": produced[0],
        "error": None,
    }


def run_e2e(
    *,
    bid: str,
    doc: dict,
    source_path: Path,
    work: Path,
) -> dict[str, Any]:
    e2e = doc.get("e2e")
    if not isinstance(e2e, dict) or not e2e:
        return {
            "attempted": False,
            "ok": False,
            "path": None,
            "run_id": None,
            "error": "no-e2e-block",
        }
    script_rel = e2e.get("path") or e2e.get("script")
    if not isinstance(script_rel, str) or not script_rel.strip():
        return {
            "attempted": False,
            "ok": False,
            "path": None,
            "run_id": None,
            "error": "e2e-path-missing",
        }
    script = (source_path.parent / script_rel).resolve()
    rel = script_rel
    if not script.is_file():
        return {
            "attempted": True,
            "ok": False,
            "path": rel,
            "run_id": None,
            "error": f"e2e-script-missing:{rel}",
        }
    code, tail = _run_python(script, work)
    run_id = f"e2e-{bid}-{sha256_bytes(script.read_bytes())[:12]}"
    if code != 0:
        return {
            "attempted": True,
            "ok": False,
            "path": rel,
            "run_id": run_id,
            "error": f"e2e-exit:{code}:{tail[:300]}",
        }
    expected = str(e2e.get("expected_artifact") or "result.json")
    dest = work / expected
    if not dest.is_file() or dest.stat().st_size <= 0:
        return {
            "attempted": True,
            "ok": False,
            "path": rel,
            "run_id": run_id,
            "error": f"e2e-postcondition-missing-artifact:{expected}",
        }
    try:
        json.loads(dest.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "attempted": True,
            "ok": False,
            "path": rel,
            "run_id": run_id,
            "error": f"e2e-postcondition-unparseable:{type(exc).__name__}",
        }
    return {
        "attempted": True,
        "ok": True,
        "path": rel,
        "run_id": run_id,
        "error": None,
    }


def contradiction_of(
    *,
    bid: str,
    doc: dict,
    ir_ok: bool,
    executable: bool,
    flagship_ok: bool,
) -> dict[str, str] | None:
    disc = IR.declared_discovery_only(doc)
    native = IR.declares_native(doc)
    claimed_fs = IR.declares_flagship(doc)
    if native and not ir_ok:
        return {
            "blueprint_id": bid,
            "kind": "declared-native-but-ir-load-failed",
            "declared": f"state={IR.declared_state(doc)!r} tier={IR.declared_quality_tier(doc)!r} discovery_only={disc}",
            "measured": "ir_load.ok=false",
        }
    if native and ir_ok and not executable:
        return {
            "blueprint_id": bid,
            "kind": "declared-native-but-not-executable",
            "declared": f"state={IR.declared_state(doc)!r} tier={IR.declared_quality_tier(doc)!r}",
            "measured": "classification!=executable",
        }
    if disc and executable:
        return {
            "blueprint_id": bid,
            "kind": "declared-discovery-but-executable",
            "declared": "discovery_only=true",
            "measured": "classification=executable",
        }
    if claimed_fs and not flagship_ok:
        return {
            "blueprint_id": bid,
            "kind": "declared-flagship-but-no-e2e",
            "declared": f"quality_tier={IR.declared_quality_tier(doc)!r} flagship={doc.get('flagship')!r}",
            "measured": "flagship_identified=false",
        }
    return None


def classify(*, ir_ok: bool, smoke_ok: bool) -> str:
    if not ir_ok:
        return "load-error"
    if not smoke_ok:
        return "failure"
    return "executable"


def measure_doc(
    *,
    bid: str,
    rel: str,
    doc: dict,
    source_path: Path,
    clean_root: Path,
) -> dict[str, Any]:
    ir = IR.load_ir(doc, rel=rel, bid=bid)
    work = Path(clean_root) / hashlib.sha256(f"{rel}#{bid}".encode()).hexdigest()[:16]
    work.mkdir(parents=True, exist_ok=True)
    smoke = smoke_after_ir(
        bid=bid, rel=rel, doc=doc, source_path=source_path, work=work
    )
    e2e = run_e2e(bid=bid, doc=doc, source_path=source_path, work=work)
    ir_ok = bool(ir["ok"])
    smoke_ok = bool(smoke["ok"])
    executable = ir_ok and smoke_ok
    flagship_ok = executable and bool(e2e["ok"]) and bool(e2e.get("run_id"))
    cls = classify(ir_ok=ir_ok, smoke_ok=smoke_ok)
    contra = contradiction_of(
        bid=bid,
        doc=doc,
        ir_ok=ir_ok,
        executable=executable,
        flagship_ok=flagship_ok,
    )
    remaining = RW.remaining_for_row(
        bid=bid,
        executable=executable,
        ir_ok=ir_ok,
        smoke_ok=smoke_ok,
        flagship_ok=flagship_ok,
        claimed_flagship=IR.declares_flagship(doc),
        discovery_only=IR.declared_discovery_only(doc),
    )
    row: dict[str, Any] = {
        "id": bid,
        "path": rel,
        "declared_discovery_only": IR.declared_discovery_only(doc),
        "declared_state": IR.declared_state(doc),
        "declared_quality_tier": IR.declared_quality_tier(doc),
        "ir_load": {
            "ok": ir_ok,
            "error": ir.get("error"),
            "source_anchor_injected": ir.get("source_anchor_injected"),
            "stage_count": len((ir.get("ir") or {}).get("stages") or []) if ir_ok else 0,
        },
        "smoke": {
            "ok": smoke_ok,
            "exit_code": smoke.get("exit_code"),
            "invocation": smoke.get("invocation"),
            "artifact_path": smoke.get("artifact_path"),
            "error": smoke.get("error"),
        },
        "e2e": {
            "attempted": e2e.get("attempted"),
            "ok": e2e.get("ok"),
            "path": e2e.get("path"),
            "run_id": e2e.get("run_id"),
            "error": e2e.get("error"),
        },
        "classification": cls,
        "exit_code": int(smoke.get("exit_code") if smoke.get("exit_code") is not None else (0 if ir_ok else 2)),
        "flagship_identified": flagship_ok,
        "remaining_work": remaining,
    }
    if smoke.get("artifact_path"):
        row["artifact_path"] = smoke["artifact_path"]
    err = smoke.get("error") if not smoke_ok else (ir.get("error") if not ir_ok else None)
    if not smoke_ok and not ir_ok:
        err = ir.get("error")
    if contra:
        row["contradiction"] = contra["kind"]
        err = err or contra["kind"]
    if err:
        row["error"] = err
    elif not row.get("artifact_path"):
        row["error"] = "no-artifact-non-executable"
    return row


def cells_for_row(row: dict[str, Any]) -> list[dict[str, Any]]:
    bid = row["id"]
    ir_ok = bool((row.get("ir_load") or {}).get("ok"))
    smoke_ok = bool((row.get("smoke") or {}).get("ok"))
    flagship = bool(row.get("flagship_identified"))
    disc = bool(row.get("declared_discovery_only"))
    return [
        {
            "blueprint_id": bid,
            "tier": "discovery_record",
            "status": "EVIDENCED" if disc else "EMPTY",
            "detail": f"discovery_only={disc}",
        },
        {
            "blueprint_id": bid,
            "tier": "ir_load",
            "status": "EVIDENCED" if ir_ok else "FAIL",
            "detail": str((row.get("ir_load") or {}).get("error") or "ir_load.ok"),
        },
        {
            "blueprint_id": bid,
            "tier": "smoke",
            "status": "EVIDENCED" if smoke_ok else "FAIL",
            "detail": str((row.get("smoke") or {}).get("error") or row.get("artifact_path") or "smoke"),
        },
        {
            "blueprint_id": bid,
            "tier": "flagship_e2e",
            "status": "EVIDENCED" if flagship else ("EMPTY" if not (row.get("e2e") or {}).get("attempted") else "FAIL"),
            "detail": str((row.get("e2e") or {}).get("run_id") or (row.get("e2e") or {}).get("error") or "no-e2e"),
        },
    ]


def measure_paths(pairs: list[tuple[str, Path]], *, prefix: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=prefix) as tmp:
        clean = Path(tmp)
        rows: list[dict[str, Any]] = []
        for rel, path in pairs:
            expanded = expand_library_file(path, rel)
            for bid, src, doc, err in expanded:
                if err or doc is None:
                    row = {
                        "id": bid,
                        "path": rel,
                        "declared_discovery_only": False,
                        "declared_state": "",
                        "declared_quality_tier": "",
                        "ir_load": {
                            "ok": False,
                            "error": err or "load-error:unparsed",
                            "source_anchor_injected": False,
                            "stage_count": 0,
                        },
                        "smoke": {
                            "ok": False,
                            "exit_code": 2,
                            "invocation": "LOAD",
                            "artifact_path": None,
                            "error": "smoke-not-run:unparsed",
                        },
                        "e2e": {
                            "attempted": False,
                            "ok": False,
                            "path": None,
                            "run_id": None,
                            "error": "no-e2e-block",
                        },
                        "classification": "load-error",
                        "exit_code": 2,
                        "error": err or "load-error:unparsed",
                        "flagship_identified": False,
                        "remaining_work": RW.remaining_for_row(
                            bid=bid,
                            executable=False,
                            ir_ok=False,
                            smoke_ok=False,
                            flagship_ok=False,
                            claimed_flagship=False,
                            discovery_only=False,
                        ),
                    }
                    rows.append(row)
                    continue
                use_rel = rel if src == path else f"{rel}#{bid}"
                rows.append(
                    measure_doc(
                        bid=bid,
                        rel=use_rel,
                        doc=doc,
                        source_path=src,
                        clean_root=clean,
                    )
                )
        measured = sum(1 for r in rows if r["classification"] == "executable")
        flagship_ids = [r["id"] for r in rows if r.get("flagship_identified")]
        contradictions: list[dict[str, str]] = []
        for r in rows:
            kind = r.get("contradiction")
            if not kind:
                continue
            contradictions.append(
                {
                    "blueprint_id": r["id"],
                    "kind": str(kind),
                    "declared": (
                        f"state={r.get('declared_state')!r} "
                        f"tier={r.get('declared_quality_tier')!r} "
                        f"discovery_only={r.get('declared_discovery_only')}"
                    ),
                    "measured": (
                        f"class={r.get('classification')} "
                        f"ir={(r.get('ir_load') or {}).get('ok')} "
                        f"flagship={r.get('flagship_identified')}"
                    ),
                }
            )
        cells: list[dict[str, Any]] = []
        for r in rows:
            cells.extend(cells_for_row(r))
        fingerprint = sha256_bytes(
            json.dumps(
                {"rows": rows, "measured": measured, "flagship": flagship_ids},
                sort_keys=True,
                ensure_ascii=True,
            ).encode("utf-8")
        )
        ir_ok_n = sum(1 for r in rows if (r.get("ir_load") or {}).get("ok"))
        smoke_ok_n = sum(1 for r in rows if (r.get("smoke") or {}).get("ok"))
        return {
            "rows": rows,
            "cells": cells,
            "measured_executable_count": measured,
            "flagship_identified": flagship_ids,
            "contradictions": contradictions,
            "pre_claim_fingerprint": fingerprint,
            "clean_env": f"tempfile.TemporaryDirectory(prefix={prefix!r})",
            "totals": {
                "live_blueprint_rows": len(rows),
                "ir_load_ok": ir_ok_n,
                "smoke_ok": smoke_ok_n,
                "measured_executable": measured,
                "flagship_identified": len(flagship_ids),
                "contradictions": len(contradictions),
                "honest_null_library_absent": len(rows) == 0,
            },
        }


def sweep_live(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or REPO
    pairs = enumerate_live_paths(repo)
    result = measure_paths(pairs, prefix="wfa0124-live-")
    result["scanned_roots"] = scan_live_roots(repo)
    result["enumerated_from"] = "filesystem"
    result["member_paths"] = [rel for rel, _ in pairs]
    result["library_present"] = any(
        (repo / rel).is_file() for rel in LIVE_LIBRARY_FILES
    ) or any((repo / d).is_dir() and any((repo / d).rglob("*.json")) for d in LIVE_LIBRARY_DIRS)
    return result


def sweep_fixtures() -> dict[str, Any]:
    pairs = enumerate_fixture_paths()
    result = measure_paths(pairs, prefix="wfa0124-fx-")
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
    ra08 = next((u for u in items if isinstance(u, dict) and u.get("id") == "R-A08"), None)
    wfa = next((u for u in units if isinstance(u, dict) and u.get("id") == "WFA-0124"), None)
    if not isinstance(ra08, dict) or not isinstance(wfa, dict):
        raise RuntimeError("catalog missing R-A08 (items) or WFA-0124 (work_units)")
    evidence = str(ra08.get("evidence") or "")
    claim_m = re.search(r"\u2192\s*(\d+)\s+blueprints", evidence)
    if claim_m is None:
        claim_m = re.search(r"->\s*(\d+)\s+blueprints", evidence)
    if claim_m is None:
        raise RuntimeError("R-A08 evidence has no blueprint count")
    target = str(ra08.get("target") or "")
    floor_m = re.search(r"(?:≥|>=)\s*(\d+)", target)
    flag_m = re.search(r"(?:≥|>=)\s*(\d+)\s*flagship", target, re.IGNORECASE)
    inp = " ".join(str(x) for x in (wfa.get("inputs") or []))
    inp_claim = re.search(r"(\d+)\s+blueprints", inp)
    catalog_claim = int(claim_m.group(1))
    if inp_claim is not None and int(inp_claim.group(1)) != catalog_claim:
        raise RuntimeError(
            f"catalog claim disagree R-A08={catalog_claim} WFA-0124-input={inp_claim.group(1)}"
        )
    small = re.search(r"BUILD-SMALL n=(\d+)", inp)
    return {
        "catalog_claim": catalog_claim,
        "declared_executable_floor": int(floor_m.group(1) if floor_m else 96),
        "flagship_required": int(flag_m.group(1) if flag_m else 40),
        "claim_source": "command-center/WORK-UNIT-CATALOG.json#R-A08.evidence",
        "floor_source": "command-center/WORK-UNIT-CATALOG.json#R-A08.target",
        "completion_sentinel": str(wfa.get("completion_sentinel") or ""),
        "question": str(wfa.get("question_or_target") or ""),
        "title": str(wfa.get("title") or ""),
        "catalog_declared_size_components": {
            "BUILD-SMALL": int(small.group(1)) if small else None,
            "note": "catalog-declared, not measured on this filesystem",
        },
    }


def load_fixture_catalog_claim() -> dict[str, Any]:
    return json.loads(CATALOG_CLAIM_FILE.read_text(encoding="utf-8"))


def every_row_complete(rows: list[dict[str, Any]]) -> bool:
    for r in rows:
        if "exit_code" not in r:
            return False
        if not r.get("artifact_path") and not r.get("error"):
            return False
        if "classification" not in r:
            return False
        if "ir_load" not in r or "smoke" not in r:
            return False
        rw = r.get("remaining_work")
        if r.get("classification") != "executable":
            if not isinstance(rw, list) or not rw:
                return False
            ok, _ = RW.all_concrete(rw)
            if not ok:
                return False
    return True


def detector_controls() -> dict[str, Any]:
    fx = sweep_fixtures()
    rows = fx["rows"]
    by_id = {r["id"]: r for r in rows}
    want = {
        "bp.ok.smoke",
        "bp.ok.flagship",
        "bp.discovery-only",
        "bp.contradiction.native-unloadable",
        "bp.flagship-claimed-no-e2e",
        "bp.fail.no-artifact",
        "bp.load-error.missing-stages",
    }
    missing = sorted(want - set(by_id))
    native = by_id.get("bp.contradiction.native-unloadable") or {}
    discovery = by_id.get("bp.discovery-only") or {}
    claimed_fs = by_id.get("bp.flagship-claimed-no-e2e") or {}
    real_fs = by_id.get("bp.ok.flagship") or {}
    smoke_ok = by_id.get("bp.ok.smoke") or {}
    no_art = by_id.get("bp.fail.no-artifact") or {}
    load_err = by_id.get("bp.load-error.missing-stages") or {}

    measured = fx["measured_executable_count"]
    flagship_ids = list(fx["flagship_identified"])
    contra_ids = {c["blueprint_id"]: c["kind"] for c in fx["contradictions"]}

    native_contra = contra_ids.get("bp.contradiction.native-unloadable") == (
        "declared-native-but-ir-load-failed"
    )
    discovery_silent = "bp.discovery-only" not in contra_ids
    discovery_not_exec = discovery.get("classification") != "executable"
    claimed_not_identified = "bp.flagship-claimed-no-e2e" not in flagship_ids
    claimed_contra = contra_ids.get("bp.flagship-claimed-no-e2e") == (
        "declared-flagship-but-no-e2e"
    )
    real_identified = "bp.ok.flagship" in flagship_ids and real_fs.get("classification") == "executable"
    smoke_exec = smoke_ok.get("classification") == "executable"
    no_art_fail = no_art.get("classification") == "failure"
    load_is_err = load_err.get("classification") == "load-error"
    remaining_ok, remaining_bad = RW.all_concrete(load_err.get("remaining_work") or [])
    mutant_vague_ok, _ = RW.all_concrete(RW.category_label_mutant("bp.load-error.missing-stages"))
    mutant_flagship_count = sum(
        1
        for r in rows
        if IR.declared_quality_tier({"quality_tier": r.get("declared_quality_tier")})
        in IR.FLAGSHIP_TIERS
        or r.get("declared_quality_tier") == "flagship"
    )
    # claimed flagship count from declared tier, not identification
    declared_flagship_n = sum(
        1 for r in rows if r.get("declared_quality_tier") == "flagship"
    )
    identified_n = len(flagship_ids)

    fired_native = native_contra and native.get("classification") == "load-error"
    fired_flagship = claimed_not_identified and claimed_contra and declared_flagship_n != identified_n
    fired_vague = remaining_ok and (not mutant_vague_ok)
    silent_good = bool(smoke_exec) and bool(real_identified) and discovery_silent and discovery_not_exec

    catalog = load_fixture_catalog_claim()
    catalog_claimed = int(catalog.get("claimed_executable_count") or 0)

    pass_all = (
        not missing
        and measured == 3
        and identified_n == 1
        and fired_native
        and fired_flagship
        and fired_vague
        and silent_good
        and no_art_fail
        and load_is_err
        and catalog_claimed != measured
        and remaining_ok
        and not remaining_bad
        and every_row_complete(rows)
    )
    return {
        "pass": pass_all,
        "missing_ids": missing,
        "fixture_measured_executable_count": measured,
        "fixture_catalog_claim": catalog_claimed,
        "fixture_flagship_identified": flagship_ids,
        "fixture_contradiction_ids": sorted(contra_ids),
        "rows": rows,
        "member_paths": fx["member_paths"],
        "pre_claim_fingerprint": fx["pre_claim_fingerprint"],
        "native_contradiction_fired": fired_native,
        "flagship_claimed_demoted": fired_flagship,
        "remaining_work_concrete": remaining_ok,
        "vague_mutant_rejected": fired_vague,
        "no_artifact_classified_failure": no_art_fail,
        "load_error_classified": load_is_err,
        "discovery_consistent": discovery_silent and discovery_not_exec,
        "mutant_declared_flagship_count": declared_flagship_n,
        "identified_flagship_count": identified_n,
        "fired_on_bad_state": fired_native and fired_flagship and fired_vague,
        "silent_on_good_state": silent_good,
        "totals": fx["totals"],
        "contradictions": fx["contradictions"],
    }
