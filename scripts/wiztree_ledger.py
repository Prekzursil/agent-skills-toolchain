#!/usr/bin/env python3
"""
wiztree_ledger.py — durable decision ledger overlay for the disk-hygiene rule.

Problem this fixes: wiztree_analyze.py's DECISIONS-PENDING report is regenerated
FRESH every weekly run, so an un-actioned item silently reappears with no memory,
and an explicit "no" (declined) is forgotten and gets re-asked forever.

This script UPSERTS the analyzer's JSON-sidecar candidates (REVIEW-category top
files/folders) into a stable ledger keyed by content (category + path + rounded
size), never rewriting existing decisions. States: pending / approved / done /
declined / snoozed / expired. A declined item is a TOMBSTONE — it is never
re-surfaced as a new pending item again (fail-closed = keep the file / do nothing
forever, not "ask again next week").

Usage:
  python wiztree_ledger.py upsert  <analysis.json> [--ledger <ledger.json>]
  python wiztree_ledger.py pending [--ledger <ledger.json>]           # print open items
  python wiztree_ledger.py decide  <id> <approved|declined|snoozed> [--reason TEXT] [--days N] [--ledger <ledger.json>]
  python wiztree_ledger.py done    <id> --freed-bytes N [--ledger <ledger.json>]
"""
import json, sys, os, hashlib, argparse, datetime

DEFAULT_LEDGER = r"D:\wiztree-reports\disk-decisions.json"

def load(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"items": {}}

def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.replace(tmp, path)  # atomic on the same volume

def stable_id(category, path_, size):
    # Size rounded to a bucket so a few bytes of drift (log rotation, etc.) doesn't
    # mint a new id every week for what is obviously the same candidate.
    bucket = size // (50 * 1024 * 1024)  # 50 MB buckets
    raw = f"{category}|{path_.lower()}|{bucket}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

def now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")

# NEVER propose these as deletion candidates — OS-managed, in-use, or structurally
# required. Proposing pagefile.sys or $MFT would be actively harmful advice.
NEVER_PROPOSE = (
    r"\pagefile.sys", r"\hiberfil.sys", r"\swapfile.sys", r"\$mft", r"\$recycle.bin",
    r"c:\windows", r"\system volume information", r"\programdata\microsoft\windows\containers",
    r"\config.msi", r"\bootmgr", r"\recovery",
)

def is_excluded(path_):
    p = path_.lower()
    return any(tok in p for tok in NEVER_PROPOSE)

def drop_ancestors(entries):
    """Keep only the most specific path in any parent/child chain.

    WizTree reports aggregate folder sizes, so AppData(279GB) > AppData\\Local(247GB) >
    Packages(99GB) > ...\\LocalState(95GB) > ext4.vhdx(95GB) are all the SAME bytes.
    Summing them fabricates a ~3TB 'reclaimable' number on a 953GB disk. Keeping only
    the deepest entry per chain makes the total meaningful and the candidate actionable.
    entries: list of (category, path, size). Returns the filtered list.
    """
    paths = sorted({e[1].rstrip("\\").lower() for e in entries if e[1][1:2] == ":"}, key=len, reverse=True)
    redundant = set()
    for i, parent in enumerate(paths):
        for child in paths[:i]:                      # only strictly longer paths
            if child.startswith(parent + "\\"):
                redundant.add(parent)
                break
    return [e for e in entries if e[1].rstrip("\\").lower() not in redundant]

def cmd_upsert(args):
    ledger = load(args.ledger)
    with open(args.analysis, "r", encoding="utf-8") as f:
        analysis = json.load(f)
    added = refreshed = tombstoned_skip = 0
    candidates = []
    for size, path_ in analysis.get("top_files", []):
        candidates.append(("large-file", path_, size))
    for size, path_ in analysis.get("top_folders", []):
        candidates.append(("large-folder", path_, size))
    # Drop OS-critical paths, then collapse parent/child chains to the deepest entry.
    candidates = [c for c in candidates if not is_excluded(c[1])]
    candidates = drop_ancestors(candidates)
    # Category rollups are summaries, NOT separately-reclaimable bytes (they overlap the
    # file/folder entries above), so they are tracked with a distinct category prefix and
    # excluded from the reclaimable total in cmd_pending.
    for cat, meta in analysis.get("categories", {}).items():
        if meta.get("autonomy") == "REVIEW" and meta.get("bytes", 0) > 0:
            candidates.append((f"summary:{cat}", cat, meta["bytes"]))

    for category, path_, size in candidates:
        cid = stable_id(category, path_, size)
        existing = ledger["items"].get(cid)
        if existing is None:
            ledger["items"][cid] = {
                "id": cid, "category": category, "path": path_, "bytes": size,
                "state": "pending", "created_at": now_iso(), "last_surfaced_at": now_iso(),
                "decided_at": None, "decided_reason": None, "snooze_until": None,
            }
            added += 1
        elif existing["state"] == "declined":
            tombstoned_skip += 1  # never resurrect a "no"
        elif existing["state"] in ("pending", "snoozed"):
            snooze_until = existing.get("snooze_until")
            if snooze_until and snooze_until > now_iso()[:10]:
                pass  # still snoozed, don't bump back to visible-pending
            else:
                existing["state"] = "pending"
                existing["last_surfaced_at"] = now_iso()
                existing["bytes"] = size  # refresh size in case it grew/shrank
            refreshed += 1
        # approved / done items are left alone (their own flow owns them)
    save(args.ledger, ledger)
    print(f"UPSERT added={added} refreshed={refreshed} declined_skipped={tombstoned_skip} "
          f"total={len(ledger['items'])}")

def cmd_pending(args):
    ledger = load(args.ledger)
    items = [v for v in ledger["items"].values() if v["state"] in ("pending",)]
    items.sort(key=lambda v: -v["bytes"])
    if not items:
        print("PENDING=0")
        return
    # Only real paths count toward the total; "summary:*" rollups overlap them.
    total = sum(v["bytes"] for v in items if not v["category"].startswith("summary:"))
    print(f"PENDING={len(items)}  RECLAIMABLE={total/1024**3:.2f}GB (distinct paths; summaries excluded)")
    for v in items[:40]:
        print(f"  {v['bytes']/1024**3:8.2f}GB  [{v['id']}]  {v['category']:<20}  {v['path']}")
    declined = [v for v in ledger["items"].values() if v["state"] == "declined"]
    print(f"(declined/tombstoned, never re-asked: {len(declined)})")

def cmd_decide(args):
    ledger = load(args.ledger)
    item = ledger["items"].get(args.id)
    if not item:
        print(f"NOT_FOUND {args.id}"); sys.exit(1)
    item["state"] = args.state
    item["decided_at"] = now_iso()
    item["decided_reason"] = args.reason
    if args.state == "snoozed" and args.days:
        item["snooze_until"] = (datetime.date.today() + datetime.timedelta(days=args.days)).isoformat()
    save(args.ledger, ledger)
    print(f"DECIDED {args.id} -> {args.state}")

def cmd_done(args):
    ledger = load(args.ledger)
    item = ledger["items"].get(args.id)
    if not item:
        print(f"NOT_FOUND {args.id}"); sys.exit(1)
    item["state"] = "done"
    item["decided_at"] = now_iso()
    item["freed_bytes"] = args.freed_bytes
    save(args.ledger, ledger)
    print(f"DONE {args.id} freed={args.freed_bytes/1024**3:.2f}GB")

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("upsert"); p.add_argument("analysis"); p.add_argument("--ledger", default=DEFAULT_LEDGER)
    p = sub.add_parser("pending"); p.add_argument("--ledger", default=DEFAULT_LEDGER)
    p = sub.add_parser("decide"); p.add_argument("id"); p.add_argument("state", choices=["approved","declined","snoozed","pending"])
    p.add_argument("--reason", default=None); p.add_argument("--days", type=int, default=None); p.add_argument("--ledger", default=DEFAULT_LEDGER)
    p = sub.add_parser("done"); p.add_argument("id"); p.add_argument("--freed-bytes", type=int, required=True); p.add_argument("--ledger", default=DEFAULT_LEDGER)

    args = ap.parse_args()
    {"upsert": cmd_upsert, "pending": cmd_pending, "decide": cmd_decide, "done": cmd_done}[args.cmd](args)

if __name__ == "__main__":
    main()
