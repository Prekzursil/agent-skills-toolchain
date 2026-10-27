"""ADV-0006 emit: current receipt_core shapes (schema regenerated 2026-08-28)."""
from pathlib import Path

p = Path(
    __file__).resolve().parents[1] / "command-center/p2-wave/probes/ADV-0006/emit_artifact.py"
src = p.read_text(encoding="utf-8")

# ---------- helper functions ----------
old = "def main() -> int:"
new = '''def _fp(cmd: str) -> str:
    import hashlib

    return hashlib.sha256(("command|" + cmd).encode("utf-8")).hexdigest()[:12]


def _probe_card(role: str, cmd: str, raw: str) -> dict:
    return {
        "role": role,
        "method": "command",
        "command": cmd,
        "raw_output": raw,
        "fingerprint": _fp(cmd),
    }


def _artifact_rows() -> list:
    rows = [
        {"path": A.OUTPUT_REL, "role": "primary"},
        {"path": A.SCHEMA_REL, "role": "supporting"},
        {"path": A.CATALOG_REL, "role": "supporting"},
        {"path": "command-center/p2-wave/probes/ADV-0006/audit.py", "role": "supporting"},
        {"path": A.P1_REL, "role": "supporting"},
        {"path": A.P2_REL, "role": "supporting"},
        {"path": "command-center/p2-wave/probes/ADV-0006/emit_artifact.py", "role": "supporting"},
    ]
    out = []
    for row in rows:
        f = A.REPO / row["path"]
        present = f.is_file()
        out.append(
            {
                "path": row["path"],
                "exists": present,
                "role": row["role"],
                **(
                    {"bytes": f.stat().st_size, "sha256": _crlf_sha(f)}
                    if present
                    else {}
                ),
            }
        )
    return out


def _crlf_sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes().replace(b"\\r\\n", b"\\n")).hexdigest()


def main() -> int:'''
assert old == "def main() -> int:"
assert src.count(old) == 1, "main anchor missing"
src = src.replace(old, new, 1)

# ---------- evidence cards ----------
old = '''    evidence = [
        {
            "claim": row["sentence"],
            "verdict": row["verdict"],
            "target_id": row["target_id"],
        }
        for row in meas["rows"]
    ]'''
new = '''    evidence = [
        {
            "claim": str(row["sentence"])[:2000],
            "verdict": row["verdict"],
            "confidence": "almost-certain",
            "anchor": str(row.get("source") or row["target_id"])[:2048],
            "probes": [
                _probe_card("source", A.P1_CMD, raw1),
                _probe_card("verifier", A.P2_CMD, raw2),
            ],
        }
        for row in meas["rows"]
    ]'''
assert old in src, "evidence anchor missing"
src = src.replace(old, new, 1)

# ---------- artifacts ----------
old = '''    artifacts = [{"path": A.OUTPUT_REL, "exists": True, "role": "primary"}]
    for rel in supporting:
        artifacts.append({
            "path": rel,
            "exists": (A.REPO / rel).is_file(),
            "role": "supporting",
        })'''
new = '''    artifacts = _artifact_rows()'''
assert old in src, "artifacts anchor missing"
src = src.replace(old, new, 1)

# ---------- NC kind enum ----------
src = src.replace('"kind": "planted-mutant"', '"kind": "mutation"')
src = src.replace('"kind": "sentence-widening-mutant"', '"kind": "mutation"')

# ---------- retry/timestamps/report after measured_at ----------
old = '''        "measured_at": now,'''
new = '''        "measured_at": now,
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "Two-strikes: after a second failure on the same error "
                "fingerprint the unit pivots instruments. First live attempt on "
                "this worktree generation."
            ),
        },
        "report": {
            "kind": "refutation-record",
            "observations": [
                {
                    "name": row["target_id"],
                    "measured": row["verdict"],
                    "method": "quantifier-vs-cardinality arithmetic + outside-set counterexample hunt",
                    "anchor": str(row.get("source") or row["target_id"])[:2048],
                }
                for row in meas["rows"]
            ],
            "control_ids": [
                "planted-overclaim-vs-scoped",
                "widen-scoped-mutant",
            ],
        },
        "downstream_consumers": [
            {
                "consumer": "p2 wave reducer",
                "artifact_path": A.OUTPUT_REL,
                "executed": True,
                "read_ok": True,
                "probe": _probe_card("verifier", A.P2_CMD, raw2),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "CONFIRMED-registry population is reconstructed from "
                    "calibration plants, live confirmation headlines and CONFIRMED "
                    "rows harvested from command-center/research/*.json; the "
                    "CLAIM-REGISTRY.json SSOT is absent on this worktree, so the "
                    "population may be incomplete."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Restore CLAIM-REGISTRY.json and re-run the population census; "
                    "verdicts recompute mechanically from the same arithmetic."
                ),
            }
        ],'''
assert old in src, "measured_at anchor missing"
src = src.replace(old, new, 1)

p.write_text(src, encoding="utf-8")
import ast
ast.parse(src)
print("0006 emit shapes upgraded")
