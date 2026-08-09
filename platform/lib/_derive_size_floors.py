"""Derive per-class minimum-meaningful-size floors from the REAL artifact distribution.

ARC-0084 requires: "Size floors are derived from the distribution of real artifacts already on
disk rather than chosen arbitrarily, and the derivation is shown."

Population = every file registered in command-center/ARTIFACT-MANIFEST.json plus every
command-center/*.json|*.md|*.jsonl on disk. Floor rule (stated before looking at the numbers so
it cannot be fitted to a desired answer):

    floor(class) = max(64, floor_to_pow2_ish(0.5 * min(observed sizes in class)))

i.e. half the smallest REAL artifact of that class, never below 64 bytes. Half-the-minimum keeps
the floor strictly under every real artifact (no false positives on today's corpus) while staying
orders of magnitude above 1 byte, which ARC-0084 explicitly rejects as "not a real threshold".
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

CC = Path(r"C:/Users/Prekzursil/source/ast-integrate/command-center")
REPO = CC.parent


def classify(p: Path) -> str:
    suf = p.suffix.lower()
    if suf == ".jsonl":
        return "jsonl"
    if suf == ".json":
        return "json"
    if suf == ".md":
        return "markdown"
    return "other"


def main() -> int:
    seen: dict[Path, int] = {}

    manifest = json.loads((CC / "ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
    manifest_paths = []
    for a in manifest["artifacts"]:
        fp = REPO / a["path"]
        manifest_paths.append(a["path"])
        if fp.is_file():
            seen[fp] = fp.stat().st_size

    for pat in ("*.json", "*.md"):
        for fp in CC.glob(pat):
            if fp.name.startswith("_"):
                continue  # scratch probes, not artifacts
            seen[fp] = fp.stat().st_size
    for fp in (CC / "events").glob("*.jsonl"):
        seen[fp] = fp.stat().st_size

    by_class: dict[str, list[int]] = {}
    for fp, n in seen.items():
        by_class.setdefault(classify(fp), []).append(n)

    out = {
        "population_size": len(seen),
        "manifest_registered": len(manifest_paths),
        "by_class": {},
        "floor_rule": "max(64, int(0.5 * min(class)))",
    }
    for cls, sizes in sorted(by_class.items()):
        sizes.sort()
        floor = max(64, int(0.5 * sizes[0]))
        out["by_class"][cls] = {
            "n": len(sizes),
            "min": sizes[0],
            "p50": int(statistics.median(sizes)),
            "max": sizes[-1],
            "derived_floor": floor,
            "smallest_real_artifact_over_floor": sizes[0] > floor,
        }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
