"""Three real unit shapes sampled from this worktree.

Idempotence criterion: two executions with the same idempotence_key yield
the same CRLF-normalized sha256 of the unit's primary artifact. A shape
that fails is classified NON-IDEMPOTENT; the runtime must skip-if-complete
rather than re-execute it after SUCCEEDED.

Shapes (live code, not hypothetical):
  1. generated-ssot — ARC-0010 generator.two_run_identical
  2. architecture-dossier-emit — wall-clock ended_at, the live emit_design pattern
  3. shared-reducer — TST-0003 reducer.evaluate on a frozen receipt
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
GEN_DIR = REPO / "command-center/p2-wave/probes/ARC-0010"
REDUCER = REPO / "command-center/p2-wave/probes/TST-0003/reducer.py"
PASS_FIX = REPO / "command-center/p2-wave/probes/TST-0003/fixtures/SYNTH-PASS.json"
EMIT_0003 = REPO / "command-center/p2-wave/probes/ARC-0003/emit_design.py"
EMIT_0010 = REPO / "command-center/p2-wave/probes/ARC-0010/emit_design.py"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"import-fail:{path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def shape_generated_ssot() -> dict[str, Any]:
    if str(GEN_DIR) not in sys.path:
        sys.path.insert(0, str(GEN_DIR))
    import generator as G  # type: ignore

    registry = G.load_default_registry()
    identical, nfiles = G.two_run_identical(registry)
    a = G.generate(registry)
    b = G.generate(registry)
    blob_a = b"".join(v for _, v in sorted(a.items()))
    blob_b = b"".join(v for _, v in sorted(b.items()))
    sha_a, sha_b = _sha(blob_a), _sha(blob_b)
    idempotent = bool(identical) and sha_a == sha_b and nfiles >= 8
    return {
        "id": "generated-ssot",
        "catalog_shape": "ARC-0010 generated SSOT",
        "source": "command-center/p2-wave/probes/ARC-0010/generator.py",
        "artifact": "generate(registry) concatenated files",
        "run1_sha256": sha_a,
        "run2_sha256": sha_b,
        "nfiles": nfiles,
        "idempotent": idempotent,
        "classification": "IDEMPOTENT" if idempotent else "NON-IDEMPOTENT",
        "note": "Same registry bytes + generator_version 1.0.0; no timestamps.",
    }


def shape_dossier_emit() -> dict[str, Any]:
    """Mirror the live architecture-dossier emitters: ended_at = datetime.now()."""
    cites = []
    for p in (EMIT_0003, EMIT_0010):
        text = p.read_text(encoding="utf-8") if p.is_file() else ""
        cites.append(
            {
                "path": str(p.relative_to(REPO).as_posix()),
                "calls_datetime_now": "datetime.now(" in text,
            }
        )
    with tempfile.TemporaryDirectory(prefix="arc0031-dossier-") as td:
        root = Path(td)

        def emit(path: Path) -> None:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            doc = {
                "unit_id": "ARC-0031-scratch",
                "state": "SUCCESS",
                "sentinel": "SUCCESS:ARC-0031-scratch",
                "ended_at": now,
                "emitted_ns": time.time_ns(),
                "payload": "architecture-dossier-emit-shape",
            }
            path.write_text(
                json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
            )

        p1 = root / "run1.json"
        emit(p1)
        time.sleep(0.02)
        p2 = root / "run2.json"
        emit(p2)
        sha_a = _sha(p1.read_bytes())
        sha_b = _sha(p2.read_bytes())
    idempotent = sha_a == sha_b
    return {
        "id": "architecture-dossier-emit",
        "catalog_shape": "ARC-* DESIGN.json emit (wall-clock ended_at)",
        "source": "live emit_design.py pattern on this tree",
        "artifact": "scratch DESIGN-shaped JSON",
        "run1_sha256": sha_a,
        "run2_sha256": sha_b,
        "idempotent": idempotent,
        "classification": "IDEMPOTENT" if idempotent else "NON-IDEMPOTENT",
        "live_emitters_call_datetime_now": cites,
        "note": (
            "Re-running emit_design.py mutates timestamps. The runtime must "
            "skip-if-complete after SUCCEEDED rather than re-execute this shape."
        ),
    }


def shape_shared_reducer() -> dict[str, Any]:
    mod = _load(REDUCER, "arc0031_tst0003_reducer")
    receipt = json.loads(PASS_FIX.read_text(encoding="utf-8"))
    v1 = mod.evaluate(receipt)
    v2 = mod.evaluate(receipt)
    raw1 = json.dumps(v1, sort_keys=True, separators=(",", ":")).encode("utf-8")
    raw2 = json.dumps(v2, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sha_a, sha_b = _sha(raw1), _sha(raw2)
    idempotent = sha_a == sha_b and v1.get("verdict") == "PASS"
    return {
        "id": "shared-reducer",
        "catalog_shape": "TST-0003 shared 12-condition completion reducer",
        "source": "command-center/p2-wave/probes/TST-0003/reducer.py",
        "artifact": "evaluate(SYNTH-PASS) verdict object",
        "run1_sha256": sha_a,
        "run2_sha256": sha_b,
        "verdict": v1.get("verdict"),
        "idempotent": idempotent,
        "classification": "IDEMPOTENT" if idempotent else "NON-IDEMPOTENT",
        "note": "Pure function of the receipt; exit code is not consulted.",
    }


def run_all() -> list[dict[str, Any]]:
    return [
        shape_generated_ssot(),
        shape_dossier_emit(),
        shape_shared_reducer(),
    ]
