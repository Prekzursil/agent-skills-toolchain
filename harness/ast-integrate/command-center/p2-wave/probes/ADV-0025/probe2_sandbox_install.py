#!/usr/bin/env python3
"""Probe 2: install linter-accepted variants in a disposable sandbox; record effects."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import (  # noqa: E402
    ABUSE_TARGETS,
    OUTSIDE_BODY,
    REPO,
    UNIT,
    build_all,
    dumps,
    sandbox_install,
    submit_to_linter,
    unsafe_extract,
    with_work,
)


def measure(work: Path) -> dict:
    variants = build_all(work)
    # Isolate dest_home so the naive path-escape fixture (sibling under work)
    # cannot be attributed to a sandbox install.
    dest_home = work / "sandbox" / "dest-home"
    dest_home.mkdir(parents=True, exist_ok=True)
    naive_root = work / "naive" / "extract-root"
    outside_variant = variants["T-WRITE-OUTSIDE-ROOT"]
    naive_written = unsafe_extract(Path(outside_variant["blob"]), naive_root)
    naive_outside = work / "naive" / "OUTSIDE-ADV0025.txt"
    naive_went_red = (
        naive_outside.is_file() and naive_outside.read_bytes() == OUTSIDE_BODY
    )

    lint_rows = {}
    for vid, spec in variants.items():
        lint_rows[vid] = submit_to_linter(
            Path(spec["blob"]), variant_id=vid, work=work
        )

    installs = []
    for vid, spec in variants.items():
        lint = lint_rows[vid]
        if not lint.get("accepted"):
            installs.append(
                {
                    "variant_id": vid,
                    "skipped": True,
                    "reason": "linter-rejected",
                    "rule_ids": list(lint.get("rule_ids") or []),
                    "installed": False,
                    "wrote_outside_dest_home": False,
                    "postinstall_fired": False,
                    "live_plugin_tree_used": False,
                }
            )
            continue
        row = sandbox_install(spec, dest_home)
        row["skipped"] = False
        row["linter_accepted"] = True
        installs.append(row)

    by_id = {r["variant_id"]: r for r in installs}
    control = by_id["C-BENIGN"]
    control_ok = (
        control.get("installed") is True
        and not control.get("raised")
        and not control.get("wrote_outside_dest_home")
        and not control.get("inside_repo")
        and not control.get("live_plugin_tree_used")
    )
    repo_escape = any(r.get("inside_repo") for r in installs)
    live_tree = any(r.get("live_plugin_tree_used") for r in installs)
    write_row = by_id["T-WRITE-OUTSIDE-ROOT"]
    script_row = by_id["T-INSTALL-TIME-SCRIPT"]
    pass_ok = (
        control_ok
        and naive_went_red
        and not repo_escape
        and not live_tree
        and {r["variant_id"] for r in installs} == {"C-BENIGN", *ABUSE_TARGETS}
    )
    return {
        "probe": "probe2-sandbox-install",
        "unit_id": UNIT,
        "dest_home": str(dest_home),
        "inside_repo": bool(control.get("inside_repo")),
        "live_plugin_tree_used": live_tree,
        "control_installed_clean": control_ok,
        "naive_extract_went_red": naive_went_red,
        "naive_written_count": len(naive_written),
        "naive_outside_path": str(naive_outside) if naive_outside.is_file() else None,
        "write_outside_install_escaped": bool(
            write_row.get("wrote_outside_dest_home")
        ),
        "write_outside_raised": write_row.get("raised"),
        "postinstall_fired": bool(script_row.get("postinstall_fired")),
        "installs": installs,
        "pass": pass_ok,
        "repo": str(REPO),
    }


def main() -> int:
    doc = with_work(measure)
    print(dumps(doc))
    print(
        "control_ok={control} naive_red={naive} escaped={escaped} "
        "postinstall_fired={script} live_tree={live}".format(
            control=doc["control_installed_clean"],
            naive=doc["naive_extract_went_red"],
            escaped=doc["write_outside_install_escaped"],
            script=doc["postinstall_fired"],
            live=doc["live_plugin_tree_used"],
        )
    )
    if not doc.get("pass"):
        print("FAILED:ADV-0025-probe2 sandbox install matrix did not hold")
        return 1
    print(
        "SUCCESS:ADV-0025-probe2 sandbox install of accepted variants; "
        "live plugin tree untouched"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
