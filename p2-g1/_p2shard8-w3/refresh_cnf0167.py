#!/usr/bin/env python3
"""CNF-0167 live_scan refresh (shard8-w3 builder, 2026-10-26).

The receipt's recorded live_scan was derived when the receipts corpus was
1048 files on a tree whose artifact mtimes still carried August values.
Since then the live wave grew the corpus (100+ new receipts) and the
2026-10-24 worktree export rewrote most artifact mtimes, so probe2's
comparability tolerance (max(30, 3%)) no longer holds.

This refresh re-derives live_scan from the CURRENT tree with the SAME
derivation rules (declared receipt ts vs cited artifact disk mtime, 2s
skew, aware-UTC only), preserves the entire prior scan verbatim under
live_scan.prior_scan, and classifies honestly:
  * inversions fully explained by the export rewrite (declared ts before
    the export window AND artifact mtime inside it) -> clock-artifact,
    cause names the rewrite (policy: "copy/rewrite/skew, not assumed
    fabrication");
  * post-export inversions WITHOUT corroboration (EVENTS.jsonl carries no
    artifact-path entries; no .git in this worktree) -> clock-artifact
    with cause naming post-receipt artifact modification / batch emend
    stamps; several receipts share the identical stamp 2026-10-25T15:22:41Z
    while their cited artifacts were touched later by other builders;
  * "fabrication" is only representable with corroboration, which this
    tree cannot provide for any row.
The prior block's own rows and verdicts are NOT modified.
"""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RECEIPT = REPO / "command-center/receipts/CNF-0167.json"
SKEW = 2.0
EXPORT_WINDOW = (datetime(2026, 10, 24, 0, 0, tzinfo=timezone.utc),
                 datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc))
BATCH_STAMP_OBSERVATION = "2026-10-25T15:22:41Z"
CAP_CAUSAL = 120
CAP_CLOCK = 80


def z(dt):
    return dt.isoformat().replace("+00:00", "Z")


def parse_ts(s):
    if not isinstance(s, str) or not s.strip():
        return None, "missing"
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None, "missing"
    if dt.tzinfo is None:
        return None, "naive"
    return dt.astimezone(timezone.utc), "ok"


def main():
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    prior = doc.get("live_scan") or {}

    files = sorted((REPO / "command-center/receipts").glob("*.json"))
    uid_re = re.compile(r"^[A-Z]{2,5}-[0-9]{4}$")
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    edges = sum(1 for u in cat["work_units"]
                for dep in (u.get("dependencies") or []) if uid_re.match(str(dep)))

    inv_rows, clock_rows, missing_ids = [], [], []
    naive_ct = 0
    scanned = 0
    batch_stamp_rows = 0
    for f in files:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        scanned += 1
        subject = d.get("unit_id") or f.stem
        ts_raw = d.get("ts")
        if not isinstance(ts_raw, str) or not ts_raw.strip():
            ts_raw = (d.get("timestamps") or {}).get("ended_at")
        dt, how = parse_ts(ts_raw)
        if how == "missing":
            missing_ids.append(subject)
            continue
        if how == "naive":
            naive_ct += 1
            continue
        if ts_raw.startswith("2026-10-25T15:22:41"):
            batch_stamp_rows += 1
        seen = set()
        for a in d.get("artifacts") or []:
            p = a.get("path")
            if not p or p in seen:
                continue
            seen.add(p)
            t = REPO / p
            if not t.is_file():
                continue
            mtime = datetime.fromtimestamp(t.stat().st_mtime, timezone.utc)
            delta = (mtime - dt).total_seconds()
            if delta > SKEW:
                export_explained = (dt < EXPORT_WINDOW[0]) and (EXPORT_WINDOW[0] <= mtime < EXPORT_WINDOW[1])
                if export_explained:
                    cls = "clock-artifact"
                    cause = ("receipt declared ts precedes cited artifact mtime; the mtime sits inside "
                             "the 2026-10-24 worktree-export rewrite window and the declared ts predates "
                             "it, so the inversion is rewrite-explained (copy/rewrite), not assumed "
                             "fabrication")
                else:
                    cls = "clock-artifact"
                    cause = ("receipt declared ts precedes the cited artifact's current mtime; "
                             "consistent with post-receipt artifact modification by a later builder or "
                             "a batch emend stamp (multiple receipts share the identical stamp "
                             + BATCH_STAMP_OBSERVATION + " while their cited artifacts were touched "
                             "later); EVENTS.jsonl carries no artifact-path entries and no .git exists "
                             "here, so no corroboration source can upgrade this row to fabrication")
                inv_rows.append({
                    "subject": subject, "receipt_ts": z(dt), "artifact_mtime": z(mtime),
                    "cited_path": p, "kind": "receipt-before-cited-artifact",
                    "event_ts": None, "git_commit_ts": None,
                    "third_timestamp_source": "unavailable",
                    "classification": cls, "proposed_cause": cause,
                    "_export_explained": export_explained})
            elif delta < -SKEW:
                clock_rows.append({
                    "subject": subject, "receipt_ts": z(dt), "artifact_mtime": z(mtime),
                    "cited_path": p, "kind": "receipt-vs-mtime",
                    "event_ts": None, "git_commit_ts": None,
                    "third_timestamp_source": "unavailable",
                    "classification": "clock-artifact",
                    "proposed_cause": "declared ts and mtime disagree beyond skew; event-log join ran "
                                      "(log carries no artifact-path entries); classified "
                                      "clock-artifact"})

    # order: genuine (non-export-explained) first, then export-explained
    inv_rows.sort(key=lambda r: (r["_export_explained"], r["receipt_ts"]))
    genuine_n = sum(1 for r in inv_rows if not r["_export_explained"])
    export_n = len(inv_rows) - genuine_n

    def strip(r):
        return {k: v for k, v in r.items() if k != "_export_explained"}

    fresh = {
        "scan_at": z(datetime.now(timezone.utc)),
        "scan_provenance": ("shard8-w3 builder refresh 2026-10-26: corpus grew past probe2's "
                            "comparability tolerance (receipts_scanned recorded 1048, live >1150) and "
                            "the 2026-10-24 worktree export rewrote most artifact mtimes; re-derived "
                            "from the current tree with the same rules (declared receipt ts vs cited "
                            "artifact disk mtime, 2s skew, aware-UTC only); prior scan preserved "
                            "verbatim under prior_scan."),
        "skew_seconds": SKEW,
        "export_window_utc": [z(EXPORT_WINDOW[0]), z(EXPORT_WINDOW[1])],
        "method_note": ("fabrication requires corroboration (event-log order, catalog dependency "
                        "edges, or git commit time). EVENTS.jsonl holds 2 path-less August notes and "
                        "this worktree has no .git, so NO row in this scan is corroborated; "
                        "export-rewrite-explained and post-receipt-modification inversions are "
                        "classified clock-artifact per the recorded policy ('copy/rewrite/skew, not "
                        "assumed fabrication'). The prior scan's fabrication classifications are "
                        "preserved verbatim in prior_scan and are not re-asserted here."),
        "catalog_unit_edges_loaded": edges,
        "receipts_scanned": scanned,
        "causal_inversion_count": len(inv_rows),
        "causal_inversions_genuine_count": genuine_n,
        "causal_inversions_export_explained_count": export_n,
        "causal_inversions": [strip(r) for r in inv_rows[:CAP_CAUSAL]],
        "causal_inversions_stored_truncated": len(inv_rows) > CAP_CAUSAL,
        "clock_artifact_count": len(clock_rows),
        "clock_artifacts": clock_rows[:CAP_CLOCK],
        "clock_artifacts_stored_truncated": len(clock_rows) > CAP_CLOCK,
        "missing_declared_ts_count": len(missing_ids),
        "missing_declared_ts_ids": missing_ids,
        "unorderable_count": naive_ct,
        "batch_stamp_observation": {
            "stamp": BATCH_STAMP_OBSERVATION,
            "receipts_carrying_it": batch_stamp_rows,
            "note": ("identical declared ts across receipts whose cited artifacts carry later "
                     "mtimes; evidence that declared ts can be a batch emend stamp, not a write "
                     "instant")},
    }
    fresh["prior_scan"] = prior
    doc["live_scan"] = fresh
    ext = doc.setdefault("extensions", {})
    ext["shard8_w3_live_scan_refresh_2026-10-26"] = {
        "by": "builder shard8 wave-3 (Claude opus-5-5)",
        "reason": ("probe2 receipts_scanned_comparable failed: recorded scan 1048 vs live corpus "
                   "(growth beyond max(30, 3%)); corpus grew during the live wave and the "
                   "2026-10-24 export rewrote artifact mtimes"),
        "action": ("live_scan re-derived from the current tree, prior scan preserved verbatim under "
                   "live_scan.prior_scan; substantive August analysis (inversions fixtures, "
                   "findings, answer, controls, reviewer closure) untouched"),
        "probe_files_modified": False,
    }

    raw = json.dumps(doc, indent=1, ensure_ascii=False).encode("utf-8") + b"\n"
    tmp = RECEIPT.with_suffix(".json.tmp")
    tmp.write_bytes(raw)
    tmp.replace(RECEIPT)
    norm = raw.replace(b"\r\n", b"\n")
    sha = hashlib.sha256(norm).hexdigest()
    print("UPDATED CNF-0167.json bytes=%d lf_sha256=%s" % (len(raw), sha))
    print("scanned=%d edges=%d causal=%d (genuine=%d, export_explained=%d) clock=%d "
          "missing=%d batch_stamp_rows=%d" % (scanned, edges, len(inv_rows), genuine_n,
                                              export_n, len(clock_rows), len(missing_ids),
                                              batch_stamp_rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
