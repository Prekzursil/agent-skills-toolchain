#!/usr/bin/env python3
"""Probe 1: icacls-style textual classification of writers.

Renders icacls text for every modeled deployed path (and parent chain),
parses that text, and buckets writers into owner / administrators / SYSTEM
/ broad groups. Does not attempt a write. Does not modify any ACL.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from layout import deployed_nodes, packaging_census  # noqa: E402
from lib_acl import (  # noqa: E402
    classify_writers_from_aces,
    naive_broad_writable,
    parse_icacls,
    render_icacls,
    self_test,
    writer_summary,
)

OUT = HERE / "probe1-icacls-classify.raw.json"
UID = "ADV-0036"


def classify_node(node) -> dict:
    text = render_icacls(node.sd)
    path, parsed = parse_icacls(text)
    buckets = classify_writers_from_aces(parsed, node.sd.owner)
    parent_text = None
    parent_buckets = None
    if node.sd.parent_dacl is not None:
        from lib_acl import SecurityDescriptor

        parent_sd = SecurityDescriptor(
            path=node.sd.parent_path or "",
            owner=node.sd.parent_owner or node.sd.owner,
            dacl=list(node.sd.parent_dacl),
            is_dir=True,
        )
        parent_text = render_icacls(parent_sd)
        _, parent_parsed = parse_icacls(parent_text)
        parent_buckets = writer_summary(
            classify_writers_from_aces(parent_parsed, parent_sd.owner)
        )
    return {
        "id": node.node_id,
        "role": node.role,
        "control": node.control,
        "win_path": node.sd.path,
        "source_rel": node.source_rel,
        "owner": node.sd.owner,
        "icacls_text": text,
        "parsed_path": path,
        "writers": writer_summary(buckets),
        "naive_broad_writable": naive_broad_writable(text),
        "parent_icacls_text": parent_text,
        "parent_writers": parent_buckets,
        "note": node.note,
    }


def main() -> int:
    engine = self_test()
    rows = [classify_node(n) for n in deployed_nodes()]
    census = packaging_census()
    protected = next(r for r in rows if r["control"] == "protected")
    user_owned = next(r for r in rows if r["control"] == "user-owned")
    trap = next(r for r in rows if r["control"] == "inherited-deny-trap")
    everyone = next(r for r in rows if r["control"] == "planted-everyone-write")
    pf_rows = [r for r in rows if r["id"].endswith("programfiles")]
    parse_ok = all(r["parsed_path"] == r["win_path"] for r in rows)
    protected_ok = (
        not protected["writers"]["has_broad_writer"]
        and not protected["writers"]["has_owner_writer"]
        and bool(protected["writers"]["SYSTEM"])
        and bool(protected["writers"]["administrators"])
    )
    user_ok = user_owned["writers"]["has_owner_writer"]
    trap_textual_broad = trap["writers"]["has_broad_writer"]
    everyone_broad = everyone["writers"]["has_broad_writer"]
    pf_no_broad = all(not r["writers"]["has_broad_writer"] for r in pf_rows)
    icacls_absent = census["icacls_binary"] is None
    live_windows = bool(census["live_windows"])

    ok = (
        engine["ok"]
        and parse_ok
        and protected_ok
        and user_ok
        and trap_textual_broad
        and everyone_broad
        and pf_no_broad
        and not census["installer_sets_acl"]
    )
    report = {
        "probe": "probe1-icacls-classify",
        "unit_id": UID,
        "pass": ok,
        "computed_not_asserted": True,
        "engine_self_test": engine,
        "live_windows": live_windows,
        "icacls_binary": census["icacls_binary"],
        "icacls_invoked": False,
        "acl_modified": False,
        "instrument": "icacls-text-parse-and-writer-classification",
        "packaging": {
            "files_scanned": census["files_scanned"],
            "installer_sets_acl": census["installer_sets_acl"],
            "packaging_mentions": census["packaging_mentions"],
            "mention_count": len(census["mentions"]),
        },
        "controls": {
            "protected_no_broad_writer": protected_ok,
            "user_owned_has_owner_writer": user_ok,
            "inherited_deny_trap_textual_broad": trap_textual_broad,
            "everyone_textual_broad": everyone_broad,
            "program_files_no_broad": pf_no_broad,
        },
        "rows": rows,
        "which_icacls": shutil.which("icacls"),
    }
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "probe", "unit_id", "pass", "live_windows", "icacls_binary",
        "icacls_invoked", "acl_modified", "packaging", "controls",
    )}, sort_keys=True))
    print(
        f"rows={len(rows)} parse_ok={parse_ok} protected_ok={protected_ok} "
        f"user_ok={user_ok} trap_textual_broad={trap_textual_broad} "
        f"installer_sets_acl={census['installer_sets_acl']}"
    )
    if ok:
        print("SUCCESS:ADV-0036-probe1 icacls-text classify writers; no ACL modified")
        return 0
    print("FAILED:ADV-0036-probe1 classification controls did not hold")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
