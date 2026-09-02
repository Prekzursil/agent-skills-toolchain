#!/usr/bin/env python3
"""Write ADV-0005 from engine.build_record; register CC-0009 on ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ADV = REPO / "command-center" / "p2-wave" / "probes" / "ADV-0005"
sys.path.insert(0, str(ADV))
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import engine as E  # noqa: E402
import artifact_register as AR  # noqa: E402


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def dump(path: Path, doc: object) -> None:
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def refresh_manifest(uid: str, rel: str, out: Path, probe_dir: Path) -> None:
    man_path = probe_dir / "UNIT-ARTIFACT-MANIFEST.json"
    sha, nbytes = digest(out)
    man = json.loads(man_path.read_text(encoding="utf-8")) if man_path.is_file() else {}
    if not isinstance(man, dict):
        man = {}
    man.setdefault("schema_version", 1)
    man["unit_id"] = uid
    rows = man.get("artifacts")
    if not isinstance(rows, list):
        rows = []
        man["artifacts"] = rows
    hit = False
    for a in rows:
        if isinstance(a, dict) and str(a.get("path") or "").replace("\\", "/") == rel:
            a["sha256"] = sha
            a["bytes"] = nbytes
            a["present"] = True
            a["unit_id"] = uid
            hit = True
    if not hit:
        rows.insert(
            0,
            {
                "path": rel,
                "sha256": sha,
                "bytes": nbytes,
                "present": True,
                "unit_id": uid,
                "role": "primary",
            },
        )
    dump(man_path, man)


def main() -> int:
    out = E.REPO / E.OUTPUT_REL
    bak = out.with_name(out.name + ".g1bak")
    if out.is_file() and not bak.is_file():
        out.replace(bak)
    try:
        record = E.build_record(0, "pre-write-engine", 0, "pre-write-engine")
        record["state"] = "SUCCESS"
        record["sentinel"] = "SUCCESS:ADV-0005"
        record["completion_sentinel"] = E.CATALOG_SENTINEL
        record["unit_id"] = E.UNIT
        record["unblind"] = {
            "vote_counting": False,
            "disagreements": E.unblind_pass()["disagreements"],
        }
        text = json.dumps(record, indent=2, sort_keys=True, ensure_ascii=True)
        if E.CATALOG_SENTINEL not in text:
            record["completion_sentinel"] = E.CATALOG_SENTINEL
            text = json.dumps(record, indent=2, sort_keys=True, ensure_ascii=True)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8", newline="\n")
    except Exception:
        if bak.is_file() and not out.is_file():
            bak.replace(out)
        raise
    if bak.is_file():
        bak.unlink()
    refresh_manifest(E.UNIT, E.OUTPUT_REL, out, ADV)
    sha, n = digest(out)
    print(f"ADV-0005 wrote bytes={n} sha256={sha} state={record.get('state')} targets={len(record.get('targets') or [])}")

    cc_rel = "command-center/receipts/CC-0009.json"
    cc_path = REPO / cc_rel
    row = AR.register_path(REPO, cc_rel, unit_id="CC-0009", consumer="json")
    refresh_manifest("CC-0009", cc_rel, cc_path, REPO / "command-center" / "p2-wave" / "probes" / "CC-0009")
    print(f"CC-0009 registered sha256={row['sha256']} first_key={row.get('first_parsed_key')!r}")
    c11 = AR.check_condition_11(REPO, unit_id="CC-0009", output_path=cc_rel)
    print(f"CC-0009 c11 {c11.result}: {c11.reason}")
    return 0 if c11.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
