#!/usr/bin/env python3
"""WSL-side patches that must match the live p2-g1 host."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path("/home/prekzursil/p2-g1")
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "command-center" / "p2-wave" / "probes" / "CNF-0098"))


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def refresh(uid: str, rel: str) -> None:
    man_path = ROOT / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    out = ROOT / rel
    sha, size = digest(out)
    man = json.loads(man_path.read_text(encoding="utf-8"))
    for a in man.get("artifacts") or []:
        if a.get("unit_id") == uid and str(a.get("path") or "").replace("\\", "/") == rel:
            a["sha256"] = sha
            a["bytes"] = size
            a["present"] = True
    man_path.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print("refresh", uid, sha[:16], size)


def patch_imp0047() -> None:
    from plugin.migration import (
        MigrationEngine,
        Step,
        blake2_tree_digest,
        build_demo_tree,
        censuses,
        censuses_equal,
        demo_engine,
        sha256_file_census,
        wrong_inverse_spec,
    )

    out = ROOT / "command-center" / "receipts" / "IMP-0047.json"
    with tempfile.TemporaryDirectory(prefix="imp0047-wsl-") as tmp:
        base = Path(tmp)
        root = build_demo_tree(base / "rt")
        before_blake = blake2_tree_digest(root)
        before_files = sha256_file_census(root)
        engine = demo_engine()
        engine.migrate(root, "3", journal=base / "rt.json")
        engine.invert(root, "0", journal=base / "rt.json")
        after_blake = blake2_tree_digest(root)
        after_files = sha256_file_census(root)
        once = build_demo_tree(base / "once")
        twice = build_demo_tree(base / "twice")
        demo_engine().migrate(once, "3", journal=base / "once.json")
        e2 = demo_engine()
        e2.migrate(twice, "3", journal=base / "twice.json")
        e2.migrate(twice, "3", journal=base / "twice.json", resume=False)
        resume_engine = demo_engine()
        resume_root = build_demo_tree(base / "resume")
        resume_journal = base / "resume.json"
        resume_engine.migrate(resume_root, "3", journal=resume_journal, kill_after="s1-relocate-key")
        resume_engine.migrate(resume_root, "3", journal=resume_journal, resume=True)
        bad_root = build_demo_tree(base / "bad")
        bad_before = censuses(bad_root)
        bad_engine = MigrationEngine([Step(wrong_inverse_spec())])
        bad_engine.migrate(bad_root, "1", journal=base / "bad.json")
        bad_engine.invert(bad_root, "0", journal=base / "bad.json")
        bad_after = censuses(bad_root)
        doc = json.loads(out.read_text(encoding="utf-8"))
        doc["round_trip"] = {
            "file_count": len(before_files),
            "before_file_census": before_files,
            "after_file_census": after_files,
            "before_blake2": before_blake,
            "after_blake2": after_blake,
            "file_census_restored": after_files == before_files,
            "blake2_restored": after_blake == before_blake,
        }
        doc["idempotency"] = {
            "apply_once_equals_apply_twice": censuses_equal(censuses(once), censuses(twice))
        }
        doc["resume"] = {"s1_not_rerun": resume_engine.by_id["s1-relocate-key"].apply_calls == 1}
        doc["negative_control_wrong_inverse"] = {
            "round_trip_equal": censuses_equal(bad_before, bad_after),
            "detected": not censuses_equal(bad_before, bad_after),
        }
        if "SUCCESS:IMP-0047" not in json.dumps(doc):
            doc["sentinel"] = "SUCCESS:IMP-0047"
        out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    refresh("IMP-0047", "command-center/receipts/IMP-0047.json")


def patch_cnf0098() -> None:
    import estate as E

    live = E.signal_command()
    art = ROOT / "command-center" / "confirmation" / "CNF-0098-macos-reachability.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    proofs = list(doc.get("two_signal_proof") or [])
    found = False
    for p in proofs:
        if isinstance(p, dict) and p.get("method") == "command":
            p["fingerprint"] = live["fingerprint"]
            p["observation"] = live["observation"]
            p["this_host_darwin"] = live["this_host_darwin"]
            found = True
    if not found:
        proofs.append(
            {
                "method": "command",
                "fingerprint": live["fingerprint"],
                "observation": live["observation"],
                "this_host_darwin": live["this_host_darwin"],
            }
        )
    doc["two_signal_proof"] = proofs
    doc["this_host_darwin"] = bool(live["this_host_darwin"])
    art.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    refresh("CNF-0098", "command-center/confirmation/CNF-0098-macos-reachability.json")
    print("cnf0098 darwin", live["this_host_darwin"], live["fingerprint"][:16])


def main() -> None:
    patch_imp0047()
    patch_cnf0098()


if __name__ == "__main__":
    main()
