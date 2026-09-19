#!/usr/bin/env python3
"""Produce and verify the dedicated completion-condition-11 unit manifest.

The charter manifest intentionally contains only contracted program files.  Unit
outputs therefore need a separately derived registration index (owner decision,
command-center/p2-next/OWNER-DECISION-condition-11.md, Option B).

CLOSED REGISTRATION CONTRACT (v2, 2026-09-19).  The derivation set is every
receipt-shaped JSON under command-center/ whose
``manifest_registration.manifest_path`` names THIS file.  A receipt that points
at a probe-local ``p2-wave/probes/<unit>/UNIT-ARTIFACT-MANIFEST.json`` is a
different, self-contained contract and is ignored here.  The v1 derivation
(all receipts under receipts/adversarial/audit) could never produce a file: it
failed closed on the first of ~90 receipts naming probe outputs that were never
committed, so the manifest could not be written at all -- a producer that cannot
run is indistinguishable from no producer (measured 2026-09-19,
command-center/p2-next/C11-MISSING-ARTIFACTS.json).

FAIL-CLOSED RULES.  Discovery or verification aborts (exit 1, FAILED marker) on:
  * zero receipts declaring this manifest (empty walk);
  * an unreadable/unparseable declaring receipt;
  * a receipt whose manifest_registration.registered is TRUE naming an absent
    artifact -- a claimed registration that cannot be honored is the exact
    false-green this program exists to prevent, so it is fatal, not skippable;
  * zero registrable claimers while claimers exist (the manifest would be an
    empty shell over its own contract);
  * an unreadable artifact file.
A DECLARING receipt with registered != true that names absent artifacts is NOT
silently skipped: it is recorded in ``unregistrable_claimers`` with its missing
paths, so the manifest is green only by disclosing what it could not register.
Deleting such an artifact still turns --check red via drift, and flipping the
receipt to registered=true turns --write red via the fatal rule.

Digests are sha256 over CRLF-to-LF-normalized bytes, matching what
completion_predicate._c11_manifest compares.  Output carries no timestamps so
--check is a stable byte comparison.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_REL = "command-center/UNIT-ARTIFACT-MANIFEST.json"

#: Files never ingested as receipts, whatever their content.
_SELF_NAMES = {"ARTIFACT-MANIFEST.json", "UNIT-ARTIFACT-MANIFEST.json"}


class ManifestError(RuntimeError):
    """Discovery or verification failed closed."""


def _is_scratch(path: Path, root: Path) -> bool:
    """Underscore-prefixed trees are probe output, not the receipt corpus.

    Measured 2026-09-19: without this call, receipt-validate self-test mutants
    written to command-center/p2-wave/_r2_tmp/ leak into the contract the moment
    the golden they copy declares this manifest.
    """
    return any(part.startswith("_") for part in path.relative_to(root).parts)


def _declaring_receipts(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    """Every receipt-shaped JSON under command-center/ that declares THIS manifest."""
    corpus = root / "command-center"
    if not corpus.is_dir():
        raise ManifestError(f"no command-center/ directory under {root}")
    found: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(corpus.rglob("*.json")):
        if path.name in _SELF_NAMES or _is_scratch(path, root):
            continue
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ManifestError(f"unreadable JSON {path}: {exc}") from exc
        if b"manifest_registration" not in raw:
            continue  # cheap prefilter; non-declaring files are the overwhelming case
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            # Only a DECLARING receipt must parse; but the block above matched the
            # key string, so a parse failure here means a receipt claiming this
            # manifest is broken -- fail closed rather than skip.
            raise ManifestError(f"unparseable JSON {path}: {exc}") from exc
        if not isinstance(value, dict):
            continue
        reg = value.get("manifest_registration")
        if not isinstance(reg, dict) or reg.get("manifest_path") != MANIFEST_REL:
            continue
        unit_id = value.get("unit_id")
        artifacts = value.get("artifacts")
        if not (
            isinstance(unit_id, str)
            and unit_id.strip()
            and isinstance(artifacts, list)
            and artifacts
        ):
            continue
        found.append((path, value))
    if not found:
        raise ManifestError(
            "discovered ZERO receipts declaring " + MANIFEST_REL + " (empty walk)"
        )
    return found


def derive(root: Path) -> dict[str, Any]:
    """Derive the manifest entirely from receipt claims and filesystem bytes."""
    rows: list[dict[str, Any]] = []
    unregistrable: list[dict[str, Any]] = []
    declaring = _declaring_receipts(root)
    for receipt_path, receipt in declaring:
        receipt_rel = receipt_path.relative_to(root).as_posix()
        reg = receipt.get("manifest_registration") or {}
        claimed = reg.get("registered") is True
        missing: list[str] = []
        for artifact in receipt["artifacts"]:
            if not isinstance(artifact, dict) or not isinstance(
                artifact.get("path"), str
            ):
                raise ManifestError(f"malformed artifact in {receipt_rel}")
            rel = artifact["path"].replace("\\", "/")
            target = root / rel
            if not target.is_file():
                missing.append(rel)
                continue
            try:
                raw = target.read_bytes()
            except OSError as exc:
                raise ManifestError(f"artifact unreadable {target}: {exc}") from exc
            normalized = raw.replace(b"\r\n", b"\n")
            rows.append(
                {
                    "path": rel,
                    "sha256": hashlib.sha256(normalized).hexdigest(),
                    "bytes": len(normalized),
                    "present": True,
                    "unit_id": receipt["unit_id"],
                    "receipt_path": receipt_rel,
                    "receipt_registered": claimed,
                }
            )
        if missing:
            if claimed:
                # A registration this receipt CLAIMS cannot be honored: fatal.
                raise ManifestError(
                    f"receipt {receipt_rel} claims registered=true but names absent "
                    f"artifact(s): {', '.join(missing[:5])}"
                )
            unregistrable.append(
                {
                    "receipt_path": receipt_rel,
                    "unit_id": receipt["unit_id"],
                    "missing": missing,
                }
            )
    if not rows:
        raise ManifestError(
            "zero registrable claimers: every receipt declaring "
            + MANIFEST_REL
            + " names absent artifacts"
        )
    rows.sort(key=lambda row: (row["path"], row["receipt_path"], row["unit_id"]))
    unregistrable.sort(key=lambda row: row["receipt_path"])
    return {
        "schema_version": 2,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "selection": (
            "every receipt-shaped JSON under command-center/ whose "
            "manifest_registration.manifest_path == this file; probe-local "
            "UNIT-ARTIFACT-MANIFEST.json files are separate contracts and are "
            "not aggregated here; underscore-prefixed scratch trees excluded"
        ),
        "derivation": "tools/command-center/unit_manifest.py --write",
        "verified_on_disk": True,
        "expected_claimers": len(declaring),
        "registered_artifacts": len(rows),
        "unregistrable_claimers": len(unregistrable),
        "artifacts": rows,
        "unregistrable": unregistrable,
    }


def _encoded(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, ensure_ascii=True) + "\n"


def write(root: Path) -> int:
    try:
        value = derive(root)
        path = root / MANIFEST_REL
        path.write_text(_encoded(value), encoding="utf-8", newline="\n")
    except (ManifestError, OSError) as exc:
        print(f"FAILED:unit-manifest {exc}")
        return 1
    print(
        f"SUCCESS:unit-manifest registered {value['registered_artifacts']} artifact "
        f"row(s) from {value['expected_claimers']} claimer(s); "
        f"unregistrable_claimers={value['unregistrable_claimers']} -> {MANIFEST_REL}"
    )
    return 0


def check(root: Path) -> int:
    try:
        expected = _encoded(derive(root))
        actual = (root / MANIFEST_REL).read_text(encoding="utf-8")
    except (ManifestError, OSError, UnicodeDecodeError) as exc:
        print(f"FAILED:unit-manifest {exc}")
        return 1
    if actual != expected:
        print(f"FAILED:unit-manifest drift in {MANIFEST_REL}")
        return 1
    print(
        f"SUCCESS:unit-manifest {MANIFEST_REL} matches derived claimer corpus "
        "(closed registration contract)"
    )
    return 0


def _claim(root: Path, name: str, registered: bool, artifacts: list[str]) -> Path:
    """Write one declaring receipt; returns its path."""
    rel = f"command-center/receipts/{name}.json"
    receipt = {
        "unit_id": name,
        "state": "BLOCKED",
        "artifacts": [{"path": p} for p in artifacts],
        "manifest_registration": {
            "registered": registered,
            "manifest_path": MANIFEST_REL,
        },
    }
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return path


def _other_manifest_receipt(root: Path, name: str, absent: str) -> Path:
    """A receipt declaring a DIFFERENT manifest (contract closure control)."""
    rel = f"command-center/receipts/{name}.json"
    receipt = {
        "unit_id": name,
        "state": "BLOCKED",
        "artifacts": [{"path": absent}],
        "manifest_registration": {
            "registered": True,
            "manifest_path": f"command-center/p2-wave/probes/{name}/UNIT-ARTIFACT-MANIFEST.json",
        },
    }
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return path


def self_test() -> int:
    """Both-states controls: every fatal rule must FIRE somewhere and stay
    SILENT where it should, or the producer is indistinguishable from a no-op."""
    hexdigits = set("0123456789abcdef")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        art1 = root / "out1.txt"
        art1.write_bytes(b"known-good\r\n")
        art2 = root / "out2.txt"
        art2.write_bytes(b"second artifact\n")
        _claim(root, "TST-A", True, ["out1.txt", "out2.txt"])
        _claim(root, "TST-B", False, ["out1.txt"])
        _other_manifest_receipt(root, "TST-OTHER", "never-committed.txt")
        # T1 clean write: both artifacts hashed, digests are hex.
        if write(root) != 0:
            print("FAILED:unit-manifest-self-test T1 clean write not green")
            return 1
        written = json.loads((root / MANIFEST_REL).read_text(encoding="utf-8"))
        if written["registered_artifacts"] != 3 or written["expected_claimers"] != 2:
            print(
                "FAILED:unit-manifest-self-test T1 counts "
                f"registered={written['registered']} claimers={written['expected_claimers']}"
            )
            return 1
        for row in written["artifacts"]:
            digest = row.get("sha256")
            if not (
                isinstance(digest, str)
                and len(digest) == 64
                and all(c in hexdigits for c in digest)
            ):
                print("FAILED:unit-manifest-self-test T1 non-hex sha256 emitted")
                return 1
        if any("TST-OTHER" in r["unit_id"] for r in written["artifacts"]):
            print("FAILED:unit-manifest-self-test T1 other-manifest receipt leaked in")
            return 1
        # T2 known-bad manifest bytes -> check must go red; rewrite -> green.
        bad = written
        bad["artifacts"][0]["sha256"] = "0" * 64
        (root / MANIFEST_REL).write_text(_encoded(bad), encoding="utf-8", newline="\n")
        if check(root) != 1:
            print("FAILED:unit-manifest-self-test T2 known-bad manifest stayed green")
            return 1
        if write(root) != 0 or check(root) != 0:
            print("FAILED:unit-manifest-self-test T2 clean control did not go green")
            return 1
        # T3 REGISTERED claimer names an absent artifact -> write AND check FATAL.
        _claim(root, "TST-GHOST", True, ["never-committed.txt"])
        if write(root) != 1:
            print("FAILED:unit-manifest-self-test T3 registered ghost stayed green")
            return 1
        if check(root) != 1:
            print("FAILED:unit-manifest-self-test T3 registered ghost check green")
            return 1
        # T4 same ghost, registered=false -> disclosed as unregistrable, NOT fatal,
        #    and the disclosure flips the manifest content (drift-visible).
        ghost_rel = root / "command-center/receipts/TST-GHOST.json"
        ghost = json.loads(ghost_rel.read_text(encoding="utf-8"))
        ghost["manifest_registration"]["registered"] = False
        ghost_rel.write_text(json.dumps(ghost, indent=2), encoding="utf-8")
        if check(root) != 1:
            print("FAILED:unit-manifest-self-test T4 unregistrable change not drift")
            return 1
        if write(root) != 0:
            print("FAILED:unit-manifest-self-test T4 disclosed ghost aborted write")
            return 1
        written = json.loads((root / MANIFEST_REL).read_text(encoding="utf-8"))
        if written["unregistrable_claimers"] != 1 or not written["unregistrable"]:
            print("FAILED:unit-manifest-self-test T4 unregistrable not disclosed")
            return 1
        if written["unregistrable"][0]["missing"] != ["never-committed.txt"]:
            print("FAILED:unit-manifest-self-test T4 missing path not recorded")
            return 1
        if check(root) != 0:
            print("FAILED:unit-manifest-self-test T4 post-write check not green")
            return 1
    with tempfile.TemporaryDirectory() as tmp:
        # T5 empty walk: nothing declares this manifest -> fail closed. The
        # claiming receipt inside the _scratch tree must be IGNORED, so the
        # failure must be the empty-walk message, not the registered-ghost
        # fatal rule -- those are different reds, and only one is correct here.
        root = Path(tmp)
        (root / "command-center" / "receipts").mkdir(parents=True)
        (root / "command-center" / "receipts" / "stray.json").write_text(
            json.dumps({"unit_id": "TST-STRAY", "artifacts": []}), encoding="utf-8"
        )
        scratch_dir = root / "command-center" / "p2-wave" / "_r2_tmp"
        scratch_dir.mkdir(parents=True)
        (scratch_dir / "selftest-mutant.json").write_text(
            json.dumps(
                {
                    "unit_id": "TST-0334",
                    "state": "SUCCESS",
                    "artifacts": [{"path": "never-committed.txt"}],
                    "manifest_registration": {
                        "registered": True,
                        "manifest_path": MANIFEST_REL,
                    },
                }
            ),
            encoding="utf-8",
        )
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc_w = write(root)
        msg = buf.getvalue()
        if rc_w != 1 or check(root) != 1:
            print("FAILED:unit-manifest-self-test T5 empty walk did not fail closed")
            return 1
        if "ZERO receipts declaring" not in msg:
            print(
                "FAILED:unit-manifest-self-test T5 scratch claimer leaked "
                f"(message was: {msg.strip()[:120]})"
            )
            return 1
    with tempfile.TemporaryDirectory() as tmp:
        # T6 zero registrable: the only claimer is a disclosed ghost -> the
        #    manifest would be an empty shell, so write is fatal.
        root = Path(tmp)
        art = root / "present.txt"
        art.write_bytes(b"present\n")
        _claim(root, "TST-OK", False, ["present.txt"])
        _claim(root, "TST-ALLGHOST", False, ["missing-1.txt"])
        # one registrable claimer exists (TST-OK), so green; now remove it
        if write(root) != 0:
            print("FAILED:unit-manifest-self-test T6 setup not green")
            return 1
        (root / "command-center/receipts/TST-OK.json").unlink()
        if write(root) != 1:
            print("FAILED:unit-manifest-self-test T6 zero-registrable stayed green")
            return 1
    print(
        "SUCCESS:unit-manifest-self-test green on clean, red on drift, fatal on "
        "registered-ghost, disclosed on unregistered-ghost, closed on empty walk, "
        "closed on zero-registrable, ignored other-manifest receipts"
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="unit_manifest")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--self-test", action="store_true")
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    ns = parser.parse_args(argv)
    if ns.self_test:
        return self_test()
    return write(ns.root) if ns.write else check(ns.root)


if __name__ == "__main__":
    raise SystemExit(main())
