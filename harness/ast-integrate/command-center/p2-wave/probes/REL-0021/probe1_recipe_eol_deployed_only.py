#!/usr/bin/env python3
"""Probe 1: blob recipe CRLF delta, deployed-only class, EOL-only identical."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import parity as P  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/REL-0021.json"


def fail(msg: str) -> int:
    print(f"FAILED:REL-0021-probe1 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="rel0021-p1-") as td:
        root = Path(td)
        healthy = S.build_healthy(root / "healthy")
        control = S.build_control(root / "control")
        recipe = P.measure_recipe(control["repo"], control["known_path"])
        healthy_census = P.census_world(
            healthy["repo"], healthy["package_zip"], healthy["deployed"]
        )
        control_census = P.census_world(
            control["repo"], control["package_zip"], control["deployed"]
        )

    if recipe["crlf_count_difference"] == 0 or recipe["cat_file_equals_archive"]:
        return fail(f"archive and cat-file did not differ {recipe}")
    if recipe["chosen_recipe"] != P.BLOB_RECIPE:
        return fail(f"chosen recipe {recipe['chosen_recipe']}")
    if "git cat-file" not in recipe["retrieval_command"]:
        return fail("retrieval command is not git cat-file")
    if "git archive" not in recipe["rejected_alternative"]:
        return fail("rejected alternative is not git archive")
    if recipe["cat_file_crlf"] != 0:
        return fail(f"LF blob unexpectedly has CRLF {recipe['cat_file_crlf']}")
    if recipe["archive_crlf"] <= recipe["cat_file_crlf"]:
        return fail(f"archive CRLF not greater than cat-file {recipe}")

    if control_census["four_way"]["deployed-only"] != 1:
        return fail(f"deployed-only count {control_census['four_way']}")
    if "shipped/owner-note.txt" not in control_census["deployed_only_paths"]:
        return fail(f"owner file not deployed-only {control_census['deployed_only_paths']}")
    owner = next(r for r in control_census["files"] if r["path"] == "shipped/owner-note.txt")
    if owner["class"] == "missing":
        return fail("deployed-only misclassified as missing")
    if owner["class"] != "deployed-only":
        return fail(f"owner class {owner['class']}")

    if control_census["four_way"]["package-only"] != 1:
        return fail(f"package-only count {control_census['four_way']}")

    eol = next(r for r in healthy_census["files"] if r["path"] == "shipped/eol.txt")
    if eol["class"] != "identical":
        return fail(f"EOL-only file class {eol['class']}")
    if not eol.get("eol_only_difference"):
        return fail("EOL-only file was raw-equal; control did not discriminate endings")
    if eol["git_lf_sha256"] != eol["deployed_lf_sha256"] or eol["git_lf_sha256"] != eol["package_lf_sha256"]:
        return fail("EOL-only LF hashes do not match")
    if eol["git_sha256"] == eol["deployed_sha256"]:
        return fail("EOL-only raw hashes unexpectedly equal")

    if healthy_census["verdict"] != "PROMOTE":
        return fail(f"healthy verdict {healthy_census['verdict']}")
    if healthy_census["four_way"]["divergent-both-ways"] != 0:
        return fail(f"healthy two-way {healthy_census['four_way']}")

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:REL-0021" not in text:
            return fail("receipt sentinel absent")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"receipt self-declared {doc.get('state')}")
        br = doc.get("blob_recipe") or {}
        if int(br.get("crlf_count_difference") or 0) == 0:
            return fail("receipt recipe difference is zero")
        if "git cat-file" not in str(br.get("retrieval_command") or ""):
            return fail("receipt did not name cat-file")

    print(
        json.dumps(
            {
                "probe": "probe1-recipe-eol-deployed-only",
                "cat_file_crlf": recipe["cat_file_crlf"],
                "archive_crlf": recipe["archive_crlf"],
                "crlf_count_difference": recipe["crlf_count_difference"],
                "retrieval_command": recipe["retrieval_command"],
                "deployed_only": control_census["four_way"]["deployed-only"],
                "package_only": control_census["four_way"]["package-only"],
                "eol_class": eol["class"],
                "healthy_verdict": healthy_census["verdict"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:REL-0021-probe1 recipe-eol-deployed-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
