#!/usr/bin/env python3
"""fb_timeline -- read the owner's OWN Facebook timeline posts into the corpus.

Instagram exposes ``get_recent_posts`` (the owner's own posts) through a private
API. Facebook has **no equivalent personal-profile post API** for an arbitrary
app, so this is the honest FB counterpart. It offers the two rails that actually
work, and is explicit about what each can and cannot see:

RAIL 1 -- Meta "Download Your Information" (DYI) export  [PRIMARY, chosen]
  * Sees: EVERY post you authored that Meta still retains, full text, structured
    JSON, no scraping, no ToS risk. This is the rail the writing-corpus pipeline
    was designed around (``isolate_facebook.py``).
  * Cannot see: posts you deleted, and (per Meta's own help text) possibly some
    very early history -- survivorship gaps, not parser bugs.
  * Owner action: request the export (Accounts Centre -> Download Your
    Information -> Posts -> JSON), then point ``--dyi`` at the zip or folder.

RAIL 2 -- Graph API ``/me/posts`` with a USER token  [SECONDARY, live, LIMITED]
  * Sees: only what Meta's Graph API still returns for a personal profile with
    the token you supply -- in practice recent/app-scoped posts, NOT your full
    historical timeline. Meta restricted ``user_posts`` reads years ago.
  * Owner action: generate a short-lived User token with the ``user_posts``
    scope in the Graph API Explorer on your own dev app, export it as
    ``FB_USER_TOKEN``. No password is ever handled here.

Both rails emit the SAME corpus JSONL shape as the other sources
(``{"ts","source":"facebook","kind","url","text"}``) so ``build_corpus.py`` folds
them in unchanged.

Meta DYI JSON is frequently double-encoded (latin-1 mojibake). This module
repairs it AFTER ``json.loads`` and only when a detector says a string is
actually mojibake'd -- a blind repair corrupts already-correct text.

Usage::

    python fb_timeline.py dyi  <export.zip|dir> [--out DIR] [--min-chars N]
    python fb_timeline.py graph [--out DIR] [--limit N]   # needs FB_USER_TOKEN
"""

from __future__ import annotations

import argparse
import glob
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

GRAPH_VERSION = os.environ.get("FB_GRAPH_VERSION", "v21.0")
GRAPH_ROOT = "https://graph.facebook.com"
DEFAULT_MIN_CHARS = 1  # keep every non-empty post; the corpus builder tiers later

# DYI post files have drifted across export layouts; glob every known root.
_DYI_GLOBS = (
    "**/your_posts*.json",
    "**/your_posts/*.json",
    "**/posts/your_posts*.json",
    "**/your_activity_across_facebook/posts/*.json",
    "**/your_facebook_activity/posts/*.json",
    "**/posts/profile_posts*.json",
)


# --------------------------------------------------------------------------- #
# mojibake repair (detector-gated -- never repair already-correct text)
# --------------------------------------------------------------------------- #
_MOJIBAKE_MARKERS = ("Ã", "Â", "â\x80", "Ð", "Ñ", "\xc3\x83")


def _looks_mojibake(s: str) -> bool:
    """True only if `s` shows the tell-tale latin-1/utf-8 double-encode markers."""
    return any(m in s for m in _MOJIBAKE_MARKERS)


def repair_mojibake(s: str) -> str:
    """Repair a double-encoded string, but ONLY when it looks mojibake'd.

    Meta writes UTF-8 bytes that were mis-read as latin-1 and re-encoded, so the
    inverse is ``encode('latin-1').decode('utf-8')``. Guarded by a detector and a
    round-trip check so a correct string is returned untouched.
    """
    if not isinstance(s, str) or not _looks_mojibake(s):
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


# --------------------------------------------------------------------------- #
# DYI rail
# --------------------------------------------------------------------------- #
def _iter_dyi_files(root: str):
    """Yield (name, raw_bytes) for every owner-post JSON in a zip or directory."""
    if zipfile.is_zipfile(root):
        with zipfile.ZipFile(root) as zf:
            for info in zf.infolist():
                low = info.filename.lower()
                if low.endswith(".json") and (
                    "your_posts" in low or "profile_posts" in low
                ):
                    yield info.filename, zf.read(info.filename)
        return
    if os.path.isdir(root):
        seen: set[str] = set()
        for pattern in _DYI_GLOBS:
            for path in glob.glob(os.path.join(root, pattern), recursive=True):
                if path not in seen:
                    seen.add(path)
                    with open(path, "rb") as fh:
                        yield path, fh.read()
        return
    # A single JSON file.
    with open(root, "rb") as fh:
        yield root, fh.read()


def _post_records(obj) -> list:
    """Normalize the several DYI post container shapes into a flat list."""
    if isinstance(obj, dict):
        for key in ("your_posts_v2", "your_posts", "posts", "profile_posts_v2"):
            if isinstance(obj.get(key), list):
                return obj[key]
        return []
    return obj if isinstance(obj, list) else []


def _extract_text(post: dict) -> str:
    """Pull the owner's authored prose out of one DYI post record."""
    parts: list[str] = []
    for item in post.get("data") or []:
        if isinstance(item, dict) and isinstance(item.get("post"), str):
            parts.append(item["post"])
    # Some records carry the body only in the title (e.g. status updates).
    if not parts and isinstance(post.get("title"), str) and "\n" in post["title"]:
        parts.append(post["title"])
    return repair_mojibake("\n".join(p for p in parts if p).strip())


def parse_dyi(root: str, min_chars: int = DEFAULT_MIN_CHARS) -> list[dict]:
    """Extract the owner's own posts from a DYI export into corpus rows."""
    rows: list[dict] = []
    for _name, raw in _iter_dyi_files(root):
        try:
            obj = json.loads(raw.decode("utf-8", "replace"))
        except json.JSONDecodeError:
            continue
        for post in _post_records(obj):
            if not isinstance(post, dict):
                continue
            text = _extract_text(post)
            if len(text) < min_chars:
                continue
            ts = post.get("timestamp")
            rows.append(
                {
                    "ts": _ts19(ts),
                    "source": "facebook",
                    "kind": "post",
                    "url": "",
                    "text": text,
                }
            )
    rows.sort(key=lambda r: r["ts"])
    return rows


# --------------------------------------------------------------------------- #
# Graph rail
# --------------------------------------------------------------------------- #
def _graph_get(path: str, params: dict) -> dict:
    url = f"{GRAPH_ROOT}/{GRAPH_VERSION}/{path}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "social-hub/fb_timeline"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310 - https graph.facebook.com
        return json.loads(resp.read().decode("utf-8", "replace"))


def fetch_graph_feed(token: str, limit: int = 100, max_pages: int = 50) -> list[dict]:
    """Fetch /me/posts with a user token. Returns whatever Graph still permits.

    ``/me/posts`` + ``user_posts`` is the documented read edge and returns posts the
    user created on their timeline (and posts they are tagged in). HONEST LIMIT:
    Meta warns an unauthorised feed returns an empty array, so completeness is NOT
    guaranteed -- use the DYI rail when you need every post.
    """
    rows: list[dict] = []
    params = {
        "fields": "id,message,created_time,permalink_url,type",
        "limit": str(limit),
        "access_token": token,
    }
    path = "me/posts"
    for _ in range(max_pages):
        data = _graph_get(path, params)
        for post in data.get("data", []):
            msg = repair_mojibake(post.get("message") or "")
            if not msg.strip():
                continue
            rows.append(
                {
                    "ts": (post.get("created_time") or "").replace("T", " ")[:19],
                    "source": "facebook",
                    "kind": "post",
                    "url": post.get("permalink_url") or "",
                    "text": msg,
                }
            )
        nxt = (data.get("paging") or {}).get("next")
        if not nxt:
            break
        # The `next` cursor already carries fields+token; call it directly.
        parsed = urllib.parse.urlparse(nxt)
        path = parsed.path.split(f"/{GRAPH_VERSION}/", 1)[-1].lstrip("/")
        params = dict(urllib.parse.parse_qsl(parsed.query))
    rows.sort(key=lambda r: r["ts"])
    return rows


# --------------------------------------------------------------------------- #
# shared output
# --------------------------------------------------------------------------- #
def _ts19(ts) -> str:
    """Best-effort 19-char timestamp from a unix int or an ISO string."""
    if isinstance(ts, (int, float)) and ts > 0:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
    if isinstance(ts, str) and ts:
        return ts.replace("T", " ")[:19]
    return ""


def write_corpus(rows: list[dict], out_dir: str, stem: str = "facebook_posts") -> dict:
    """Write JSONL + a plain-text view; return a small stats dict (no bodies)."""
    os.makedirs(out_dir, exist_ok=True)
    jsonl = os.path.join(out_dir, f"{stem}.jsonl")
    txt = os.path.join(out_dir, f"{stem}.txt")
    with io.open(jsonl, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    with io.open(txt, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            head = f"[{row['ts']}]" + (f" ({row['url']})" if row["url"] else "")
            fh.write(f"{head}\n{row['text']}\n\n")
    words = sum(len(r["text"].split()) for r in rows)
    return {
        "posts": len(rows),
        "words": words,
        "jsonl": jsonl,
        "txt": txt,
        "oldest": rows[0]["ts"] if rows else None,
        "newest": rows[-1]["ts"] if rows else None,
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Read the owner's own FB posts.")
    sub = ap.add_subparsers(dest="rail", required=True)

    d = sub.add_parser("dyi", help="parse a Meta DYI export (zip or dir)")
    d.add_argument("path", help="the DYI .zip or the unzipped folder")
    d.add_argument("--out", default=".", help="output dir (default: cwd)")
    d.add_argument("--min-chars", type=int, default=DEFAULT_MIN_CHARS)

    g = sub.add_parser("graph", help="fetch /me/posts via a FB_USER_TOKEN")
    g.add_argument("--out", default=".", help="output dir (default: cwd)")
    g.add_argument("--limit", type=int, default=100)

    args = ap.parse_args(argv)

    if args.rail == "dyi":
        if not os.path.exists(args.path):
            print(f"FAILED:fb-timeline path not found: {args.path}")
            return 1
        rows = parse_dyi(args.path, args.min_chars)
    else:
        token = os.environ.get("FB_USER_TOKEN")
        if not token:
            print("FAILED:fb-timeline FB_USER_TOKEN is not set (see the docstring)")
            return 1
        try:
            rows = fetch_graph_feed(token, args.limit)
        except (urllib.error.URLError, ValueError) as exc:
            print(f"FAILED:fb-timeline graph error: {exc}")
            return 1

    stats = write_corpus(rows, args.out)
    print(json.dumps(stats, ensure_ascii=False))
    print(f"SUCCESS:fb-timeline {stats['posts']} posts -> {stats['jsonl']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
