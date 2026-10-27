r"""_i1_track_precheck.py -- is tracking the H-family a NEW disclosure or a NEW secret?

Two questions, answered separately because they have different answers:

  1. Do these files carry credential-SHAPED strings? Classified by STRUCTURE only (length,
     charset, prefix); no value is ever printed, per AGENTS.md section 9.
  2. Does the home path they contain constitute a NEW exposure class, or does ALREADY-TRACKED
     evidence in this same directory carry it? A control both ways: the detector must find
     the path in a file known to contain it, and must not find it in a synthetic clean string.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EVID = REPO / "command-center" / "hook-audit"
CANDIDATES = [
    "H1-INVENTORY.json",
    "H2-UNWIRED.json",
    "H5-CP1252.json",
    "H6-WIRECHECK-FASTPATH.json",
    "H7-WIRECHECK-FP.json",
    "H8-ROLLBACK-GAP.json",
    "H9-BLOCK-CENSUS.json",
]

# Structure only. A long high-entropy run, or a known key prefix. Never the value.
SECRETISH = re.compile(
    r"(?:sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{20,}|"
    r"gh[pousr]_[A-Za-z0-9]{20,}|xox[abprs]-[A-Za-z0-9-]{20,}|"
    r"AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,})"
)
HOMEPATH = re.compile(r"[Cc]:[\\/]{1,2}Users[\\/]{1,2}\w+", re.IGNORECASE)


def tracked_json() -> list[str]:
    p = subprocess.run(
        ["git", "ls-files", "--", "command-center/hook-audit"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=60,
    )
    return [n for n in p.stdout.splitlines() if n.strip().endswith(".json")]


def main() -> int:
    out: dict[str, object] = {"controls": {}, "candidates": {}, "already_tracked": {}}

    # Detector controls FIRST. A silent scanner over a clean string proves nothing.
    out["controls"]["C1_homepath_detector_fires"] = bool(
        HOMEPATH.search(r"C:\Users\someone\.claude\hooks")
    )
    out["controls"]["C2_homepath_detector_silent"] = not HOMEPATH.search(
        "hooks/wire-check/check.py ran in 12 ms"
    )
    out["controls"]["C3_secret_detector_fires"] = bool(
        SECRETISH.search("AKIA" + "Q" * 16)
    )
    out["controls"]["C4_secret_detector_silent"] = not SECRETISH.search(
        "verdict=INERT-CONFIRMED wall_ms=123.5"
    )

    for name in CANDIDATES:
        fp = EVID / name
        text = fp.read_text(encoding="utf-8", errors="replace")
        out["candidates"][name] = {
            "bytes": len(text),
            "secretish_hits": len(SECRETISH.findall(text)),
            "homepath_hits": len(HOMEPATH.findall(text)),
            "parses_as_json": _parses(text),
        }

    for name in tracked_json():
        text = (REPO / name).read_text(encoding="utf-8", errors="replace")
        hp = len(HOMEPATH.findall(text))
        sk = len(SECRETISH.findall(text))
        if hp or sk:
            out["already_tracked"][name] = {"homepath_hits": hp, "secretish_hits": sk}

    out["already_tracked_files_with_homepath"] = len(out["already_tracked"])
    out["candidate_secretish_total"] = sum(
        int(v["secretish_hits"])  # type: ignore[index]
        for v in out["candidates"].values()  # type: ignore[union-attr]
    )
    (EVID / "I1-TRACK-PRECHECK.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8"
    )
    for k, v in out["controls"].items():  # type: ignore[union-attr]
        print(f"CONTROL {k} = {v}")
    for k, v in out["candidates"].items():  # type: ignore[union-attr]
        print(f"  {k}: {v}")
    print(
        f"\nalready-tracked evidence files carrying a home path: "
        f"{out['already_tracked_files_with_homepath']}"
    )
    print(
        f"credential-shaped strings in candidates: {out['candidate_secretish_total']}"
    )
    ok = all(out["controls"].values()) and out["candidate_secretish_total"] == 0  # type: ignore[union-attr]
    print(
        "SUCCESS:track-precheck no credential-shaped string in any candidate"
        if ok
        else "FAILED:track-precheck controls failed or a candidate carries a secret shape"
    )
    return 0 if ok else 1


def _parses(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
