#!/usr/bin/env python3
"""Probe 2: out-of-band check that submit writes no network and no index bytes.

Independent of probe 1's exit-code matrix: hashes the index before/after and
reads the egress log. Also proves a lint failure blocks sign and submit.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import workspace as W  # noqa: E402

ART = W.REPO / "command-center/receipts/IMP-0115.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="imp0115-p2-"))
    good = W.write_good_tree(root)
    bad = W.write_bad_tree(root)
    index = W.write_empty_index(root)
    key = root / "hmac.key"
    key.write_text("0123456789abcdef0123456789abcdef", encoding="utf-8")
    pkg = root / "good.zip"
    bad_pkg = root / "bad.zip"
    pr = root / "submit.pr.json"
    egress = root / "egress.jsonl"
    sig = root / "good.sig.json"

    pack = W.run_cli(["pack", "--src", str(good), "--out", str(pkg)], root)
    if pack.returncode != W.EXIT_OK:
        print("FAILED:IMP-0115-probe2 pack good")
        return 1

    before = sha256(index)
    before_bytes = index.read_bytes()
    submit = W.run_cli(
        [
            "submit",
            "--package",
            str(pkg),
            "--index",
            str(index),
            "--out",
            str(pr),
            "--egress-log",
            str(egress),
        ],
        root,
    )
    after = sha256(index)
    events = [
        json.loads(line)
        for line in egress.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    last = events[-1] if events else {}
    side = {
        "submit_exit": submit.returncode,
        "index_sha256_before": before,
        "index_sha256_after": after,
        "index_bytes_unchanged": index.read_bytes() == before_bytes,
        "index_mutated_flag": last.get("index_mutated"),
        "network_attempted": last.get("network_attempted"),
        "network_writes": last.get("network_writes"),
        "pr_kind": json.loads(pr.read_text(encoding="utf-8")).get("kind") if pr.is_file() else None,
        "pr_network_write": json.loads(pr.read_text(encoding="utf-8")).get("network_write")
        if pr.is_file()
        else None,
        "pr_direct_index_write": json.loads(pr.read_text(encoding="utf-8")).get("direct_index_write")
        if pr.is_file()
        else None,
    }

    pack_bad = W.run_cli(["pack", "--src", str(bad), "--out", str(bad_pkg)], root)
    sign_bad = W.run_cli(
        ["sign", "--package", str(bad_pkg), "--key", str(key), "--out", str(sig)],
        root,
    )
    submit_bad = W.run_cli(
        [
            "submit",
            "--package",
            str(bad_pkg),
            "--index",
            str(index),
            "--out",
            str(root / "bad.pr.json"),
            "--egress-log",
            str(root / "bad.egress.jsonl"),
        ],
        root,
    )
    negative = {
        "pack_bad_exit": pack_bad.returncode,
        "sign_bad_exit": sign_bad.returncode,
        "submit_bad_exit": submit_bad.returncode,
        "sign_blocked": sign_bad.returncode == W.EXIT_VALIDATION and not sig.exists(),
        "submit_blocked": submit_bad.returncode == W.EXIT_VALIDATION
        and not (root / "bad.pr.json").exists(),
        "index_still_unchanged": sha256(index) == before,
    }

    direct = W.run_cli(
        [
            "submit",
            "--direct",
            "--package",
            str(pkg),
            "--index",
            str(index),
            "--out",
            str(root / "direct.pr.json"),
            "--egress-log",
            str(root / "direct.egress.jsonl"),
        ],
        root,
    )
    blocked = {
        "direct_exit": direct.returncode,
        "expected": W.EXIT_BLOCKED_NEEDS_OWNER,
        "direct_pr_absent": not (root / "direct.pr.json").exists(),
        "index_after_direct": sha256(index),
    }

    report = {"side_effect": side, "negative_lint": negative, "direct_guard": blocked}
    (HERE / "probe2-submit-side-effects.raw.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True))

    ok = (
        submit.returncode == W.EXIT_OK
        and before == after
        and side["index_bytes_unchanged"] is True
        and side["index_mutated_flag"] is False
        and side["network_attempted"] is False
        and side["network_writes"] == []
        and side["pr_kind"] == "pull-request"
        and side["pr_network_write"] is False
        and side["pr_direct_index_write"] is False
        and negative["sign_blocked"]
        and negative["submit_blocked"]
        and negative["index_still_unchanged"]
        and blocked["direct_exit"] == W.EXIT_BLOCKED_NEEDS_OWNER
        and blocked["direct_pr_absent"]
        and blocked["index_after_direct"] == before
    )
    if not ok:
        print("FAILED:IMP-0115-probe2 side-effect or lint-block check")
        return 1

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:IMP-0115-probe2 self-declared {doc.get('state')}")
            return 1
        if "SUCCESS:IMP-0115" not in text:
            print("FAILED:IMP-0115-probe2 sentinel absent")
            return 1

    print("SUCCESS:IMP-0115-probe2 submit wrote nothing; lint blocks sign/submit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
