"""Receipt gate: invalid or missing registered receipts turn the gate red (IMP-0435).

Contract:
* walk command-center/p2-wave/probes/*/UNIT-ARTIFACT-MANIFEST.json and admit
  every receipt the current wave registered (through receipt_validate.admit);
* no manifests, or zero registered receipts, is a RED (fail-closed empty walk);
* C1 parse / C3 catalog-id / missing file rejections are RED;
* C2 schema-invalid rejections are reported per receipt as `schema_drift`
  (the live gate schema tightened after the historical receipts were closed;
  the drift census keeps that visible instead of folding it into green);
* there is NO skip flag. --skip-receipts style argv is refused with exit 2.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
PROBES = REPO / "command-center" / "p2-wave" / "probes"

BANNED_FLAGS = (
    "--skip-receipts", "--no-receipts", "--skip-gate",
    "--continue-on-error", "--exit-zero", "--force-green",
)
GATING_CLASSES = ("C1", "C3", "C4", "C5")


def registered_receipts(root: Path | None = None) -> list[dict[str, Any]]:
    """Receipt paths registered by the current wave's per-unit manifests."""
    base = Path(root) if root is not None else REPO
    probes = base / "command-center" / "p2-wave" / "probes"
    rows: dict[str, dict[str, Any]] = {}
    if not probes.is_dir():
        return []
    for man in sorted(probes.glob("*/UNIT-ARTIFACT-MANIFEST.json")):
        try:
            doc = json.loads(man.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for art in doc.get("artifacts") or []:
            if not isinstance(art, dict) or art.get("present") is not True:
                continue
            rel = str(art.get("path") or "").replace(chr(92), "/")
            if not rel.endswith(".json") or "/receipts/" not in "/" + rel:
                continue
            uid = str(art.get("unit_id") or doc.get("unit_id") or "")
            if rel not in rows:
                rows[rel] = {"path": rel, "unit_id": uid,
                             "manifest": man.relative_to(base).as_posix()}
    return sorted(rows.values(), key=lambda r: r["path"])


def check_default(root: Path | None = None) -> dict[str, Any]:
    """Admit every registered receipt. Fail closed; report schema drift."""
    base = Path(root) if root is not None else REPO
    reg = registered_receipts(base)
    if not reg:
        return {"ok": False, "reason": "fail-closed empty walk (no registered receipts)",
                "checked": 0, "admitted": 0, "rejected": [], "schema_drift": [],
                "empty_walk": True}

    sys.path.insert(0, str(REPO / "command-center"))
    import receipt_validate as rv  # noqa: PLC0415

    ids = rv.catalog_ids(REPO)
    gate = rv._load_gate()
    admitted = 0
    rejected: list[dict[str, str]] = []
    drift: list[dict[str, str]] = []
    for row in reg:
        p = base / row["path"]
        if not p.is_file():
            rejected.append({"path": row["path"], "unit_id": row["unit_id"],
                             "reason": "C1 missing receipt file"})
            continue
        ok, uid, reason = rv.admit(p, ids, gate)
        if ok:
            admitted += 1
            continue
        entry = {"path": row["path"], "unit_id": uid or row["unit_id"], "reason": reason}
        # An unknown catalog id is unconditionally invalid: schema drift never
        # absorbs a C3. Only known-id receipts may ride the drift census.
        unknown_id = (uid or row["unit_id"]) not in ids
        if reason.startswith("C2") and not unknown_id:
            drift.append(entry)
        else:
            if unknown_id and reason.startswith("C2"):
                entry["reason"] = "C3 unit_id %r is not one of the %d catalog units" % (
                    entry["unit_id"], len(ids))
            rejected.append(entry)

    return {
        "ok": not rejected,
        "reason": "" if not rejected else "%d gating rejection(s)" % len(rejected),
        "checked": len(reg),
        "admitted": admitted,
        "rejected": rejected,
        "rejected_count": len(rejected),
        "schema_drift": drift,
        "schema_drift_count": len(drift),
        "empty_walk": False,
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    for flag in argv:
        if flag in BANNED_FLAGS:
            print("FAILED:receipt-gate banned flag %s refused (no skip surface)" % flag)
            return 2
    root = None
    if "--root" in argv:
        i = argv.index("--root")
        root = Path(argv[i + 1])
    report = check_default(root)
    for entry in report.get("rejected") or []:
        print("REJECT:%s %s" % (entry.get("unit_id"), entry.get("reason", "")[:120]))
    for entry in report.get("schema_drift") or []:
        print("SCHEMA-DRIFT:%s %s" % (entry.get("unit_id"), entry.get("reason", "")[:96]))
    if not report["ok"]:
        print("FAILED:receipt-gate %s" % report.get("reason", ""))
        return 1
    print("SUCCESS:receipt-gate checked=%d admitted=%d schema_drift=%d"
          % (report["checked"], report["admitted"], report.get("schema_drift_count", 0)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
