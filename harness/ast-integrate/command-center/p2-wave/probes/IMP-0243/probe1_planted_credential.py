#!/usr/bin/env python3
"""IMP-0243 probe1: planted credential detected; value absent from every output."""

from __future__ import annotations

import json
import secrets
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
import platform as _plat

_plat.__path__ = [str(REPO / "platform")]  # type: ignore[attr-defined]

from platform.blueprints.security import callset, contract, mechanisms, runtime  # noqa: E402

PREFIX = "PLANTEDFAKE_"
HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0243-probe1 {msg}")
    return 1


def count_hits(root: Path, needle: str) -> int:
    total = 0
    if not needle:
        return 0
    blob = needle.encode("utf-8")
    for path in root.rglob("*"):
        if path.is_file():
            total += path.read_bytes().count(blob)
    return total


def main() -> int:
    blueprints = []
    for path in runtime.discover_blueprints():
        doc = runtime.load_blueprint(path)
        blueprints.append(doc)
    ids = [d["id"] for d in blueprints]
    expected = [
        "wf.sec.threat-modeling",
        "wf.sec.red-blue-review",
        "wf.sec.permission-least-privilege",
        "wf.sec.secret-exposure",
    ]
    if ids != expected:
        return fail(f"blueprint ids {ids} != {expected}")

    refusals = contract.omission_refusals(blueprints[0])
    codes = list(refusals.values())
    if len(set(codes)) != 6 or any(c == "NOT-REFUSED" for c in codes):
        return fail(f"omission refusals not 6 distinct: {refusals}")

    smokes = [runtime.smoke(doc, FIXTURES) for doc in blueprints]
    if not all(s.get("ok") for s in smokes):
        return fail(f"smoke failed: {smokes}")

    body = secrets.token_hex(16)
    value = PREFIX + body
    with tempfile.TemporaryDirectory(prefix="imp0243-") as tmp:
        tmp_path = Path(tmp)
        planted = tmp_path / "in" / "config.env"
        out_dir = tmp_path / "out"
        planted.parent.mkdir()
        out_dir.mkdir()
        planted.write_text(f"API_KEY={value}\n", encoding="utf-8")
        report = mechanisms.secret_exposure(planted.parent)
        mechanisms.emit_report(report, known_secrets=[value])
        (out_dir / "secret-exposure.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        detected = int(report.get("finding_count") or 0) >= 1
        prefixes = [f.get("prefix") for f in report.get("findings") or []]
        recs = [
            (f.get("rotation") or {}).get("recommendation")
            for f in report.get("findings") or []
        ]
        rotates = bool(report.get("rotates"))
        owner_rec = "RECOMMENDATION" in (report.get("owner_recommendation") or "").upper() or any(
            "RECOMMENDATION" in (r or "").upper() or "Owner must rotate" in (r or "") for r in recs
        )
        prefix_hits = count_hits(out_dir, PREFIX)
        value_hits = count_hits(out_dir, value)
        summary = {
            "probe": "probe1-planted-credential",
            "blueprints": ids,
            "omission_codes": codes,
            "smokes_ok": [s.get("ok") for s in smokes],
            "detected": detected,
            "prefix": PREFIX,
            "prefixes_reported": prefixes,
            "prefix_hits": prefix_hits,
            "value_hits": value_hits,
            "rotates": rotates,
            "owner_recommendation_present": owner_rec,
            "finding_count": report.get("finding_count"),
            "bare_prefix_findings": smokes[-1].get("finding_count"),
        }
        dumped = json.dumps(summary, sort_keys=True)
        if value in dumped:
            return fail("summary leaked planted value")
        print(dumped)
        if not detected:
            return fail("planted credential not detected")
        if PREFIX not in prefixes:
            return fail("prefix not reported")
        if prefix_hits <= 0:
            return fail("prefix absent from outputs")
        if value_hits != 0:
            return fail("secret value present in outputs")
        if rotates:
            return fail("report claims rotate=true")
        if not owner_rec:
            return fail("rotation recommendation missing")
        if callset.forbidden_hits(["secret_exposure", "redact_value"]):
            return fail("call names misclassified")
    print("SUCCESS:IMP-0243-probe1 planted credential detected; value absent from outputs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
