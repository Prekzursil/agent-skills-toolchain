#!/usr/bin/env python3
"""Measure TST-0331: planted / valid / revision-correctness battery + report.

Emits command-center/p2-wave/probes/TST-0331/battery-summary.json with the
catalog evidence counts (checked / resolved / unresolved / unparseable) and
the three required control outcomes.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

# measure_battery.py lives at command-center/p2-wave/probes/TST-0331/ → repo root is parents[4]
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "platform" / "lib"))

from evidence_anchor_resolver import (  # noqa: E402
    line_count_at_revision,
    parse_anchor,
    resolve_anchor,
    validate_receipt_evidence,
)

PROBE_DIR = Path(__file__).resolve().parent
OUT = PROBE_DIR / "battery-summary.json"
PYTEST_OUT = PROBE_DIR / "pytest.out"
UNIT = "TST-0331"


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return (proc.stdout or "").strip()


def build_revision_fixture(root: Path) -> dict[str, str]:
    repo = root / "revrepo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "tst0331@example.com")
    _git(repo, "config", "user.name", "TST-0331")
    _git(repo, "config", "commit.gpgsign", "false")

    notes = repo / "doc" / "notes.txt"
    notes.parent.mkdir(parents=True)
    notes.write_text("L1\nL2\nL3\nL4\nL5-only-at-old\n", encoding="utf-8")
    _git(repo, "add", "doc/notes.txt")
    _git(repo, "commit", "-m", "old: five lines")
    old = _git(repo, "rev-parse", "HEAD")

    notes.write_text("L1\nL2\n", encoding="utf-8")
    _git(repo, "add", "doc/notes.txt")
    _git(repo, "commit", "-m", "head: two lines")

    present = repo / "doc" / "present.txt"
    present.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    _git(repo, "add", "doc/present.txt")
    _git(repo, "commit", "-m", "add present.txt")
    head = _git(repo, "rev-parse", "HEAD")
    return {"repo": str(repo), "old": old, "head": head}


def run_battery() -> dict:
    with tempfile.TemporaryDirectory(prefix="tst0331-") as td:
        fx = build_revision_fixture(Path(td))
        repo = Path(fx["repo"])
        old, head = fx["old"], fx["head"]

        # --- Planted bad ---
        planted = []
        for label, raw, item_extra in (
            (
                "nonexistent_file",
                f"rev:{head}:doc/does-not-exist.txt:1",
                {},
            ),
            (
                "out_of_range_line",
                f"rev:{head}:doc/present.txt:999",
                {},
            ),
            (
                "command_never_run",
                "command:python -B never_executed_probe.py",
                {
                    "probes": [
                        {
                            "role": "source",
                            "method": "command",
                            "command": "echo hello",
                            "raw_output": "hello\n",
                        }
                    ]
                },
            ),
        ):
            parsed = parse_anchor(raw)
            res = resolve_anchor(
                parsed, repo=repo, evidence_item={"anchor": raw, **item_extra}
            )
            planted.append(
                {
                    "label": label,
                    "anchor": raw,
                    "status": res.status,
                    "reason": res.reason,
                    "detected": res.status == "unresolved",
                }
            )
        planted_all_detected = all(p["detected"] for p in planted)

        # --- Valid ---
        valid_cases = []
        for label, raw, item in (
            (
                "file_line",
                f"rev:{head}:doc/present.txt:2",
                {},
            ),
            (
                "command_in_transcript",
                "command:python -B measure.py",
                {
                    "probes": [
                        {
                            "role": "source",
                            "method": "command",
                            "command": "python -B measure.py",
                            "raw_output": '{"ok": true}\n',
                        }
                    ]
                },
            ),
            (
                "url_archived",
                "https://example.com/spec",
                {
                    "archive_url": (
                        "https://web.archive.org/web/20260101000000/"
                        "https://example.com/spec"
                    )
                },
            ),
            (
                "inferred_from",
                "inferred-from:CC-0009 ARTIFACT-MANIFEST.json",
                {},
            ),
        ):
            parsed = parse_anchor(raw)
            res = resolve_anchor(
                parsed, repo=repo, evidence_item={"anchor": raw, **item}
            )
            valid_cases.append(
                {
                    "label": label,
                    "anchor": raw,
                    "status": res.status,
                    "passed": res.status == "resolved",
                    "reason": res.reason,
                }
            )
        valid_all_pass = all(v["passed"] for v in valid_cases)

        # --- Revision correctness ---
        n_old = line_count_at_revision("doc/notes.txt", old, repo=repo)
        n_head = line_count_at_revision("doc/notes.txt", head, repo=repo)
        pinned = resolve_anchor(
            parse_anchor(f"rev:{old}:doc/notes.txt:5"),
            repo=repo,
            default_revision=head,
        )
        at_head = resolve_anchor(
            parse_anchor(f"rev:{head}:doc/notes.txt:5"),
            repo=repo,
        )
        revision_ok = (
            n_old == 5
            and n_head == 2
            and pinned.status == "resolved"
            and at_head.status == "unresolved"
        )

        # Aggregate report over a synthetic receipt that mixes planted + valid.
        receipt = {
            "evidence": [
                {
                    "anchor": f"rev:{head}:doc/present.txt:1",
                    "claim": "valid",
                    "verdict": "CONFIRMED",
                    "probes": [
                        {
                            "role": "source",
                            "method": "file-read",
                            "command": "cat",
                            "raw_output": "alpha",
                        }
                    ],
                },
                {
                    "anchor": f"rev:{head}:doc/missing.txt:1",
                    "claim": "planted missing",
                    "verdict": "CONFIRMED",
                    "probes": [
                        {
                            "role": "source",
                            "method": "file-read",
                            "command": "x",
                            "raw_output": "y",
                        }
                    ],
                },
                {
                    "anchor": "command:python -B measure.py",
                    "claim": "valid cmd",
                    "verdict": "CONFIRMED",
                    "probes": [
                        {
                            "role": "source",
                            "method": "command",
                            "command": "python -B measure.py",
                            "raw_output": "ok",
                        }
                    ],
                },
                {
                    "anchor": "??? junk ???",
                    "claim": "unparseable",
                    "verdict": "CONFIRMED",
                    "probes": [
                        {
                            "role": "source",
                            "method": "command",
                            "command": "x",
                            "raw_output": "y",
                        }
                    ],
                },
            ]
        }
        report = validate_receipt_evidence(receipt, repo=repo)

        # Also spot-check one live SUCCESS receipt for false-positive rate on
        # file: anchors that are revision-unpinned (default HEAD). We only
        # count file-kind anchors that parse cleanly; command/url theatre in
        # live receipts is out of scope for the false-positive claim.
        live_path = REPO / "command-center/receipts/CC-0009.json"
        live_fp = {"path": str(live_path.relative_to(REPO)), "skipped": True}
        if live_path.is_file():
            live_doc = json.loads(live_path.read_text(encoding="utf-8"))
            file_items = []
            for ev in live_doc.get("evidence") or []:
                if not isinstance(ev, dict):
                    continue
                a = ev.get("anchor")
                if not isinstance(a, str):
                    continue
                # Prefer file:/path:line or path:line forms.
                p = parse_anchor(
                    a if a.startswith("file:") or ":" in a.split()[0] else f"file:{a}"
                )
                if p.kind == "file" and p.path:
                    # Re-resolve with file: prefix so bare prose anchors that
                    # happen to look like paths are exercised honestly.
                    item = dict(ev)
                    item["anchor"] = (
                        f"file:{p.path}" + (f":{p.line}" if p.line else "")
                    )
                    file_items.append(item)
            if file_items:
                live_report = validate_receipt_evidence(
                    file_items, repo=REPO, default_revision="HEAD"
                )
                live_fp = {
                    "path": "command-center/receipts/CC-0009.json",
                    "skipped": False,
                    "file_anchors_checked": live_report.anchors_checked,
                    "resolved": live_report.resolved,
                    "unresolved": live_report.unresolved,
                    "unparseable": live_report.unparseable,
                    "unresolved_list": live_report.unresolved_list,
                }

        ok = (
            planted_all_detected
            and valid_all_pass
            and revision_ok
            and report.anchors_checked == 4
            and report.resolved == 2
            and report.unresolved == 1
            and report.unparseable == 1
        )

        summary = {
            "unit": UNIT,
            "ok": ok,
            "both_states": {
                "planted_bad_detected": planted_all_detected,
                "valid_anchors_pass": valid_all_pass,
                "revision_correctness_pass": revision_ok,
            },
            "planted": planted,
            "valid": valid_cases,
            "revision_correctness": {
                "old_rev": old,
                "head_rev": head,
                "lines_at_old": n_old,
                "lines_at_head": n_head,
                "pinned_status": pinned.status,
                "head_status": at_head.status,
                "pass": revision_ok,
            },
            "report": report.to_dict(),
            "live_receipt_file_anchor_spotcheck": live_fp,
            "reads_cited_revision_not_worktree": True,
        }
        OUT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return summary


def main() -> int:
    # Run unit tests first; their outcome is part of the measurement surface.
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(REPO / "platform/lib/test_evidence_anchor_resolver.py"),
            "-q",
            "--tb=line",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    PYTEST_OUT.write_text(
        (proc.stdout or "") + (proc.stderr or ""), encoding="utf-8"
    )
    if proc.returncode != 0:
        print(f"FAILED:{UNIT} pytest failed:\n{proc.stdout}\n{proc.stderr}", file=sys.stderr)
        return 1

    summary = run_battery()
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary.get("ok"):
        print(f"FAILED:{UNIT} battery ok=false", file=sys.stderr)
        return 1
    print(
        f"OK:{UNIT} planted/valid/revision battery green "
        "(receipt still BLOCKED pending independent adversarial review)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
