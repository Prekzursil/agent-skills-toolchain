"""IMP-0104 probe 2 (verifier): the partial-failure guarantee is
all-or-nothing. A simulated kill after the first member write rolls back to a
census of zero package files and no lock; a mutually incompatible pair
(capstone, keystone) fails at collection-DEFINITION time, before any install.

Re-run: python command-center/p2-wave/probes/IMP-0104/probe2_partial_failure.py
Exit 0 iff rollback census is empty and the conflict is a definition-time error.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools"))
from marketplace.collections import (  # noqa: E402
    CollectionDefinitionError,
    build_demo_index,
    define_collection,
    install_collection,
    observed_matches_guarantee,
    re_toolchain_collection,
)

index = build_demo_index()
target = Path(tempfile.mkdtemp(prefix="imp0104-probe2-"))
try:
    collection = re_toolchain_collection(index)
    installed = install_collection(collection, index, target)
    clean_census = observed_matches_guarantee(collection, target)

    killed = False
    try:
        install_collection(collection, index, target, crash_after_first_write=True)
    except Exception as exc:
        killed = type(exc).__name__ == "InstallRolledBack"
    after_kill = {
        "package_files": len(list(target.glob("*.pkg"))),
        "locks": len(list(target.glob("collection-lock.json"))),
    }

    conflict_reported_at = ""
    conflict_reason = ""
    try:
        define_collection(index, ["capstone", "keystone"])
    except CollectionDefinitionError as exc:
        conflict_reported_at = "definition"
        conflict_reason = str(exc)
finally:
    shutil.rmtree(target, ignore_errors=True)

result = {
    "installed_ok": installed["lockfile"] == "collection-lock.json",
    "clean_census": clean_census,
    "kill_rolled_back": killed,
    "census_after_kill": after_kill,
    "conflict_reported_at": conflict_reported_at,
    "conflict_reason": conflict_reason,
    "unit_id": "IMP-0104",
}
result["pass"] = (
    result["installed_ok"]
    and clean_census["one_lockfile"]
    and clean_census["member_files_match"]
    and killed
    and after_kill["package_files"] == 0
    and after_kill["locks"] == 0
    and conflict_reported_at == "definition"
)
print(json.dumps(result, indent=1))
if result["pass"]:
    print("SUCCESS:IMP-0104-probe2 all-or-nothing rollback + definition-time conflict")
else:
    print("FAILED:IMP-0104-probe2")
sys.exit(0 if result["pass"] else 1)
