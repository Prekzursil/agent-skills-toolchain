"""Build judge-visible de-identified bundles and a sealed label mapping."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

from deidentify import deidentify_file
from fixtures import ensure_fixtures
from identities import ARCHITECTURES, enumerated_literals
from leakage import plant_and_scan, scan_tree
from residual import score as residual_score

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
JUDGE_ROOT = REPO / "command-center" / "phase3" / "BLIND-BUNDLE"
ENTRIES_ROOT = JUDGE_ROOT / "entries"
SEALED_ROOT = REPO / "command-center" / "phase3" / "BLIND-SEALED"
PATTERNS_PATH = HERE / "PATTERNS.json"
SALT_PATH = SEALED_ROOT / "SALT"
MAP_PATH = SEALED_ROOT / "MAPPING.json"
MAP_HASH_PATH = SEALED_ROOT / "MAPPING.sha256"
RESIDUAL_PATH = SEALED_ROOT / "RESIDUAL.json"
DOSSIER_NAMES = (
    "DESIGN.json",
    "COST.json",
    "FAILURE-MODES.json",
    "SECURITY.json",
    "MIGRATION.json",
    "TEST-PLAN.json",
    "REFUTATION.json",
)
PLANT = "marketplace-first"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def dump(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ensure_salt() -> bytes:
    SEALED_ROOT.mkdir(parents=True, exist_ok=True)
    if SALT_PATH.is_file() and SALT_PATH.stat().st_size >= 32:
        return bytes.fromhex(SALT_PATH.read_text(encoding="utf-8").strip())
    salt = os.urandom(32)
    SALT_PATH.write_text(salt.hex() + "\n", encoding="utf-8")
    return salt


def opaque_label(arch_id: str, salt: bytes) -> str:
    digest = hashlib.sha256(salt + arch_id.encode("utf-8")).hexdigest()[:12]
    return f"entry-{digest}"


def collect_sources(arch_id: str) -> list[tuple[str, Path, str]]:
    live = REPO / "command-center" / "phase3" / arch_id
    fixture = HERE / "fixtures" / "dossiers" / arch_id
    rows: list[tuple[str, Path, str]] = []
    seen: set[str] = set()
    for root, kind in ((live, "live"), (fixture, "fixture")):
        if not root.is_dir():
            continue
        for name in DOSSIER_NAMES:
            path = root / name
            if not path.is_file() or name in seen:
                continue
            seen.add(name)
            rows.append((name, path, kind))
    return rows


def build() -> dict:
    ensure_fixtures()
    salt = ensure_salt()
    if ENTRIES_ROOT.exists():
        shutil.rmtree(ENTRIES_ROOT)
    ENTRIES_ROOT.mkdir(parents=True, exist_ok=True)
    JUDGE_ROOT.mkdir(parents=True, exist_ok=True)

    mapping_labels: dict[str, dict] = {}
    label_to_arch: dict[str, str] = {}
    entries_meta: list[dict] = []
    live_count = 0
    fixture_count = 0

    for row in ARCHITECTURES:
        arch_id = row["id"]
        sources = collect_sources(arch_id)
        if not sources:
            raise SystemExit(f"FAILED:ARC-0067 no sources for {arch_id}")
        kinds = {k for _, _, k in sources}
        source_kind = "live" if "live" in kinds else "fixture"
        if source_kind == "live":
            live_count += 1
        else:
            fixture_count += 1
        label = opaque_label(arch_id, salt)
        dest = ENTRIES_ROOT / label
        dest.mkdir(parents=True, exist_ok=True)
        files = []
        for name, src, kind in sources:
            out = dest / name
            deidentify_file(src, out)
            files.append({"name": name, "source_kind": kind, "bytes": out.stat().st_size})
        mapping_labels[label] = {
            "architecture_id": arch_id,
            "architecture_name": row["name"],
            "source_kind": source_kind,
            "files": [f["name"] for f in files],
        }
        label_to_arch[label] = arch_id
        entries_meta.append(
            {
                "label": label,
                "relpath": f"entries/{label}/",
                "source_kind": source_kind,
                "file_count": len(files),
                "files": files,
            }
        )

    entries_meta.sort(key=lambda item: item["label"])
    mapping_doc = {
        "unit_id": "ARC-0067",
        "algorithm": "sha256(salt || architecture_id)[:12] with entry- prefix",
        "entry_count": len(mapping_labels),
        "labels": mapping_labels,
    }
    dump(MAP_PATH, mapping_doc)
    digest = sha256_file(MAP_PATH)
    MAP_HASH_PATH.write_text(digest + "\n", encoding="utf-8")
    dump(
        PATTERNS_PATH,
        {
            "unit_id": "ARC-0067",
            "literals": enumerated_literals(),
            "count": len(enumerated_literals()),
        },
    )

    labels_sorted = [e["label"] for e in entries_meta]
    sample = labels_sorted[:3]
    residual = residual_score(ENTRIES_ROOT, label_to_arch, sample)
    residual["all_entry_hit_rate"] = residual_score(
        ENTRIES_ROOT, label_to_arch, labels_sorted
    )["hit_rate"]
    dump(RESIDUAL_PATH, residual)

    leakage = scan_tree(ENTRIES_ROOT)
    plant = plant_and_scan("de-identified bundle body without listed names\n", PLANT)
    if leakage["hit_count"] != 0:
        raise SystemExit(
            f"FAILED:ARC-0067 leakage hits={leakage['hit_count']} sample={leakage['hits'][:5]}"
        )
    if not plant["detector_fired"]:
        raise SystemExit("FAILED:ARC-0067 detector control did not fire")

    return {
        "entry_count": len(entries_meta),
        "live_source_count": live_count,
        "fixture_source_count": fixture_count,
        "pattern_count": len(enumerated_literals()),
        "sealed_mapping_sha256": digest,
        "entries": entries_meta,
        "leakage": {
            "hit_count": leakage["hit_count"],
            "file_count": leakage["file_count"],
            "pattern_count": leakage["pattern_count"],
            "detector_control": "PASS" if plant["detector_fired"] else "FAIL",
        },
        "residual": {
            "attempts": residual["attempts"],
            "hits": residual["hits"],
            "hit_rate": residual["hit_rate"],
            "blindness_score": residual["blindness_score"],
        },
        "judge_visible_root": "command-center/phase3/BLIND-BUNDLE",
        "name_level_deidentification": True,
        "blindness_claimed": False,
    }


if __name__ == "__main__":
    summary = build()
    print(json.dumps({k: summary[k] for k in ("entry_count", "leakage", "residual")}, sort_keys=True))
    print("SUCCESS:ARC-0067 pipeline")
