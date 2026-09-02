"""Live both-states (git cat-file) and egress-blocked (UNREACHABLE≠404) controls."""
from __future__ import annotations

from pathlib import Path

from blob import (
    REPO,
    fixture_git_repo,
    probe_git_repo,
    resolve_internal,
    shape_only_ok,
)
from extract import scan_docs
from fetch import (
    LocalOrigin,
    broken_fold_unreachable_into_wrong,
    fetch_unshare,
    fetch_with_retry,
)

LIVE_URL_CAP = 20


def both_states_internal() -> dict:
    with fixture_git_repo() as fx:
        good = resolve_internal(fx["root"], fx["rev"], fx["path"], fx["good_line"])
        bad = resolve_internal(fx["root"], fx["rev"], fx["path"], fx["bad_line"])
        missing = resolve_internal(fx["root"], fx["rev"], "no-such-tst-0255.md", 1)
        shape_good = shape_only_ok(fx["path"], fx["good_line"])
        shape_bad = shape_only_ok(fx["path"], fx["bad_line"])
        silent_on_good = good.get("classification") == "OK"
        fired_on_off_by_1000 = bad.get("classification") == "BEYOND-EOF"
        fired_on_missing = missing.get("classification") == "MISSING"
        blob_text_ok = (good.get("blob_line") or "") == fx["good_text"]
        shape_misses_off_by_1000 = bool(shape_bad) and fired_on_off_by_1000
        passed = (
            silent_on_good
            and fired_on_off_by_1000
            and fired_on_missing
            and blob_text_ok
            and shape_good is True
            and shape_misses_off_by_1000
        )
        return {
            "method": "git cat-file -p <rev>:<path> plus line-count",
            "fixture_rev": fx["rev"],
            "fixture_path": fx["path"],
            "fixture_line_count": fx["line_count"],
            "good_line": fx["good_line"],
            "bad_line": fx["bad_line"],
            "good": good,
            "off_by_1000": bad,
            "missing": missing,
            "silent_on_good": silent_on_good,
            "fired_on_off_by_1000": fired_on_off_by_1000,
            "fired_on_missing": fired_on_missing,
            "blob_text_ok": blob_text_ok,
            "shape_only_accepts_good": shape_good,
            "shape_only_accepts_off_by_1000": shape_bad,
            "shape_only_misses_off_by_1000": shape_misses_off_by_1000,
            "pass": passed,
        }


def egress_detector() -> dict:
    origin = LocalOrigin()
    port = origin.start()
    try:
        url_ok = f"http://127.0.0.1:{port}/ok"
        url_404 = f"http://127.0.0.1:{port}/missing"
        url_410 = f"http://127.0.0.1:{port}/gone"
        open_ok = fetch_with_retry(url_ok, attempts=1)
        open_404 = fetch_with_retry(url_404, attempts=1)
        open_410 = fetch_with_retry(url_410, attempts=1)
        blocked_404 = fetch_unshare(url_404)
        blocked_ok = fetch_unshare(url_ok)
        broken_on_block = broken_fold_unreachable_into_wrong(blocked_404)
        unblocked_404_wrong = open_404.get("classification") == "WRONG"
        unblocked_410_wrong = open_410.get("classification") == "WRONG"
        unblocked_ok = open_ok.get("classification") == "OK"
        blocked_is_unreach = blocked_404.get("classification") == "UNREACHABLE"
        blocked_not_wrong = blocked_404.get("classification") != "WRONG"
        blocked_ok_unreach = blocked_ok.get("classification") == "UNREACHABLE"
        broken_would_404 = broken_on_block == "WRONG"
        passed = (
            unblocked_ok
            and unblocked_404_wrong
            and unblocked_410_wrong
            and blocked_is_unreach
            and blocked_not_wrong
            and blocked_ok_unreach
            and broken_would_404
        )
        return {
            "method": "unshare -n around the same classifier",
            "url_ok": url_ok,
            "url_404": url_404,
            "url_410": url_410,
            "open_ok": open_ok,
            "open_404": open_404,
            "open_410": open_410,
            "blocked_404": blocked_404,
            "blocked_ok": blocked_ok,
            "unblocked_ok_is_OK": unblocked_ok,
            "unblocked_404_is_WRONG": unblocked_404_wrong,
            "unblocked_410_is_WRONG": unblocked_410_wrong,
            "blocked_404_is_UNREACHABLE": blocked_is_unreach,
            "blocked_404_is_not_WRONG": blocked_not_wrong,
            "blocked_ok_is_UNREACHABLE": blocked_ok_unreach,
            "broken_folder_reports_WRONG_on_block": broken_would_404,
            "pass": passed,
        }
    finally:
        origin.stop()


def live_scan() -> dict:
    git = probe_git_repo(REPO)
    scanned = scan_docs(REPO)
    sample_path = "command-center/OPTION-ID-RESOLUTION.md"
    sample = resolve_internal(REPO, "HEAD", sample_path, 1)
    internal = []
    unique_paths = []
    seen_p = set()
    for row in scanned["anchors"]:
        key = (row["path"], row["line"])
        if key in seen_p:
            continue
        seen_p.add(key)
        unique_paths.append(row)
    for row in unique_paths:
        resolved = resolve_internal(REPO, "HEAD", row["path"], row["line"])
        resolved["source"] = row["source"]
        resolved["raw"] = row["raw"]
        internal.append(resolved)
    url_rows = []
    seen_u = set()
    for row in scanned["urls"]:
        if row["url"] in seen_u:
            continue
        seen_u.add(row["url"])
        if len(url_rows) >= LIVE_URL_CAP:
            break
        fetched = fetch_with_retry(row["url"], attempts=2, timeout=2.0)
        fetched["source"] = row["source"]
        url_rows.append(fetched)
    classes_i = {}
    for row in internal:
        classes_i[row["classification"]] = classes_i.get(row["classification"], 0) + 1
    classes_u = {}
    for row in url_rows:
        classes_u[row["classification"]] = classes_u.get(row["classification"], 0) + 1
    wrong = [r["url"] for r in url_rows if r["classification"] == "WRONG"]
    ok_at_rev = [r for r in internal if r["classification"] == "OK"]
    return {
        "git": git,
        "catalog_inputs": scanned["catalog_inputs"],
        "catalog_docs_present": scanned["catalog_docs_present"],
        "missing_catalog_docs": scanned["missing_catalog_docs"],
        "scanned_file_count": scanned["scanned_file_count"],
        "scanned_files": [f["path"] for f in scanned["scanned_files"]],
        "anchor_count": scanned["anchor_count"],
        "url_count": scanned["url_count"],
        "internal": internal,
        "internal_class_counts": classes_i,
        "internal_ok_at_rev": len(ok_at_rev),
        "external": url_rows,
        "external_class_counts": classes_u,
        "external_wrong": wrong,
        "cat_file_sample": sample,
        "unique_internal": len(internal),
        "unique_external_checked": len(url_rows),
    }


def measure() -> dict:
    internal_ctrl = both_states_internal()
    egress_ctrl = egress_detector()
    live = live_scan()
    target_pass = (
        live["catalog_docs_present"]
        and live["git"]["inside"]
        and live["internal_ok_at_rev"] == live["unique_internal"]
        and live["unique_internal"] > 0
        and not live["external_wrong"]
        and internal_ctrl["pass"]
        and egress_ctrl["pass"]
    )
    return {
        "both_states": internal_ctrl,
        "egress": egress_ctrl,
        "live": live,
        "checker_pass": bool(internal_ctrl["pass"] and egress_ctrl["pass"]),
        "target_pass": target_pass,
        "target_verdict": "CONFIRMED" if target_pass else "REFUTED",
    }
