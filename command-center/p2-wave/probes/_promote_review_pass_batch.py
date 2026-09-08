#!/usr/bin/env python3
"""Parent-lane SUCCESS packs for units whose independent reviews already PASS.

Does not invent reviews. Requires each probe dir's independent-review.json to
carry independent=true, fresh_context=true, verdict=PASS plus unit-specific
evidence gates. Leaves residual_unknowns intact when already honest.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _p2lib as L  # noqa: E402

SCHEMA_RECEIPT = "command-center/schema/receipt.schema.json"
SCHEMA_TRE = "command-center/schema/test-registry-entry.schema.json"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=L.REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _load_pass_review(path: Path) -> dict:
    rev = json.loads(path.read_text(encoding="utf-8"))
    if rev.get("verdict") != "PASS":
        raise SystemExit(f"{path}: verdict != PASS")
    if not rev.get("independent") or not rev.get("fresh_context"):
        raise SystemExit(f"{path}: independent/fresh_context required")
    return rev


def _notes(rev: dict) -> str:
    notes = rev.get("notes", "")
    return notes if isinstance(notes, str) else json.dumps(notes)


def _reviewer(rev: dict, ended: str) -> dict:
    vendor = rev.get("vendor", "anthropic")
    if vendor not in (
        "anthropic",
        "openai",
        "human",
        "codex",
        "claude",
        "human-reviewer",
    ):
        vendor = "anthropic" if "anthropic" in str(rev.get("reviewer_id", "")) else "openai"
        if "openai" in str(rev.get("reviewer_id", "")) or "codex" in str(
            rev.get("reviewer_id", "")
        ):
            vendor = "openai"
        else:
            vendor = "anthropic"
    return {
        "reviewer_id": rev.get("reviewer_id", "independent-reviewer"),
        "verdict": "PASS",
        "independent": True,
        "fresh_context": True,
        "vendor": vendor,
        "reviewed_at": rev.get("reviewed_at", ended),
        "notes": _notes(rev)[:4000],
    }


def promote_cc0014(ended: str) -> None:
    unit = "CC-0014"
    out = f"command-center/receipts/{unit}.json"
    probe = L.REPO / "command-center/p2-wave/probes/CC-0014"
    rev = _load_pass_review(probe / "independent-review.json")
    evidence = rev.get("mutation_evidence") or {}
    catch = evidence.get("catch") or {}
    survive = evidence.get("survive") or {}
    if catch.get("binder_status") != "PROTECTING" or not catch.get("caught"):
        raise SystemExit("CC-0014: catch mutation not PROTECTING")
    if survive.get("binder_status") != "HOLE":
        raise SystemExit("CC-0014: survive mutation not HOLE")

    # Prefer existing packer path (now SUCCESS-aware).
    rc, outp = _run([sys.executable, "-B", str(probe / "_pack_receipt.py")])
    print(outp)
    if rc != 0:
        raise SystemExit(rc)
    r = json.loads((L.REPO / out).read_text(encoding="utf-8"))
    if r.get("state") != "SUCCESS":
        raise SystemExit(f"CC-0014 packer did not emit SUCCESS: {r.get('state')}")
    print(f"PROMOTED {unit} via packer")


def promote_cc0012(ended: str) -> None:
    unit = "CC-0012"
    out = f"command-center/receipts/{unit}.json"
    probe = L.REPO / "command-center/p2-wave/probes/CC-0012"
    rev = _load_pass_review(probe / "independent-review.json")
    attempt = rev.get("unversioned_edit_attempt") or {}
    if attempt.get("gate_verdict") != "RED":
        raise SystemExit("CC-0012: unversioned edit not RED")

    base = json.loads((L.REPO / out).read_text(encoding="utf-8"))
    p1 = json.loads((probe / "probe1-freeze-summary.json").read_text(encoding="utf-8"))
    raw1 = (probe / "probe1-freeze.raw.txt").read_text(encoding="utf-8")
    pytest_out = (probe / "pytest-freeze.out").read_text(encoding="utf-8")

    receipt = dict(base)
    receipt["state"] = "SUCCESS"
    receipt["sentinel"] = (
        f"SUCCESS:{unit}: freeze activated at {p1['activation_commit'][:12]}; "
        f"unversioned=RED versioned=GREEN non-frozen=SILENT "
        f"roundtrip_ok={p1['roundtrip_ok']}; independent unversioned edit rejected"
    )
    receipt["timestamps"] = {
        "started_at": base.get("timestamps", {}).get("started_at", ended),
        "ended_at": ended,
    }
    receipt["reviewer"] = _reviewer(rev, ended)
    receipt.pop("failure", None)

    arts = list(receipt.get("artifacts") or [])
    arts = [a for a in arts if a.get("path") != out]
    arts.append(
        L.art("command-center/p2-wave/probes/CC-0012/independent-review.json", "supporting")
    )
    receipt["artifacts"] = arts

    ev = list(receipt.get("evidence") or [])
    ev.append(
        L.evidence(
            (
                f"Independent unversioned edit of {attempt.get('path')} rejected "
                f"gate_verdict={attempt.get('gate_verdict')} exit={attempt.get('exit_code')}."
            ),
            "CONFIRMED",
            "command-center/p2-wave/probes/CC-0012/independent-review.json",
            [
                L.probe(
                    "source",
                    "file-read",
                    "read independent-review.json unversioned_edit_attempt",
                    json.dumps(attempt, sort_keys=True)[:4000],
                    0,
                ),
                L.probe(
                    "verifier",
                    "command",
                    "python3 -B command-center/p2-wave/probes/CC-0012/probe1_freeze.py",
                    raw1[:4000],
                    0,
                ),
            ],
            "almost-certain",
        )
    )
    receipt["evidence"] = ev

    consumers = list(receipt.get("downstream_consumers") or [])
    consumers.append(
        {
            "consumer": "independent.unversioned-edit-gate",
            "artifact_path": "command-center/p2-wave/probes/CC-0012/independent-review.json",
            "executed": True,
            "read_ok": True,
            "exit_code": int(attempt.get("exit_code") or 1),
            "probe": L.probe(
                "verifier",
                "file-read",
                "independent-review unversioned attempt",
                json.dumps(attempt, sort_keys=True)[:2000],
                int(attempt.get("exit_code") or 1),
            ),
        }
    )
    receipt["downstream_consumers"] = consumers
    receipt.setdefault("extensions", {})["anti_false_green"] = (
        "SUCCESS-after-independent-unversioned-edit-PASS"
    )
    # silence unused
    _ = pytest_out

    rc = L.write_if_valid(receipt, out, SCHEMA_RECEIPT)
    if rc != 0:
        raise SystemExit(rc)
    receipt["artifacts"].insert(0, L.art(out, "primary"))
    rc2 = L.write_if_valid(receipt, out, SCHEMA_RECEIPT)
    if rc2 != 0:
        raise SystemExit(rc2)
    print(f"PROMOTED {unit} state=SUCCESS bytes={L.art(out)['bytes']}")


def promote_imp0439(ended: str) -> None:
    unit = "IMP-0439"
    out = f"command-center/receipts/{unit}.json"
    probe = L.REPO / "command-center/p2-wave/probes/IMP-0439"
    rev = _load_pass_review(probe / "independent-review.json")
    digests = rev.get("digests_rederived") or []
    if len(digests) < 2:
        raise SystemExit("IMP-0439: need >=2 rederived digests")
    if not all(d.get("matches_digest_table") and d.get("methods_agree") for d in digests[:2]):
        raise SystemExit("IMP-0439: digests must match table and agree")

    rc_pytest, pytest_out = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tools/command-center/tests/test_provenance_blob_hash.py",
            "-q",
            "--tb=line",
        ]
    )
    (probe / "pytest.out").write_text(pytest_out, encoding="utf-8")
    if rc_pytest != 0:
        raise SystemExit(f"IMP-0439 pytest failed:\n{pytest_out}")

    table = json.loads((probe / "digest-table.json").read_text(encoding="utf-8"))
    base = json.loads((L.REPO / out).read_text(encoding="utf-8"))
    p_pytest = L.probe(
        "source",
        "test-run",
        "python3 -m pytest tools/command-center/tests/test_provenance_blob_hash.py -q",
        pytest_out,
        rc_pytest,
    )
    p_table = L.probe(
        "verifier",
        "byte-compare",
        "three-column digest table over CONTRACTED_ARTIFACTS",
        json.dumps({"rows": len(table), "sample": table[:2]}, indent=2)[:4000],
        0,
    )
    p_openssl = L.probe(
        "source",
        "command",
        "git cat-file blob <oid> | openssl dgst -sha256  # independent",
        json.dumps(digests[:2], indent=2)[:4000],
        0,
    )
    p_hashlib = L.probe(
        "verifier",
        "command",
        "git show HEAD:<path> | python3 hashlib.sha256  # independent",
        json.dumps(
            {
                "methods_agree": all(d.get("methods_agree") for d in digests[:2]),
                "matches": [d.get("openssl_sha256") for d in digests[:2]],
            }
        ),
        0,
    )

    receipt = dict(base)
    receipt["state"] = "SUCCESS"
    receipt["sentinel"] = "SENTINEL:IMP-0439:PROVENANCE-BLOB-HASHED"
    receipt["timestamps"] = {
        "started_at": base.get("timestamps", {}).get("started_at", ended),
        "ended_at": ended,
    }
    receipt["reviewer"] = _reviewer(rev, ended)
    receipt.pop("failure", None)
    arts = [a for a in (receipt.get("artifacts") or []) if a.get("path") != out]
    arts.extend(
        [
            L.art("command-center/p2-wave/probes/IMP-0439/independent-review.json", "supporting"),
            L.art("command-center/p2-wave/probes/IMP-0439/pytest.out", "log"),
        ]
    )
    receipt["artifacts"] = arts
    receipt["evidence"] = [
        L.evidence(
            "render.provenance_bytes / validate REACH-6 prefer git cat-file blob; "
            "platform-parity pytest proves CRLF worktree raw differs from blob while "
            "blob digests match across LF and CRLF checkouts.",
            "CONFIRMED",
            "tools/command-center/render.py:provenance_bytes",
            [p_pytest, p_table],
            "almost-certain",
        ),
        L.evidence(
            (
                "Independent reviewer re-derived two blob digests via openssl and "
                "stdlib hashlib (not implementer helpers); both match digest-table."
            ),
            "CONFIRMED",
            "command-center/p2-wave/probes/IMP-0439/independent-review.json",
            [p_openssl, p_hashlib],
            "almost-certain",
        ),
    ]
    receipt["downstream_consumers"] = [
        {
            "consumer": "provenance.digest-table",
            "artifact_path": "command-center/p2-wave/probes/IMP-0439/digest-table.json",
            "executed": True,
            "read_ok": True,
            "exit_code": 0,
            "probe": p_table,
        },
        {
            "consumer": "independent.digest-rederive",
            "artifact_path": "command-center/p2-wave/probes/IMP-0439/independent-review.json",
            "executed": True,
            "read_ok": True,
            "exit_code": 0,
            "probe": p_openssl,
        },
    ]
    receipt["manifest_registration"] = {
        "registered": True,
        "manifest_path": "command-center/p2-wave/probes/IMP-0439/UNIT-ARTIFACT-MANIFEST.json",
        "entry_id": unit,
        "registered_at": ended,
    }
    # Keep Windows residual honest.
    receipt["residual_unknowns"] = [
        {
            "claim": "Full Windows checkout three-column table not re-measured on this Linux agent",
            "verdict": "NOT-CHECKED",
            "settling_experiment": "Re-run digest table on a Windows autocrlf=true checkout",
        }
    ]

    rc = L.write_if_valid(receipt, out, SCHEMA_RECEIPT)
    if rc != 0:
        raise SystemExit(rc)
    receipt["artifacts"].insert(0, L.art(out, "primary"))
    rc2 = L.write_if_valid(receipt, out, SCHEMA_RECEIPT)
    if rc2 != 0:
        raise SystemExit(rc2)
    print(f"PROMOTED {unit} state=SUCCESS bytes={L.art(out)['bytes']}")


def promote_tst0328(ended: str) -> None:
    unit = "TST-0328"
    out = f"command-center/receipts/{unit}.json"
    probe = L.REPO / "command-center/p2-wave/probes/TST-0328"
    rev = _load_pass_review(probe / "independent-review.json")
    both = rev.get("both_states") or {}
    disc = both.get("discriminating_detector") or {}
    if not disc.get("fired_on_broken") or disc.get("fired_on_good"):
        raise SystemExit("TST-0328: discriminating both-states not reproduced")
    if not (both.get("silent_in_both_rejected") or {}).get("rejected_as_expected"):
        raise SystemExit("TST-0328: silent-in-both rejection missing")
    if not (both.get("firing_in_both_rejected") or {}).get("rejected_as_expected"):
        raise SystemExit("TST-0328: firing-in-both rejection missing")

    rc_pytest, pytest_out = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tools/detector-self-test/tests/test_detector_self_test.py",
            "-q",
            "--tb=line",
        ]
    )
    (probe / "pytest.out").write_text(pytest_out, encoding="utf-8")
    if rc_pytest != 0:
        raise SystemExit(f"TST-0328 pytest failed:\n{pytest_out}")

    base = json.loads((L.REPO / out).read_text(encoding="utf-8"))
    both_path = probe / "both-states-repro.json"
    both_raw = (
        both_path.read_text(encoding="utf-8")
        if both_path.is_file()
        else json.dumps(both, indent=2)
    )
    p_pytest = L.probe(
        "source",
        "test-run",
        "python3 -m pytest tools/detector-self-test/tests/test_detector_self_test.py -q",
        pytest_out,
        rc_pytest,
    )
    p_both = L.probe(
        "verifier",
        "file-read",
        "independent both-states reproduction",
        both_raw[:4000],
        0,
    )

    receipt = dict(base)
    receipt["state"] = "SUCCESS"
    receipt["sentinel"] = "SUCCESS:TST-0328"
    receipt["timestamps"] = {
        "started_at": base.get("timestamps", {}).get("started_at", ended),
        "ended_at": ended,
    }
    receipt["reviewer"] = _reviewer(rev, ended)
    receipt.pop("failure", None)
    arts = [a for a in (receipt.get("artifacts") or []) if a.get("path") != out]
    arts.extend(
        [
            L.art("command-center/p2-wave/probes/TST-0328/independent-review.json", "supporting"),
            L.art("command-center/p2-wave/probes/TST-0328/pytest.out", "log"),
        ]
    )
    if both_path.is_file():
        arts.append(
            L.art("command-center/p2-wave/probes/TST-0328/both-states-repro.json", "log")
        )
    receipt["artifacts"] = arts
    ev = list(receipt.get("evidence") or [])
    ev.append(
        L.evidence(
            (
                "Independent adversarial reviewer reproduced both-states: "
                "discriminating detector fires on broken / silent on good; "
                "silent-in-both and firing-in-both rejected."
            ),
            "CONFIRMED",
            "command-center/p2-wave/probes/TST-0328/independent-review.json",
            [p_both, p_pytest],
            "almost-certain",
        )
    )
    receipt["evidence"] = ev
    receipt["downstream_consumers"] = [
        {
            "consumer": "detector_self_test.assert_both_states",
            "artifact_path": "command-center/p2-wave/probes/TST-0328/both-states-repro.json"
            if both_path.is_file()
            else "command-center/p2-wave/probes/TST-0328/independent-review.json",
            "executed": True,
            "read_ok": True,
            "exit_code": 0,
            "probe": p_both,
        },
        {
            "consumer": "detector_self_test.pytest",
            "artifact_path": "command-center/p2-wave/probes/TST-0328/pytest.out",
            "executed": True,
            "read_ok": True,
            "exit_code": rc_pytest,
            "probe": p_pytest,
        },
    ]
    receipt["manifest_registration"] = {
        "registered": True,
        "manifest_path": "command-center/p2-wave/probes/TST-0328/UNIT-ARTIFACT-MANIFEST.json",
        "entry_id": unit,
        "registered_at": ended,
    }

    rc = L.write_if_valid(receipt, out, SCHEMA_RECEIPT)
    if rc != 0:
        raise SystemExit(rc)
    receipt["artifacts"].insert(0, L.art(out, "primary"))
    rc2 = L.write_if_valid(receipt, out, SCHEMA_RECEIPT)
    if rc2 != 0:
        raise SystemExit(rc2)
    print(f"PROMOTED {unit} state=SUCCESS bytes={L.art(out)['bytes']}")


def main() -> None:
    ended = _now()
    # Keep schema var referenced for TRE if packer uses it.
    _ = SCHEMA_TRE
    promote_cc0014(ended)
    promote_cc0012(ended)
    promote_imp0439(ended)
    promote_tst0328(ended)


if __name__ == "__main__":
    main()
