#!/usr/bin/env python3
"""Probe 2 (reviewer): incomplete changelog is surfaced; widening without consent writes nothing.

Independent of probe1: fresh packages, no shared preview object.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from marketplace.package import make_package  # noqa: E402
from marketplace.update import (  # noqa: E402
    PreviewFidelityError,
    UpdateAborted,
    apply_update,
    assert_preview_matches_actual,
    census_tree,
    preview_update,
    underreported_preview,
    write_package_tree,
)
from plugin.permission_diff import Consent, MemoryConsentStore  # noqa: E402

PKG = "hello-skill"
RELEASES = ["1.0.0", "1.1.0", "1.2.0"]


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0087-probe2 {msg}")
    return 1


def main() -> int:
    installed = make_package(
        PKG,
        "1.0.0",
        extra_files={"skills/SKILL.md": b"# v1\n"},
        permissions=["fs:read:/pkg"],
        releases=RELEASES,
        changelog={"1.0.0": ["initial"]},
    )
    # Reviewer-constructed: changelog deliberately omits 1.1.0
    incomplete = make_package(
        PKG,
        "1.2.0",
        extra_files={"skills/SKILL.md": b"# v12\n", "docs/n.md": b"n\n"},
        permissions=["fs:read:/pkg"],  # not widening, so apply can proceed
        releases=RELEASES,
        changelog={"1.2.0": ["docs"]},  # 1.1.0 missing
    )
    preview_gap = preview_update(installed, incomplete)
    if preview_gap.changelog["gaps"] != ["1.1.0"]:
        return fail(f"gap not surfaced: {preview_gap.changelog}")
    if "1.1.0" not in preview_gap.changelog["expected_versions"]:
        return fail("intermediate version silently dropped from expected_versions")
    gap_row = next(
        e for e in preview_gap.changelog["entries"] if e["version"] == "1.1.0"
    )
    if not gap_row["gap"]:
        return fail("gap row not marked")

    # Widening without consent: dest must be byte-identical
    widening = make_package(
        PKG,
        "1.2.0",
        extra_files={"skills/SKILL.md": b"# v12\n"},
        permissions=["fs:read:/pkg", "net:connect:*"],
        releases=RELEASES,
        changelog={"1.1.0": ["fix"], "1.2.0": ["net"]},
    )
    preview_wide = preview_update(installed, widening)
    if preview_wide.permission_diff["verdict"] != "widen":
        return fail("expected widen")

    with tempfile.TemporaryDirectory() as td:
        dest = Path(td) / "pkg"
        write_package_tree(dest, installed)
        before = census_tree(dest)
        aborted = False
        try:
            apply_update(dest, installed, widening, consent_store=None)
        except UpdateAborted as exc:
            aborted = True
            if exc.reason != "permission-widening-requires-consent":
                return fail(f"reason={exc.reason}")
        if not aborted:
            return fail("widening without consent did not abort")
        if census_tree(dest) != before:
            return fail("abort wrote bytes")

        # Under-report mutant must fail fidelity after a successful non-widen apply
        apply_update(dest, installed, incomplete, consent_store=None, preview=preview_gap)
        assert_preview_matches_actual(preview_gap, dest)
        mutant_fired = False
        drop = "docs/n.md"
        try:
            assert_preview_matches_actual(underreported_preview(preview_gap, drop), dest)
        except PreviewFidelityError:
            mutant_fired = True
        if not mutant_fired:
            return fail("under-report mutant silent")

        # Wrong-version consent is not blanket
        store = MemoryConsentStore()
        store.persist(
            Consent(
                package_id=PKG,
                from_version="1.0.0",
                to_version="1.1.0",
                widened=("net:connect:*",),
            )
        )
        dest2 = Path(td) / "pkg2"
        write_package_tree(dest2, installed)
        before2 = census_tree(dest2)
        try:
            apply_update(dest2, installed, widening, consent_store=store)
            return fail("wrong-version consent authorized widen")
        except UpdateAborted:
            pass
        if census_tree(dest2) != before2:
            return fail("wrong-version consent path wrote bytes")

    report = {
        "probe": "probe2-negative-controls",
        "unit_id": "IMP-0087",
        "pass": True,
        "changelog_gap_surfaced": preview_gap.changelog["gaps"] == ["1.1.0"],
        "intermediate_not_dropped": "1.1.0" in preview_gap.changelog["expected_versions"],
        "widening_without_consent_aborted": True,
        "abort_wrote_nothing": True,
        "underreport_mutant_fired": True,
        "wrong_version_consent_rejected": True,
        "reviewer_id": "IMP-0087-probe2-incomplete-changelog",
    }
    print(json.dumps(report, sort_keys=True))
    print(
        "SUCCESS:IMP-0087-probe2 changelog gap surfaced; widening without consent writes nothing"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
