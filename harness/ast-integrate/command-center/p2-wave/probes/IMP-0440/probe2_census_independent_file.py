#!/usr/bin/env python3
"""Probe 2: independent three-route on a DIFFERENT file + plant-one census.

Reviewer path: raw ``git cat-file`` / ``git show`` / ``git archive`` via
subprocess. Does not import three_route.py. Then checks blob_bytes matches
the independent cat-file reading.

Census: zero remaining provenance prescriptions, with a plant-one control.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MG = REPO / "tools" / "measure-guard"
sys.path.insert(0, str(MG))

import archive_census as C  # noqa: E402
import blobread as B  # noqa: E402
import crlf_export_repo as F  # noqa: E402

OUT = HERE / "probe2-census-independent-file.raw.json"
ART = REPO / "command-center/receipts/IMP-0440.json"
SENTINEL = "SENTINEL:IMP-0440:BLOB-HELPER-SINGLE-SOURCE"
CRLF = b"\r\n"


def _fail(msg: str, payload: dict | None = None) -> int:
    if payload:
        OUT.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2, default=str)[:4000])
    print(f"FAILED:IMP-0440-probe2 {msg}")
    return 1


def _git(repo: Path, *args: str) -> bytes:
    r = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        env=B.git_env(),
        check=False,
    )
    if r.returncode != 0:
        err = (r.stderr or b"").decode("utf-8", "replace").strip()
        raise RuntimeError(f"git {' '.join(args)} rc={r.returncode}: {err}")
    return r.stdout


def independent_three_route(repo: Path, path: str, rev: str = "HEAD") -> dict:
    """Raw git only. Not three_route.py and not blob_bytes for the route bytes."""
    cat = _git(repo, "cat-file", "-p", f"{rev}:{path}")
    show = _git(repo, "show", f"{rev}:{path}")
    with tempfile.TemporaryDirectory(prefix="imp0440-p2arch-") as td:
        tarp = Path(td) / "a.tar"
        _git(repo, "archive", "-o", str(tarp), rev, "--", path)
        with tarfile.open(tarp) as tf:
            fh = tf.extractfile(tf.getmember(path))
            arch = fh.read() if fh else b""
    helper = B.blob_bytes(rev, path, repo=repo)
    norm = [v.replace(CRLF, b"\n") for v in (arch, cat, show)]
    return {
        "target": path,
        "reader": "independent git cat-file / show / archive (not three_route.py)",
        "routes": {
            "git archive + tar -x": {"bytes": len(arch), "crlf": arch.count(CRLF)},
            "git cat-file -p": {"bytes": len(cat), "crlf": cat.count(CRLF)},
            "git show <rev>:<path>": {"bytes": len(show), "crlf": show.count(CRLF)},
        },
        "archive_differs_from_blob": arch != cat,
        "cat_file_equals_show": cat == show,
        "helper_equals_independent_cat_file": helper == cat,
        "identical_after_lf_normalisation": bool(norm[0])
        and all(n == norm[0] for n in norm),
        "known_body_match": helper == F.BETA_BODY,
    }


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return _fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"self-declared:{st}")
    if SENTINEL not in text:
        return _fail("sentinel-absent")

    with tempfile.TemporaryDirectory(prefix="imp0440-p2-") as td:
        info = F.make_crlf_export_repo(Path(td) / "repo")
        routes = independent_three_route(info["root"], F.BETA, "HEAD")

    live = C.census()
    ctrl = C.plant_one_control()
    remaining = live["provenance_prescriptions_remaining"]

    payload = {
        "probe": "probe2-census-independent-file",
        "unit_id": "IMP-0440",
        "file": F.BETA,
        "different_file_from_probe1": F.BETA != F.ALPHA,
        "three_route": routes,
        "census": {
            "total_hits": live["total_hits"],
            "mentions": live["mentions_use_vs_mention"],
            "data_files": live["data_files_not_classifiable_as_prescriptions"],
            "real_invocations": live["real_invocations"],
            "packaging": len(live["legitimate_whole_tree_packaging"]),
            "detector_fixtures": len(live["detector_fixtures_wrong_recipe"]),
            "provenance_prescriptions_remaining": remaining,
        },
        "plant_one": {
            "found_plant": ctrl["found_plant"],
            "silent_after_removal": ctrl["silent_after_removal"],
            "remaining_after": ctrl["remaining_after"],
        },
        "pass": True,
    }
    if F.BETA == F.ALPHA:
        payload["pass"] = False
        return _fail("probe2 file is not different from probe1", payload)
    if not (
        routes["archive_differs_from_blob"]
        and routes["cat_file_equals_show"]
        and routes["helper_equals_independent_cat_file"]
        and routes["identical_after_lf_normalisation"]
        and routes["known_body_match"]
        and routes["routes"]["git archive + tar -x"]["crlf"] > 0
        and routes["routes"]["git cat-file -p"]["crlf"] == 0
    ):
        payload["pass"] = False
        return _fail("independent three-route failed", payload)
    if remaining:
        payload["pass"] = False
        return _fail("provenance prescriptions remain", payload)
    if not ctrl["found_plant"] or not ctrl["silent_after_removal"]:
        payload["pass"] = False
        return _fail("plant-one control failed", payload)

    OUT.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, default=str))
    print(
        f"file={F.BETA} remaining={len(remaining)} planted_found={ctrl['found_plant']} "
        f"silent={ctrl['silent_after_removal']}"
    )
    print("SUCCESS:IMP-0440-probe2 independent three-route on tools/beta.py and plant-one census")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
