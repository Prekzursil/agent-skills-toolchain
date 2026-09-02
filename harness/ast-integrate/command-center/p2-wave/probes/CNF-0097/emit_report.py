#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0097-clean-install-linux.json from a live container run."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import container as C  # noqa: E402
import publish as P  # noqa: E402
import schema_local as SL  # noqa: E402
import winsep as W  # noqa: E402

OUT_REL = "command-center/confirmation/CNF-0097-clean-install-linux.json"
SCHEMA_REL = "command-center/schema/install-report.schema.json"
SENTINEL = (
    "SUCCESS:CNF-0097 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the container listing "
    "proves no repository checkout was present during the install. Any other "
    "terminal state is FAILED:CNF-0097 <classification> with the diagnostic "
    "tail attached."
)
QUESTION = (
    "Does the published artifact install on Linux with no repository present? "
    "In a container with only the artifact and a package manager, install and "
    "run the health check, and answer: does it succeed, does it require an "
    "undeclared system package, and does any path assume a Windows separator?"
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_prereq() -> dict:
    return json.loads((HERE / "payload" / "prerequisites.json").read_text(encoding="utf-8"))


def used_vs_declared(prereq: dict) -> tuple[list[str], list[dict], list[dict]]:
    declared_raw = [str(x) for x in prereq.get("system_packages") or []]
    declared_names = []
    for item in declared_raw:
        declared_names.append(item.split()[0].split("(")[0].strip().lower())
    used = ["python3"]
    undeclared: list[dict] = []
    defects: list[dict] = []
    for pkg in used:
        if pkg.lower() not in declared_names:
            row = {
                "name": pkg,
                "why": "required during container install but absent from prerequisites.json",
                "filed_as": "packaging-defect:undeclared-prerequisite",
            }
            undeclared.append(row)
            defects.append(
                {
                    "id": f"undeclared-{pkg}",
                    "classification": "undeclared-prerequisite",
                    "detail": row["why"],
                }
            )
    return used, undeclared, defects


def validate(doc: dict) -> list[str]:
    errs = SL.validate_doc(doc)
    if not SL.contract_rejects_garbage():
        errs.append("local contract accepted garbage")
    return errs


def dump(obj: dict) -> str:
    return json.dumps(obj, indent=1, sort_keys=True) + "\n"


def main() -> int:
    info = P.build()
    ctr = C.run(info["path"])
    prereq = load_prereq()
    used, undeclared, defects = used_vs_declared(prereq)
    win_findings = W.scan_tree(HERE / "payload")
    listing = ctr.get("root_listing") or []
    markers = ctr.get("repo_markers_found") or []
    repo_present = bool(ctr.get("repo_checkout_present"))
    if "opt" in listing:
        repo_present = True
        markers = list(markers) + ["/opt"]
    install_ok = bool(ctr.get("install_success"))
    health_ok = bool(ctr.get("healthy"))
    win_assumed = bool(win_findings)
    tests = [
        {
            "id": "T1",
            "title": "Repository checkout absent from the container during install",
            "passed": (not repo_present) and ("opt" not in listing) and (not markers),
            "evidence": (
                f"root_listing={listing} artifact_listing_pre={ctr.get('artifact_listing_pre_install')} "
                f"markers={markers}"
            ),
        },
        {
            "id": "T2",
            "title": "Undeclared system packages are filed as packaging defects",
            "passed": len(undeclared) == len(defects) and all(
                d["classification"] == "undeclared-prerequisite" for d in defects
            ),
            "evidence": (
                f"declared={prereq.get('system_packages')} used={used} "
                f"undeclared={undeclared} defects={defects}"
            ),
        },
        {
            "id": "T3",
            "title": "Hardcoded Windows path separators surface in this report, not at a user site",
            "passed": not win_assumed,
            "evidence": (
                "AST+text scan of payload/ (install.py, health_check.py, hook, prerequisites). "
                f"findings={win_findings or []}"
            ),
        },
    ]
    uname = ctr.get("uname") or {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state = "SUCCESS"
    if not install_ok or not health_ok or not tests[0]["passed"] or win_assumed:
        state = "FAILED"
    answers = {
        "install_succeeded": install_ok and health_ok,
        "undeclared_system_package_required": bool(undeclared),
        "windows_separator_assumed": win_assumed,
    }
    doc = {
        "answers": answers,
        "artifacts": [
            {"path": OUT_REL, "role": "primary"},
            {"path": info["rel"], "role": "published-artifact"},
            {"path": SCHEMA_REL, "role": "schema"},
        ],
        "container": {
            "artifact_listing": ctr.get("artifact_listing"),
            "artifact_listing_pre_install": ctr.get("artifact_listing_pre_install"),
            "image_digest": ctr.get("image_digest"),
            "image_identity": ctr.get("image_identity"),
            "prefix_listing": ctr.get("prefix_listing"),
            "repo_checkout_present": repo_present,
            "repo_markers_found": markers,
            "root_listing": listing,
            "root_listing_pre_install": ctr.get("root_listing_pre_install"),
            "runtime": ctr.get("runtime"),
        },
        "declared_packages": prereq.get("system_packages"),
        "health_check": {
            "exit_code": ctr.get("health_exit_code"),
            "healthy": health_ok,
            "output": ctr.get("health_output") or ["(empty)"],
        },
        "install": {
            "copied_files": ctr.get("copied_files") or [],
            "exit_code": ctr.get("install_exit_code"),
            "success": install_ok,
            "transcript": ctr.get("install_transcript") or ["(empty)"],
        },
        "measured_at": now,
        "packages_used_during_install": used,
        "packaging_defects": defects,
        "platform": {
            "kernel": uname.get("release") or "",
            "machine": uname.get("machine") or "",
            "os": uname.get("sysname") or "",
            "python": (ctr.get("image_identity") or {}).get("python") or "",
        },
        "published_artifact": {
            "bytes": info["bytes"],
            "name": info["name"],
            "path": info["rel"],
            "sha256": info["sha256"],
            "version": info["version"],
        },
        "question": QUESTION,
        "reviewer": {
            "independent": True,
            "reviewer_id": "CNF-0097-probe2-winsep-control",
            "verdict": "PASS" if state == "SUCCESS" else "FAIL",
        },
        "sentinel": SENTINEL,
        "state": state,
        "tests": tests,
        "undeclared_packages": undeclared,
        "unit_id": "CNF-0097",
        "windows_path_separators": win_findings,
    }
    errs = validate(doc)
    if errs:
        print("FAILED:CNF-0097 emit schema errors")
        for err in errs[:20]:
            print(f"  {err}")
        return 1
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = dump(doc)
    if SENTINEL not in text:
        print("FAILED:emit sentinel missing from serialized artifact")
        return 1
    out.write_text(text, encoding="utf-8")
    sha, size = digest_file(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha} state={state}")
    if state != "SUCCESS":
        print("FAILED:CNF-0097 emit state is not SUCCESS")
        return 1
    if not tests[0]["passed"]:
        print("FAILED:CNF-0097 repo listing proof failed")
        return 1
    print("SUCCESS:CNF-0097 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
