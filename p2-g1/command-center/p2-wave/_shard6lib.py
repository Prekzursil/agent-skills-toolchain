#!/usr/bin/env python3
"""Shard-6 shared helpers: receipt core checks, sha, manifest/return writers.

Contract:
- receipts are NEVER rewritten by the builder (prior independent reviewer
  closures with reviewer.verdict=PASS + independent=true still verify live;
  the builder keeps them byte-identical).
- per-unit manifest sha256 is CRLF-normalized (matching
  _measure_one_delivered.py digest_file).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
P2WAVE = REPO / "command-center" / "p2-wave"
PROBES = P2WAVE / "probes"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


class ProbeFailure(AssertionError):
    pass


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise ProbeFailure(msg)


def receipt_path(uid: str) -> Path:
    return REPO / "command-center" / "receipts" / f"{uid}.json"


def load_receipt(uid: str) -> tuple[dict, str, Path]:
    p = receipt_path(uid)
    require(p.is_file() and p.stat().st_size > 0, f"{uid} receipt absent/empty")
    text = p.read_text(encoding="utf-8")
    doc = json.loads(text)
    require(isinstance(doc, dict), f"{uid} receipt not a dict")
    return doc, text, p


def check_receipt_core(uid: str) -> dict:
    """Core deliverability checks shared by every probe: parses, SUCCESS state,
    sentinel present, independent reviewer PASS closure."""
    doc, text, p = load_receipt(uid)
    st = str(doc.get("state") or "").upper()
    require(st == "SUCCESS", f"{uid} receipt state={st}")
    sent = str(doc.get("sentinel") or doc.get("completion_marker") or "")
    require(sent.startswith(f"SUCCESS:{uid}"), f"{uid} sentinel malformed: {sent}")
    require(sent in text, f"{uid} sentinel string absent from receipt bytes")
    rev = doc.get("reviewer") or {}
    require(
        str(rev.get("verdict") or "").upper() == "PASS" and rev.get("independent") is True,
        f"{uid} reviewer closure not PASS/independent",
    )
    return doc


def sha256_normalized(path: Path) -> str:
    raw = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_manifest(uid: str, supporting: list[tuple[Path, str]] | None = None) -> Path:
    """Write probes/<uid>/UNIT-ARTIFACT-MANIFEST.json with the primary receipt
    row (CRLF-normalized sha) plus optional supporting rows."""
    doc, _t, p = load_receipt(uid)
    out_rel = p.relative_to(REPO).as_posix()
    rows = [
        {
            "unit_id": uid,
            "path": out_rel,
            "bytes": p.stat().st_size,
            "sha256": sha256_normalized(p),
            "present": True,
            "receipt_path": (PROBES / uid / "SUBAGENT-RETURN.json")
            .relative_to(REPO)
            .as_posix(),
            "role": "primary",
        }
    ]
    for path, role in supporting or []:
        rows.append(
            {
                "unit_id": uid,
                "path": path.relative_to(REPO).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_normalized(path),
                "present": True,
                "receipt_path": (PROBES / uid / "SUBAGENT-RETURN.json")
                .relative_to(REPO)
                .as_posix(),
                "role": role,
            }
        )
    man = {
        "unit_id": uid,
        "generated_by": "builder shard 6 wave 2",
        "hash_note": "sha256 over CRLF-normalized bytes (LF), matching _measure_one_delivered.py",
        "artifacts": rows,
    }
    mp = PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json"
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(man, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return mp


def write_return(
    uid: str,
    named_probes: list[dict],
    notes: str,
    supporting: list[tuple[Path, str]] | None = None,
    extra: dict | None = None,
) -> Path:
    """Write probes/<uid>/SUBAGENT-RETURN.json + per-unit manifest.

    named_probes entries: {id, name, command, exit_code, raw_output}.
    The reviewer block quotes the receipt's EXISTING independent closure; the
    builder claims no closure of its own."""
    doc, _t, p = load_receipt(uid)
    rev = doc.get("reviewer") or {}
    ret = {
        "id": uid,
        "unit_id": uid,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": f"SUCCESS:{uid}",
        "output_path": p.relative_to(REPO).as_posix(),
        "output_schema": "command-center/schema/see-catalog.json",
        "cloud_ok": False,
        "artifacts": [
            {
                "path": p.relative_to(REPO).as_posix(),
                "bytes": p.stat().st_size,
                "sha256": sha256_normalized(p),
                "exists": True,
            }
        ],
        "named_probes": named_probes,
        "reviewer": {
            "verdict": rev.get("verdict"),
            "independent": rev.get("independent"),
            "reviewer_id": rev.get("reviewer_id"),
            "source": "pre-existing receipt closure (kept; still verifies live via this unit's probes)",
        },
        "owner_gate": "none - unit was not owner-gated",
        "notes": notes,
        "ts_source": "receipt timestamps kept verbatim; probes add none",
    }
    if extra:
        ret.update(extra)
    rp = PROBES / uid / "SUBAGENT-RETURN.json"
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(ret, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    write_manifest(uid, supporting)
    return rp


def run_capture(argv: list[str], cwd: Path | None = None) -> tuple[int, str]:
    p = subprocess.run(
        argv, cwd=str(cwd or REPO), capture_output=True, text=True, timeout=300
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def scratch_dir(prefix: str) -> tempfile.TemporaryDirectory:
    return tempfile.TemporaryDirectory(prefix=prefix)


def git_fixture(paths: dict[str, str], delete: list[str] | None = None) -> tuple[str, list[str]]:
    """Throwaway git repo: commit `paths`, optionally commit deletion of
    `delete` entries. Returns (repo_dir, [revision]) — the first revision holds
    the original content."""
    import os as _os

    tmp = tempfile.mkdtemp(prefix="shard6-gitfix-")
    env = dict(_os.environ)
    env["GIT_AUTHOR_NAME"] = env["GIT_COMMITTER_NAME"] = "shard6-fixture"
    env["GIT_AUTHOR_EMAIL"] = env["GIT_COMMITTER_EMAIL"] = "shard6@fixture.invalid"
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        env.pop(key, None)

    def git(*args: str) -> str:
        r = subprocess.run(
            ["git", "-C", tmp, *args], capture_output=True, text=True, env=env, timeout=120
        )
        require(r.returncode == 0, f"git fixture {' '.join(args)}: {r.stderr[:200]}")
        return r.stdout.strip()

    git("init", "-q")
    git("config", "user.name", "shard6-fixture")
    git("config", "user.email", "shard6@fixture.invalid")
    for rel, content in paths.items():
        f = Path(tmp) / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content, encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "fixture: original")
    rev = git("rev-parse", "HEAD")
    for rel in delete or []:
        (Path(tmp) / rel).unlink()
    if delete:
        git("add", "-A")
        git("commit", "-q", "-m", "fixture: delete")
    return tmp, [rev]


__all__ = [
    "REPO", "PROBES", "P2WAVE", "NOT_DELIVERING", "ProbeFailure", "require",
    "receipt_path", "load_receipt", "check_receipt_core", "sha256_normalized",
    "sha256_text", "write_manifest", "write_return", "run_capture", "scratch_dir",
    "git_fixture",
]

if __name__ == "__main__":
    print("shard6lib: import-only module", file=sys.stderr)
    sys.exit(2)
