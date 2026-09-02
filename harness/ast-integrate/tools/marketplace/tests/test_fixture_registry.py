"""Marketplace fixture-registry suite (IMP-0118 catalog test).

Runs against the self-contained registry :func:`tools.marketplace.fixture.build`
materialises - never the live index, never the network.  Each test is a plain
function; :func:`all_tests` lists them in definition order so the IMP-0118 probe
can re-run them under :func:`tools.marketplace.hermetic.egress_blocked`, and
``python3 -B tools/marketplace/tests/test_fixture_registry.py`` runs the whole
suite and exits non-zero on the first failure.  Both-states tests plant a defect
(dangling blob, patched blob, lying feature label, tampered payload) in a scratch
copy and require the corresponding detector to fire.
"""
from __future__ import annotations

import inspect
import json
import shutil
import socket
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.marketplace.crypto import FIXTURE_KEY_ID, verify_signature  # noqa: E402
from tools.marketplace.features import DECLARED_FEATURES, coverage_matrix  # noqa: E402
from tools.marketplace.fixture import FIXTURE_REGISTRY_ID, build, load_payloads  # noqa: E402
from tools.marketplace.hermetic import BLOCK_MSG, egress_blocked, is_egress_blocked  # noqa: E402
from tools.marketplace.index_linter import lint_index, lint_registry  # noqa: E402
from tools.marketplace.storage import normalised, read_json, rebuild_index, registry_dir  # noqa: E402

#: Keys a ranking-neutral fixture must never carry (RES-0060 checks the same set).
POPULARITY_KEYS = frozenset({"download_count", "downloads", "downloadcount", "installs", "install_count"})


def _fresh_index() -> dict[str, Any]:
    build(REPO)
    return read_json(registry_dir(REPO) / "index.json")


def _nested_keys(doc: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(doc, dict):
        for key, value in doc.items():
            keys.add(str(key).lower())
            keys |= _nested_keys(value)
    elif isinstance(doc, list):
        for item in doc:
            keys |= _nested_keys(item)
    return keys


def _signature_status(index: dict[str, Any], payloads: dict[str, bytes]) -> dict[str, str]:
    return {
        entry["id"]: verify_signature(payloads[entry["id"]], entry.get("signature"))
        for entry in index["packages"]
    }


def _scratch_copy(td: str) -> tuple[Path, dict[str, Any]]:
    dest = Path(td) / "registry"
    shutil.copytree(registry_dir(REPO), dest)
    return dest, read_json(dest / "index.json")


def test_fixture_is_lint_clean() -> None:
    build(REPO)
    findings = lint_registry(REPO)
    assert findings == [], f"fixture registry is not lint-clean: {findings}"


def test_index_identity_and_publisher() -> None:
    index = _fresh_index()
    assert index["registry_id"] == FIXTURE_REGISTRY_ID
    assert index["publisher_key"]["key_id"] == FIXTURE_KEY_ID
    ids = [entry["id"] for entry in index["packages"]]
    assert len(ids) == len(set(ids)), "duplicate package ids"
    assert ids == sorted(ids), "packages must be sorted by id"
    assert len(ids) >= len(DECLARED_FEATURES), "fewer packages than declared features"
    overlap = _nested_keys(index) & POPULARITY_KEYS
    assert not overlap, f"fixture carries popularity keys {sorted(overlap)}"


def test_every_package_signature_verifies() -> None:
    index = _fresh_index()
    payloads = load_payloads(REPO)
    status = _signature_status(index, payloads)
    bad = {pid: st for pid, st in status.items() if st != "OK"}
    assert not bad, f"signatures failing verification: {bad}"
    victim = index["packages"][0]
    tampered = payloads[victim["id"]] + b"x"
    assert verify_signature(tampered, victim["signature"]) != "OK", "tampered payload still verifies"


def test_declared_features_all_covered() -> None:
    index = _fresh_index()
    payloads = load_payloads(REPO)
    matrix = coverage_matrix(index, payloads, _signature_status(index, payloads))
    assert matrix["missing"] == [], f"uncovered features: {matrix['missing']}"
    assert matrix["label_mismatches"] == [], json.dumps(matrix["label_mismatches"], indent=1)
    assert matrix["complete"] is True
    for feature in DECLARED_FEATURES:
        assert matrix["covered_by"][feature], f"{feature} has no covering package"
    assert matrix["covered_by"]["multi-version"] == ["hello-skill@1.0.0", "hello-skill@1.1.0"]


def test_coverage_detects_lying_label() -> None:
    index = _fresh_index()
    payloads = load_payloads(REPO)
    status = _signature_status(index, payloads)
    liar = json.loads(json.dumps(index))
    victim = next(entry for entry in liar["packages"] if entry["id"] == "hello-lib@1.0.0")
    victim["features"] = sorted(set(victim["features"]) | {"with-sbom"})
    matrix = coverage_matrix(liar, payloads, status)
    assert matrix["complete"] is False, "lying label went undetected"
    rows = [row for row in matrix["label_mismatches"] if row["id"] == "hello-lib@1.0.0"]
    assert rows and rows[0]["unbacked_labels"] == ["with-sbom"], matrix["label_mismatches"]
    assert coverage_matrix(index, payloads, status)["complete"] is True, "honest index flagged"


def test_index_rebuild_round_trip() -> None:
    index = build(REPO)
    rebuilt = rebuild_index(registry_dir(REPO))
    assert normalised(index) == normalised(rebuilt), "rebuilt index differs from built index"


def test_linter_fires_on_dangling_blob() -> None:
    build(REPO)
    with tempfile.TemporaryDirectory() as td:
        dest, index = _scratch_copy(td)
        victim = next(p for p in index["packages"] if p["id"] == "hello-skill@1.0.0")
        (dest / str(victim["blob"])).unlink()
        codes = {f["code"] for f in lint_index(dest, index)}
    assert "DANGLING_BLOB" in codes, f"dangling blob not reported: {sorted(codes)}"


def test_linter_fires_on_digest_mismatch() -> None:
    build(REPO)
    with tempfile.TemporaryDirectory() as td:
        dest, index = _scratch_copy(td)
        victim = next(p for p in index["packages"] if p["id"] == "hello-skill@1.1.0")
        blob = dest / str(victim["blob"])
        raw = blob.read_bytes()
        patched = raw.replace(b"Newer skill version", b"Never skill version", 1)
        assert patched != raw, "digest mutant did not change the blob"
        blob.write_bytes(patched)
        codes = {f["code"] for f in lint_index(dest, index)}
    assert "DIGEST_MISMATCH" in codes, f"digest mismatch not reported: {sorted(codes)}"


def test_placeholder() -> None:
    """The suite inventory is complete: every test_* function is listed, lint test included."""
    listed = [name for name, _fn in all_tests()]
    defined = sorted(
        name
        for name, obj in globals().items()
        if name.startswith("test_") and inspect.isfunction(obj) and obj.__module__ == __name__
    )
    assert sorted(listed) == defined, f"all_tests() drifted: {listed} vs {defined}"
    assert "test_fixture_is_lint_clean" in listed


def test_suite_passes_with_egress_blocked() -> None:
    """Every other test passes with egress refused, and the refusal is live (both states)."""
    with egress_blocked() as block:
        assert is_egress_blocked()
        for name, fn in all_tests():
            if name != "test_suite_passes_with_egress_blocked":
                fn()
        try:
            socket.create_connection(("192.0.2.1", 80), timeout=1)
        except OSError as exc:
            assert BLOCK_MSG in str(exc), f"blocker raised without marker: {exc}"
        else:
            raise AssertionError("egress blocker is not live: connection attempt was not refused")
        assert block.attempts and block.attempts[-1]["api"] == "create_connection"
    assert not is_egress_blocked(), "egress block did not lift on exit"


def all_tests() -> list[tuple[str, Callable[[], None]]]:
    """Every ``test_*`` function in this module, in definition order."""
    found = [
        (name, obj)
        for name, obj in globals().items()
        if name.startswith("test_") and inspect.isfunction(obj) and obj.__module__ == __name__
    ]
    found.sort(key=lambda item: inspect.getsourcelines(item[1])[1])
    return found


def main(argv: list[str] | None = None) -> int:
    selected = set(argv or [])
    failures = 0
    ran = 0
    for name, fn in all_tests():
        if selected and name not in selected:
            continue
        ran += 1
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - reported below, exit code carries it
            failures += 1
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
        else:
            print(f"PASS {name}")
    print(f"{ran - failures}/{ran} passed")
    if failures or ran == 0:
        print("FAILED:test_fixture_registry")
        return 1
    print("SUCCESS:test_fixture_registry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
