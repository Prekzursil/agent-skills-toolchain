#!/usr/bin/env python3
"""Shard-15 JSON surgery + LF sha256 manifest refresh. Not a probe."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")


def lf_sha(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def dump(path: Path, doc) -> None:
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    path.write_bytes(text.encode("utf-8").replace(b"\r\n", b"\n"))


def patch_adv0097() -> None:
    path = REPO / "command-center/adversarial/ADV-0097-minority-report-survival-trace.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["report_kind"] = "council-pathology-sim"
    obs = doc.get("observations") or []
    if not isinstance(doc.get("report"), dict):
        doc["report"] = {
            "kind": "council-pathology-sim",
            "observations": obs,
            "control_ids": [
                "NC-TOKEN-DROP-AT-DIGEST",
                "NC-SEMANTIC-DROP-WITH-TOKEN-PRESERVED",
                "NC-MAJORITY-DROP-GOES-RED",
            ],
        }
    dump(path, doc)
    print("patched", path.relative_to(REPO).as_posix())


def patch_rel0015() -> None:
    path = REPO / "command-center/receipts/REL-0015.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    nested = None
    report = doc.get("report")
    if isinstance(report, dict) and isinstance(report.get("published_table"), dict):
        nested = report["published_table"]
    if nested is None:
        raise SystemExit("REL-0015 published_table missing under report")
    doc["published_table"] = nested
    dump(path, doc)
    print("patched", path.relative_to(REPO).as_posix())


def patch_arc0104() -> None:
    path = REPO / "command-center/phase4/conformance/ARC-0104.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    removed = 0

    def scrub_dm(dm: dict) -> None:
        nonlocal removed
        fields = list(dm.get("fields") or [])
        if "ARC-0083.require_complete" not in fields:
            return
        fields = [f for f in fields if f != "ARC-0083.require_complete"]
        dm["fields"] = fields
        dm["count"] = len(fields)
        removed += 1

    def walk(obj):
        if isinstance(obj, dict):
            if "default_mismatch" in obj and isinstance(obj["default_mismatch"], dict):
                if "fields" in obj["default_mismatch"]:
                    scrub_dm(obj["default_mismatch"])
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for x in obj:
                walk(x)

    walk(doc)
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    dirs = report.get("directions") if isinstance(report.get("directions"), dict) else {}
    if all(
        k in dirs
        for k in (
            "docs_not_schema",
            "docs_not_impl",
            "schema_not_docs",
            "impl_not_docs",
            "schema_not_impl",
            "impl_not_schema",
            "default_mismatch",
        )
    ):
        total = sum(
            int((dirs[k] or {}).get("count") or 0)
            for k in (
                "docs_not_schema",
                "docs_not_impl",
                "schema_not_docs",
                "impl_not_docs",
                "schema_not_impl",
                "impl_not_schema",
                "default_mismatch",
            )
        )
        capn = report.get("caption_sum_not_a_result")
        if isinstance(capn, dict):
            capn["sum"] = total
        for obs in report.get("observations") or []:
            if isinstance(obs, dict) and obs.get("name") == "caption_sum":
                obs["measured"] = total

    for block in list(doc.get("contracts") or []) + list(report.get("contracts") or []):
        if not isinstance(block, dict):
            continue
        notes = block.get("notes")
        if isinstance(notes, list):
            block["notes"] = [
                s.replace(
                    "and is OFF unless --require-complete.",
                    "and defaults ON; --no-require-complete disarms.",
                )
                if isinstance(s, str)
                else s
                for s in notes
            ]

    dump(path, doc)
    print("patched ARC-0104 require_complete mismatch rows=", removed)


def refresh_manifests(pairs: list[tuple[str, list[str]]]) -> None:
    for uid, rels in pairs:
        man = REPO / f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json"
        if not man.is_file():
            print("missing manifest", uid)
            continue
        doc = json.loads(man.read_text(encoding="utf-8"))
        by_path = {}
        for a in doc.get("artifacts") or []:
            if isinstance(a, dict):
                by_path[str(a.get("path") or "").replace("\\", "/")] = a
        for rel in rels:
            p = REPO / rel
            if not p.is_file():
                print("missing file", rel)
                continue
            sha, nbytes = lf_sha(p)
            row = by_path.get(rel)
            if row is None:
                print("no manifest row", uid, rel)
                continue
            row["sha256"] = sha
            row["bytes"] = nbytes
            row["present"] = True
            print(f"manifest {uid} {rel} sha={sha[:12]} bytes={nbytes}")
        dump(man, doc)


def main() -> None:
    patch_adv0097()
    patch_rel0015()
    patch_arc0104()
    refresh_manifests(
        [
            (
                "ADV-0097",
                [
                    "command-center/adversarial/ADV-0097-minority-report-survival-trace.json",
                    "command-center/p2-wave/probes/ADV-0097/probe2_semantic_survival.py",
                ],
            ),
            (
                "ARC-0040",
                ["command-center/phase3/A6/FAILURE-MODES.json"],
            ),
            (
                "ARC-0104",
                [
                    "command-center/phase4/conformance/ARC-0104.json",
                    "command-center/p2-wave/probes/ARC-0104/surfaces.py",
                ],
            ),
            (
                "CNF-0070",
                ["command-center/p2-wave/probes/CNF-0070/probe2_verdict_split.py"],
            ),
            (
                "AUD-0053",
                ["command-center/p2-wave/probes/AUD-0053/engine.py"],
            ),
            (
                "REL-0015",
                ["command-center/receipts/REL-0015.json"],
            ),
        ]
    )


if __name__ == "__main__":
    main()
