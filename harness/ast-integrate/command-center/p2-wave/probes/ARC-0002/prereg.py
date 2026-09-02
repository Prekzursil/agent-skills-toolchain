#!/usr/bin/env python3
"""Pre-registration: hash match, +0.01 mutation fire, dossier mtime order."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from score import MUTATION_BPS, MUTATION_DELTA, public_dimensions

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
RUBRIC_REL = "command-center/phase3/RUBRIC.json"
MANIFEST_REL = "command-center/phase3/ARTIFACT-MANIFEST.json"
FIXTURE_REL = (
    "command-center/p2-wave/probes/ARC-0002/fixtures/post-freeze-dossier.json"
)
DUMPS_KW = {"indent": 2, "ensure_ascii": True}


def dumps(doc: Any) -> str:
    return json.dumps(doc, **DUMPS_KW) + "\n"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    canon = raw.replace(b"\r\n", b"\n")
    return sha256_bytes(raw), len(canon)


def parse_registered_at(stamp: str) -> datetime:
    if stamp.endswith("Z"):
        stamp = stamp[:-1] + "+00:00"
    dt = datetime.fromisoformat(stamp)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def mtime_utc(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def check_hash_match(rubric_path: Path, manifest_path: Path) -> dict[str, Any]:
    live_sha, live_bytes = sha256_file(rubric_path)
    man = load_json(manifest_path)
    rec = man.get("rubric") or {}
    rec_sha = str(rec.get("sha256") or "")
    rec_path = str(rec.get("path") or "").replace("\\", "/")
    ok = rec_sha == live_sha and rec_path == RUBRIC_REL
    return {
        "ok": ok,
        "live_sha256": live_sha,
        "live_bytes": live_bytes,
        "manifest_sha256": rec_sha,
        "manifest_path_field": rec_path,
        "registered_at": rec.get("registered_at"),
    }


def mutate_one_weight(doc: dict[str, Any]) -> dict[str, Any]:
    mutant = copy.deepcopy(doc)
    dims = mutant.get("dimensions") or []
    if not dims:
        raise ValueError("no dimensions to mutate")
    row = dims[0]
    old = Decimal(str(row.get("weight_decimal") or row.get("weight")))
    new = old + MUTATION_DELTA
    row["weight"] = float(new)
    row["weight_decimal"] = f"{new:.2f}"
    if "basis_points" in row:
        row["basis_points"] = int(row["basis_points"]) + MUTATION_BPS
    mutant["weights_sum"] = float(
        sum(Decimal(str(d.get("weight_decimal") or d.get("weight"))) for d in dims)
    )
    if "weight_basis_points_sum" in mutant:
        mutant["weight_basis_points_sum"] = sum(int(d["basis_points"]) for d in dims)
    return mutant


def mutation_fires(rubric_path: Path, manifest_path: Path) -> dict[str, Any]:
    live = load_json(rubric_path)
    mutant = mutate_one_weight(live)
    mutant_raw = dumps(mutant).encode("utf-8")
    mutant_sha = sha256_bytes(mutant_raw)
    live_sha, _ = sha256_file(rubric_path)
    man = load_json(manifest_path)
    rec_sha = str((man.get("rubric") or {}).get("sha256") or "")
    with tempfile.TemporaryDirectory(prefix="arc0002-mut-") as tmp:
        tmp_path = Path(tmp) / "RUBRIC.mutated.json"
        tmp_path.write_bytes(mutant_raw)
        tmp_sha, _ = sha256_file(tmp_path)
    fired = mutant_sha != rec_sha and tmp_sha != rec_sha and live_sha == rec_sha
    return {
        "ok": fired,
        "live_sha256": live_sha,
        "mutant_sha256": mutant_sha,
        "manifest_sha256": rec_sha,
        "mutated_dimension": (live.get("dimensions") or [{}])[0].get("id"),
        "delta": str(MUTATION_DELTA),
        "live_still_matches": live_sha == rec_sha,
        "mutant_mismatches": mutant_sha != rec_sha,
    }


def freeze_compliant_paths(man: dict[str, Any]) -> list[str]:
    rows = man.get("dossier_artifacts") or []
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("freeze_compliant") is True and row.get("path"):
            out.append(str(row["path"]).replace("\\", "/"))
    return out


def check_ordering(repo: Path, manifest_path: Path) -> dict[str, Any]:
    man = load_json(manifest_path)
    rec = man.get("rubric") or {}
    stamp = rec.get("registered_at")
    if not stamp:
        return {"ok": False, "reason": "registered_at-absent"}
    registered = parse_registered_at(str(stamp))
    rows = []
    ok = True
    for rel in freeze_compliant_paths(man):
        path = repo / rel
        if not path.is_file():
            ok = False
            rows.append({"path": rel, "present": False, "precedes": False})
            continue
        mt = mtime_utc(path)
        precedes = registered.timestamp() < mt.timestamp()
        if not precedes:
            ok = False
        rows.append(
            {
                "path": rel,
                "present": True,
                "registered_at": registered.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "mtime_utc": mt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "rubric_precedes_dossier": precedes,
            }
        )
    if not rows:
        return {"ok": False, "reason": "no-freeze-compliant-dossiers"}
    return {"ok": ok, "registered_at": str(stamp), "dossiers": rows}


def ordering_negative_control(repo: Path, manifest_path: Path) -> dict[str, Any]:
    man = load_json(manifest_path)
    rec = man.get("rubric") or {}
    registered = parse_registered_at(str(rec.get("registered_at")))
    rels = freeze_compliant_paths(man)
    if not rels:
        return {"ok": False, "reason": "no-fixture"}
    src = repo / rels[0]
    early_epoch = registered.timestamp() - 120.0
    with tempfile.TemporaryDirectory(prefix="arc0002-early-") as tmp:
        dst = Path(tmp) / "early-dossier.json"
        dst.write_bytes(src.read_bytes())
        os.utime(dst, (early_epoch, early_epoch))
        mt = mtime_utc(dst)
        precedes = registered.timestamp() < mt.timestamp()
    return {
        "ok": precedes is False,
        "would_pass_if_we_ignored_mtime": precedes,
        "forced_mtime_utc": mt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "registered_at": registered.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def live_preexisting_dossiers(repo: Path) -> list[dict[str, Any]]:
    found = []
    for rel in (
        "command-center/phase3/A1/DESIGN.json",
        "command-center/phase3/A2/DESIGN.json",
    ):
        path = repo / rel
        found.append(
            {
                "path": rel,
                "present": path.is_file(),
                "mtime_utc": (
                    mtime_utc(path).strftime("%Y-%m-%dT%H:%M:%SZ")
                    if path.is_file()
                    else None
                ),
            }
        )
    return found


def dimension_ids() -> list[str]:
    return [d["id"] for d in public_dimensions()]
