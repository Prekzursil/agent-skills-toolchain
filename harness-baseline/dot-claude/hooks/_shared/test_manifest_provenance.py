#!/usr/bin/env python3
"""G-10 regression tests for strict hook-manifest provenance placement.

This directory's suites are standalone scripts, so run this file directly rather
than relying on pytest discovery:

    python hooks/_shared/test_manifest_provenance.py

Each behavioral test documents its known-broken pre-change state. The control first
proves that the detector can see and parse both known-present manifests; an empty
search result is never accepted as evidence.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
CONTRIBUTOR_CONTRACT = REPO_ROOT / "AGENTS.md"
PROVENANCE_SIDECAR = REPO_ROOT / ".provenance" / "hooks" / "hooks.json.md"
QUALITY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "quality.yml"
KNOWN_BROKEN_MANIFEST = (
    REPO_ROOT / "hooks" / "_fleet-backups" / "20260713-WU-A" / "hooks.json.before"
)
HOOK_MANIFESTS = (
    REPO_ROOT / "hooks" / "hooks.json",
    REPO_ROOT / "agent-self" / "config" / "hooks" / "hooks.json",
)
EXPECTED_TOP_LEVEL_KEYS = {"description", "hooks"}
POLICY_MARKER = (
    "store provenance in `.provenance/<repo-relative-manifest-path>.md` instead"
)
WORKFLOW_MARKER = "python hooks/_shared/test_manifest_provenance.py"


def _load_json_object(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict), f"{path} must contain a JSON object"
    return document


def test_control_finds_known_present_manifests() -> None:
    """Calibration control: observe clean targets and reject the real before-image."""
    for manifest in HOOK_MANIFESTS:
        assert manifest.is_file(), f"known-present manifest not found: {manifest}"
        _load_json_object(manifest)
    assert KNOWN_BROKEN_MANIFEST.is_file(), (
        f"known-broken manifest not found: {KNOWN_BROKEN_MANIFEST}"
    )
    broken_keys = set(_load_json_object(KNOWN_BROKEN_MANIFEST))
    assert broken_keys != EXPECTED_TOP_LEVEL_KEYS
    assert "$schema" in broken_keys


def test_forward_rule_is_in_the_contributor_contract() -> None:
    """Known-broken pre-change state: AGENTS.md has no sidecar placement rule."""
    contract = CONTRIBUTOR_CONTRACT.read_text(encoding="utf-8")
    assert POLICY_MARKER in contract, (
        "AGENTS.md must route strict-manifest provenance to .provenance sidecars"
    )


def test_hook_manifest_provenance_uses_the_reserved_sidecar() -> None:
    """Known-broken pre-change state: the required .provenance sidecar is absent."""
    assert PROVENANCE_SIDECAR.is_file(), (
        f"hook-manifest provenance must live at {PROVENANCE_SIDECAR}"
    )
    sidecar = PROVENANCE_SIDECAR.read_text(encoding="utf-8")
    for manifest in HOOK_MANIFESTS:
        relative = manifest.relative_to(REPO_ROOT).as_posix()
        assert f"`{relative}`" in sidecar, (
            f"sidecar must identify its governed manifest: {relative}"
        )


def test_quality_workflow_invokes_this_standalone_suite() -> None:
    """Known-broken pre-change state: no CI workflow invokes this suite."""
    workflow = QUALITY_WORKFLOW.read_text(encoding="utf-8")
    assert WORKFLOW_MARKER in workflow, (
        "quality.yml must invoke the standalone G-10 suite by its explicit path"
    )


def test_provenance_adds_no_hook_manifest_keys() -> None:
    """Known-broken pre-change state: no sidecar exists to carry this invariant."""
    assert PROVENANCE_SIDECAR.is_file(), "provenance policy is not activated"
    for manifest in HOOK_MANIFESTS:
        keys = set(_load_json_object(manifest))
        assert keys == EXPECTED_TOP_LEVEL_KEYS, (
            f"{manifest} top-level keys changed: expected "
            f"{sorted(EXPECTED_TOP_LEVEL_KEYS)}, got {sorted(keys)}; put provenance "
            "under .provenance instead"
        )


TESTS: tuple[Callable[[], None], ...] = (
    test_control_finds_known_present_manifests,
    test_forward_rule_is_in_the_contributor_contract,
    test_hook_manifest_provenance_uses_the_reserved_sidecar,
    test_quality_workflow_invokes_this_standalone_suite,
    test_provenance_adds_no_hook_manifest_keys,
)


def main() -> int:
    failures: list[str] = []
    for test in TESTS:
        try:
            test()
        except Exception as exc:
            failures.append(test.__name__)
            print(f"FAIL {test.__name__}: {exc}")
        else:
            print(f"PASS {test.__name__}")

    print(f"\n{len(TESTS) - len(failures)} passed, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
