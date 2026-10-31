#!/usr/bin/env python3
"""probe1 for TST-0026: an unmigrated schema edit is rejected (both states).

bad   : schema edited, no migration row              -> gate exits 1, names file
good  : same edit + migration row + version bump     -> gate exits 0
extra : rebaseline at the accepted state, edit again with a stale row and no
        new bump                                     -> gate exits 1
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "TST-0026"
HERE = Path(__file__).resolve().parent
GATE = HERE / "gate.py"

SCHEMA_V1 = {
    "schema_version": 1,
    "title": "unit",
    "type": "object",
    "properties": {"unit_id": {"type": "string"}, "state": {"type": "string"}},
    "required": ["unit_id", "state"],
}
LAUNCHER = "#!/usr/bin/env python3\n# frozen launcher fixture\n"


def baseline_tree(tree: Path) -> dict:
    (tree / "launchers").mkdir(parents=True)
    (tree / "schemas").mkdir(parents=True)
    (tree / "not-frozen").mkdir(parents=True)
    (tree / "launchers" / "fanout.py").write_text(LAUNCHER, encoding="utf-8", newline="\n")
    (tree / "schemas" / "unit.schema.json").write_text(
        json.dumps(SCHEMA_V1, indent=1) + "\n", encoding="utf-8", newline="\n")
    (tree / "schemas" / "launcher.schema.json").write_text(
        json.dumps({"schema_version": 1, "title": "launcher"}, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    (tree / "not-frozen" / "notes.txt").write_text("not frozen\n", encoding="utf-8", newline="\n")
    return snapshot(tree)


def snapshot(tree: Path) -> dict:
    files = []
    for rel in ["launchers/fanout.py", "schemas/unit.schema.json", "schemas/launcher.schema.json"]:
        p = tree / rel
        raw = p.read_bytes().replace(b"\r\n", b"\n")
        ver = 1
        try:
            head = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(head, dict) and isinstance(head.get("schema_version"), int):
                ver = head["schema_version"]
        except (json.JSONDecodeError, OSError):
            pass
        files.append({"path": rel, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                      "schema_version": ver})
    return {"schema_version": 1, "files": files}


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-I", "-B", str(GATE), *args],
                          capture_output=True, text=True, cwd=str(REPO))


def main() -> int:
    checks = {}
    with tempfile.TemporaryDirectory() as td:
        tdpath = Path(td)
        tree = tdpath / "tree"
        baseline = baseline_tree(tree)
        base_path = tdpath / "baseline.json"
        base_path.write_text(json.dumps(baseline, indent=1), encoding="utf-8", newline="\n")
        empty = tdpath / "none.json"
        empty.write_text(json.dumps({"migrations": []}), encoding="utf-8", newline="\n")

        clean = run(["--tree", str(tree), "--baseline", str(base_path), "--migrations", str(empty)])
        checks["clean_tree_accepted"] = clean.returncode == 0

        schema = tree / "schemas" / "unit.schema.json"
        doc = json.loads(schema.read_text(encoding="utf-8"))
        doc["properties"]["owner"] = {"type": "string"}
        schema.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
        bad = run(["--tree", str(tree), "--baseline", str(base_path), "--migrations", str(empty)])
        checks["unmigrated_change_rejected"] = bad.returncode == 1
        checks["rejected_names_file"] = "schemas/unit.schema.json" in bad.stdout
        checks["rejected_reason_unmigrated"] = ("unmigrated" in bad.stdout) or ("no-version-bump" in bad.stdout)

        doc["schema_version"] = 2
        schema.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
        mig = tdpath / "mig.json"
        mig.write_text(json.dumps({"migrations": [{
            "path": "schemas/unit.schema.json", "action": "edit", "to_version": 2,
            "reason": "add owner property"}]}), encoding="utf-8", newline="\n")
        good = run(["--tree", str(tree), "--baseline", str(base_path), "--migrations", str(mig)])
        checks["migrated_change_with_bump_accepted"] = good.returncode == 0

        baseline2 = snapshot(tree)
        base2 = tdpath / "baseline2.json"
        base2.write_text(json.dumps(baseline2, indent=1), encoding="utf-8", newline="\n")
        doc["properties"]["extra"] = {"type": "string"}
        schema.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
        mig2 = tdpath / "mig2.json"
        mig2.write_text(json.dumps({"migrations": [{
            "path": "schemas/unit.schema.json", "action": "edit", "to_version": 2,
            "reason": "stale row, no new bump"}]}), encoding="utf-8", newline="\n")
        nobump = run(["--tree", str(tree), "--baseline", str(base2), "--migrations", str(mig2)])
        checks["migration_row_without_bump_still_rejected"] = (
            nobump.returncode == 1 and "no-version-bump" in nobump.stdout)
    ok = all(bool(v) for v in checks.values())
    print(json.dumps({"unit_id": UID, "probe": "probe1-unmigrated-rejected", "pass": ok, "checks": checks}))
    if ok:
        print(f"SUCCESS:{UID}-probe1 unmigrated schema edit rejected naming the file; migrated edit with version bump accepted; bump-less second edit rejected at the moved freeze")
        return 0
    print(f"FAILED:{UID}-probe1 " + ",".join(k for k, v in checks.items() if not v))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
