"""Live measurement from frozen RES-0131 captures. No network."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SAMPLE = HERE / "captures" / "sample.json"
SOURCES = HERE / "captures" / "sources-index.json"
SHUFFLE_SEEDS = list(range(20260824, 20260845))

import local_score as LS  # noqa: E402
import spearman_alt as SA  # noqa: E402
import stats as ST  # noqa: E402

SENTINEL = (
    "SUCCESS:RES-0131 in the receipt AND a Spearman rank correlation over a "
    "named 30-package sample with a shuffle negative control"
)
QUESTION = (
    "Which of the signals used by the npm score, OpenSSF Scorecard, and "
    "Packagist quality ratings can be computed from the package bytes alone, "
    "offline, with no download counts and no GitHub API — and what is the "
    "measured rank correlation between that offline subset and the full online "
    "score on a sample of 30 real packages?"
)
ART_REL = (
    "command-center/research/marketplace-ecosystem/"
    "RES-0131-locally-computable-package-quality-score.json"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_sources() -> list[dict]:
    doc = json.loads(SOURCES.read_text(encoding="utf-8"))
    return list(doc.get("rails") or [])


def verify_source_rail(rail: dict) -> str | None:
    rel = str(rail.get("capture_path") or "")
    path = REPO / rel
    if not path.is_file():
        return f"missing:{rel}"
    got = sha256_file(path)
    want = str(rail.get("sha256") or "")
    if got != want:
        return f"sha-mismatch:{rail.get('id')}"
    status = int(rail.get("http_status") or 0)
    if status not in {200, 404}:
        return f"http:{rail.get('id')}:{status}"
    return None


def load_rows() -> list[dict]:
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    rows: list[dict] = []
    for item in sample.get("packages") or []:
        cap_rel = str(item["capture"])
        rec = json.loads((REPO / cap_rel).read_text(encoding="utf-8"))
        feat = rec["features"]
        npms = rec.get("npms") or {}
        off = LS.offline_score(feat)
        quality = float(rec.get("online_quality") if rec.get("online_quality") is not None else npms["quality"])
        final = float(rec.get("online_final") if rec.get("online_final") is not None else npms["final"])
        rows.append(
            {
                "name": rec.get("name") or item["name"],
                "version": rec.get("version") or item.get("version"),
                "offline_score": off,
                "stored_offline_score": float(rec.get("offline_score") or item["offline_score"]),
                "online_quality": quality,
                "online_final": final,
                "online_score_source": rec.get("online_score_source") or "npms.io",
                "tarball_sha256": rec.get("tarball_sha256") or item.get("tarball_sha256"),
                "capture": cap_rel,
                "features": feat,
                "offline_components": LS.offline_components(feat),
                "file_list_rail": LS.recompute_from_file_list(feat),
                "file_count": int(feat.get("file_count") or 0),
            }
        )
    return rows


def _file_list_agrees(feat: dict, rail: dict) -> dict:
    return {
        "has_changelog": bool(feat.get("has_changelog")) == bool(rail.get("has_changelog")),
        "has_security_md": bool(feat.get("has_security_md")) == bool(rail.get("has_security_md")),
        "has_lockfile": bool(feat.get("has_lockfile")) == bool(rail.get("has_lockfile")),
        "has_test_files": bool(feat.get("has_test_files")) == bool(rail.get("has_test_files")),
        "no_binary_artifacts": (int(feat.get("binary_artifact_count") or 0) == 0)
        == bool(rail.get("no_binary_artifacts")),
    }


def measure() -> dict:
    rows = load_rows()
    names = [r["name"] for r in rows]
    offline = [r["offline_score"] for r in rows]
    stored = [r["stored_offline_score"] for r in rows]
    quality = [r["online_quality"] for r in rows]
    final = [r["online_final"] for r in rows]
    rho_quality = ST.spearman(offline, quality)
    rho_final = ST.spearman(offline, final)
    rho_quality_alt = SA.spearman_alt(offline, quality)
    rho_final_alt = SA.spearman_alt(offline, final)
    shuf_final = ST.shuffle_rhos(offline, final, SHUFFLE_SEEDS)
    shuf_quality = ST.shuffle_rhos(offline, quality, SHUFFLE_SEEDS)
    med_final = ST.median([abs(x) for x in shuf_final])
    med_quality = ST.median([abs(x) for x in shuf_quality])
    identity_final = ST.spearman(offline, list(final))
    constructed = ST.spearman(sorted(offline), sorted(final))
    sources = load_sources()
    source_errors = [e for e in (verify_source_rail(r) for r in sources) if e]
    file_list_ok = []
    for r in rows:
        if r["file_count"] > 80:
            continue
        file_list_ok.append({"name": r["name"], **_file_list_agrees(r["features"], r["file_list_rail"])})
    stored_match = all(abs(a - b) < 1e-12 for a, b in zip(offline, stored))
    return {
        "n": len(rows),
        "names": names,
        "rows": rows,
        "rho_offline_vs_npms_quality": rho_quality,
        "rho_offline_vs_npms_final": rho_final,
        "rho_quality_alt": rho_quality_alt,
        "rho_final_alt": rho_final_alt,
        "alt_agrees": abs(rho_quality - rho_quality_alt) < 1e-9
        and abs(rho_final - rho_final_alt) < 1e-9,
        "shuffle_seeds": SHUFFLE_SEEDS,
        "shuffle_rho_final": shuf_final,
        "shuffle_rho_quality": shuf_quality,
        "shuffle_median_abs_rho_final": med_final,
        "shuffle_median_abs_rho_quality": med_quality,
        "identity_rho_final": identity_final,
        "constructed_sorted_rho_final": constructed,
        "shuffle_collapses": med_final < abs(rho_final) and med_final < 0.30,
        "identity_does_not_collapse": abs(identity_final - rho_final) < 1e-12,
        "source_errors": source_errors,
        "file_list_checks": file_list_ok,
        "file_list_all_ok": all(
            all(v is True for k, v in row.items() if k != "name") for row in file_list_ok
        ),
        "offline_not_copy_of_online": offline != final and offline != quality,
        "stored_offline_matches_recompute": stored_match,
        "quality_min": min(quality),
        "quality_max": max(quality),
        "final_min": min(final),
        "final_max": max(final),
        "offline_min": min(offline),
        "offline_max": max(offline),
    }
