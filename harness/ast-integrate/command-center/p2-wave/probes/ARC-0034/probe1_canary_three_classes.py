#!/usr/bin/env python3
"""Probe 1: planted PLANTEDFAKE_ canary in three artifact classes; mention control.

Canary shape: zero-entropy prefix PLANTEDFAKE_ plus a high-entropy random body.
Planted only in a temp dir, never in the repo. Findings report prefix and
suffix_len only. A miss in any class is P0.

False-positive control: a document that names token variables and the type
token PLANTEDFAKE_ without a secret body must stay silent.

Also measures the live marketplace payload scanner
(platform/marketplace/mkt/publish.py scan_text) against the same canary so
the review can record PEM-only (SEC-1) vs entropy (SEC-7) behaviour.
tools/marketplace/secret_gate.py is absent on this worktree and is not
invented here.
"""
from __future__ import annotations

import json
import re
import secrets
import sys
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scrubber as S  # noqa: E402

OUT = HERE / "probe1-canary.raw.json"
PREFIX = "PLANTEDFAKE_"
MENTION_DOC = """Credential handling notes (mention-only, no values):

The cloud-batch unit reads ANTHROPIC_API_KEY from the injected environment.
API_TOKEN is the variable name the broker binds at process start.
OPENAI_API_KEY must be present at runtime; the image stores the name only.
The zero-entropy prefix PLANTEDFAKE_ marks a canary type; it is not a secret.
"""


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0034-probe1 {msg}")
    return 1


PEM_ONLY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
LIVE_SCANNER = "platform/marketplace/mkt/publish.py"


def marketplace_scan_text(canary: str) -> list:
    """Call the live publish scanner. Findings must not include the secret body."""
    mkt_root = REPO / "platform" / "marketplace"
    live = mkt_root / "mkt" / "publish.py"
    if not live.is_file():
        raise RuntimeError(f"live scanner missing: {LIVE_SCANNER}")
    if str(mkt_root) not in sys.path:
        sys.path.insert(0, str(mkt_root))
    from mkt.publish import scan_text  # noqa: WPS433

    return list(scan_text(canary, "canary.txt"))


def pack_tar(files: dict[str, bytes]) -> bytes:
    buf = BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, BytesIO(data))
    return buf.getvalue()


def main() -> int:
    body = secrets.token_urlsafe(24)
    if S.shannon_entropy(body) < S.MIN_BODY_ENTROPY:
        return fail("canary body entropy below threshold; retry generation")
    canary = PREFIX + body
    classes: dict[str, bytes] = {
        "receipt-json": json.dumps(
            {"unit_id": "ARC-0034", "injected": canary}, sort_keys=True
        ).encode("utf-8"),
        "transcript-log": f"worker start\nbroker injected token={canary}\n".encode(
            "utf-8"
        ),
        "harvest-bundle": pack_tar(
            {"receipts/unit.json": b'{"ok":true}\n', "nested/secret.txt": canary.encode()}
        ),
    }

    per_class = []
    caught = 0
    for cls, blob in classes.items():
        findings = S.scan_artifact(blob, f"planted/{cls}", cls)
        hit = any(f.prefix == PREFIX and f.suffix_len == len(body) for f in findings)
        if hit:
            caught += 1
        per_class.append(
            {
                "artifact_class": cls,
                "caught": hit,
                "finding_count": len(findings),
                "prefixes": sorted({f.prefix for f in findings}),
                "rule_ids": sorted({f.rule_id for f in findings}),
            }
        )

    mention_findings = S.scan_bytes(
        MENTION_DOC.encode("utf-8"), "mention.md", "transcript-log"
    )
    mention_silent = len(mention_findings) == 0

    with tempfile.TemporaryDirectory(prefix="arc0034-p1-") as tmp:
        tmp_path = Path(tmp)
        planted = tmp_path / "planted-receipt.json"
        planted.write_bytes(classes["receipt-json"])
        report_rows = S.findings_as_dicts(
            S.scan_bytes(planted.read_bytes(), "planted-receipt.json", "receipt-json")
        )
        report_text = json.dumps(report_rows, sort_keys=True)
        leaked = S.report_contains_secret_body(report_text, body) or (
            canary in report_text
        )

    try:
        live_findings = marketplace_scan_text(canary)
    except Exception as exc:  # noqa: BLE001
        return fail(f"marketplace scan_text failed: {type(exc).__name__}")
    live_rules = sorted(
        {getattr(f, "rule", "") for f in live_findings if getattr(f, "rule", "")}
    )
    pem_only_hits = bool(PEM_ONLY.search(canary))
    gate_catches_token_canary = len(live_findings) > 0

    catch_rate = caught / len(classes)
    snap = {
        "probe": "probe1-canary-three-classes",
        "prefix": PREFIX,
        "suffix_len": len(body),
        "artifact_classes": [c["artifact_class"] for c in per_class],
        "per_class": per_class,
        "caught": caught,
        "planted": len(classes),
        "catch_rate": catch_rate,
        "mention_silent": mention_silent,
        "mention_finding_count": len(mention_findings),
        "report_leaked_body": leaked,
        "secret_gate_catches_token_canary": gate_catches_token_canary,
        "secret_gate_finding_count": len(live_findings),
        "secret_gate_path": LIVE_SCANNER,
        "secret_gate_rules": live_rules,
        "pem_only_sec1_catches_token_canary": pem_only_hits,
        "tools_marketplace_secret_gate_present": (
            REPO / "tools" / "marketplace" / "secret_gate.py"
        ).is_file(),
        "false_negative_budget_declared_shape": 0,
        "observed_declared_shape_fn": len(classes) - caught,
    }
    dumped = json.dumps(snap, indent=2, sort_keys=True)
    if body in dumped or canary in dumped:
        return fail("raw snapshot leaked canary body")
    OUT.write_text(dumped + "\n", encoding="utf-8")

    print(
        "prefix="
        + PREFIX
        + " suffix_len="
        + str(len(body))
        + " caught="
        + str(caught)
        + "/"
        + str(len(classes))
        + " catch_rate="
        + str(catch_rate)
        + " mention_silent="
        + str(mention_silent)
        + " leaked_body="
        + str(leaked)
        + " secret_gate_token_canary="
        + str(gate_catches_token_canary)
        + " pem_only="
        + str(pem_only_hits)
    )
    if caught != len(classes):
        return fail("canary miss is P0; catch_rate=" + str(catch_rate))
    if not mention_silent:
        return fail("mention document was flagged")
    if leaked:
        return fail("canary body appeared in the finding report")
    print("SUCCESS:ARC-0034-probe1 canary 3/3; mention silent; body unreported")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
