#!/usr/bin/env python3
"""List recoverable browser session options (windows + tabs) for user pick.

Parses Chromium SNSS Session/Tabs files (best-effort URL/title extraction)
and Firefox sessionstore jsonlz4. Writes a pick-list JSON + markdown.
"""

from __future__ import annotations

import json
import re
import struct
import zlib
from datetime import datetime
from pathlib import Path
from typing import Any

HOME = Path.home()
OUT_DIR = HOME / ".crcp" / "cookie-bridge"
OUT_JSON = OUT_DIR / "session_options.json"
OUT_MD = OUT_DIR / "session_options.md"

URL_RE = re.compile(rb"https?://[^\x00-\x1f\x7f-\xff]{4,500}")
# Chromium often stores 16-bit length-prefixed UTF-16 or UTF-8 strings; also plain ASCII URLs.


def _unique_urls(blob: bytes, limit: int = 500) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for m in URL_RE.finditer(blob):
        try:
            u = m.group(0).decode("ascii", errors="ignore")
        except Exception:
            continue
        # strip trailing junk
        u = u.rstrip("\\'\"),];}>) \t")
        if len(u) < 12:
            continue
        # drop noise
        if any(
            x in u
            for x in (
                "chrome://",
                "edge://",
                "extension://",
                "chrome-extension://",
                "devtools://",
                "blob:",
            )
        ):
            continue
        if u in seen:
            continue
        seen.add(u)
        found.append(u)
        if len(found) >= limit:
            break
    return found


def _titles_near_urls(blob: bytes, urls: list[str]) -> dict[str, str]:
    """Best-effort: find short printable strings near URL occurrences as titles."""
    titles: dict[str, str] = {}
    text = blob.decode("latin-1", errors="ignore")
    for u in urls:
        idx = text.find(u)
        if idx < 0:
            continue
        window = text[max(0, idx - 200) : idx]
        # last printable run before URL
        cands = re.findall(r"[\w][\w \-\|\[\]\(\)\.:]{4,80}", window)
        if cands:
            titles[u] = cands[-1].strip()
    return titles


def parse_snss_file(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    urls = _unique_urls(data)
    titles = _titles_near_urls(data, urls[:80])
    # Heuristic window split: SNSS has window markers; count roughly by command types
    # Fallback: single window with all tabs if we cannot split cleanly
    windows: list[dict[str, Any]] = []
    if not urls:
        return {
            "path": str(path),
            "bytes": path.stat().st_size,
            "mtime": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
            "windows": [],
            "tab_count": 0,
            "url_count": 0,
        }

    # Group URLs into windows by large zero gaps in file positions
    positions = []
    for u in urls:
        positions.append((data.find(u.encode("ascii", errors="ignore")), u))
    positions = [(p, u) for p, u in positions if p >= 0]
    positions.sort()

    groups: list[list[str]] = []
    current: list[str] = []
    last_pos = -10**9
    for pos, u in positions:
        if current and pos - last_pos > 50_000 and len(current) >= 3:
            groups.append(current)
            current = []
        current.append(u)
        last_pos = pos
    if current:
        groups.append(current)

    if not groups:
        groups = [urls]

    for i, g in enumerate(groups, 1):
        # de-dupe preserve order
        seen = set()
        tabs = []
        for u in g:
            if u in seen:
                continue
            seen.add(u)
            tabs.append({"url": u, "title": titles.get(u)})
        windows.append({"window_index": i, "tab_count": len(tabs), "tabs": tabs})

    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "mtime": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
        "windows": windows,
        "tab_count": sum(w["tab_count"] for w in windows),
        "url_count": len(urls),
        "sample_hosts": sorted(
            {re.sub(r"^https?://([^/]+).*", r"\1", u) for u in urls}
        )[:40],
    }


def parse_firefox_session(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    # mozilla jsonlz4: magic mozLz40\0 + lz4 block
    try:
        import lz4.block  # type: ignore
    except ImportError:
        import subprocess, sys

        subprocess.check_call([sys.executable, "-m", "pip", "install", "lz4", "-q"])
        import lz4.block  # type: ignore

    if raw.startswith(b"mozLz40\0"):
        payload = lz4.block.decompress(raw[8:])
    else:
        try:
            payload = zlib.decompress(raw)
        except Exception:
            payload = raw
    data = json.loads(payload.decode("utf-8"))
    windows_out = []
    for i, win in enumerate(data.get("windows") or [], 1):
        tabs = []
        for tab in win.get("tabs") or []:
            entries = tab.get("entries") or []
            if not entries:
                continue
            last = entries[-1]
            tabs.append(
                {
                    "url": last.get("url"),
                    "title": last.get("title"),
                }
            )
        windows_out.append(
            {
                "window_index": i,
                "tab_count": len(tabs),
                "selected": win.get("selected"),
                "tabs": tabs,
            }
        )
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "mtime": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
        "windows": windows_out,
        "tab_count": sum(w["tab_count"] for w in windows_out),
        "url_count": sum(w["tab_count"] for w in windows_out),
    }


def collect_candidates() -> dict[str, Any]:
    roots = {
        "edge": HOME / r"AppData\Local\Microsoft\Edge\User Data\Default",
        "chrome": HOME / r"AppData\Local\Google\Chrome\User Data\Default",
        "comet": HOME / r"AppData\Local\Perplexity\Comet\User Data\Default",
        "firefox": HOME
        / r"AppData\Roaming\Mozilla\Firefox\Profiles\k4cy1nuq.default-release",
    }
    out: dict[str, Any] = {"generated_at": datetime.now().isoformat(timespec="seconds"), "options": []}
    option_id = 0

    for browser, root in roots.items():
        files: list[Path] = []
        if browser == "firefox":
            files = [
                p
                for p in [
                    root / "sessionstore.jsonlz4",
                    root / "sessionstore-backups" / "recovery.jsonlz4",
                    root / "sessionstore-backups" / "recovery.baklz4",
                    root / "sessionstore-backups" / "previous.jsonlz4",
                ]
                if p.is_file()
            ]
            # upgrades
            bak = root / "sessionstore-backups"
            if bak.is_dir():
                files.extend(sorted(bak.glob("upgrade.jsonlz4*"), key=lambda p: -p.stat().st_size)[:3])
        else:
            # all Session/Tabs under profile including nested/backups
            for p in root.rglob("*"):
                if not p.is_file():
                    continue
                if p.name.startswith("Session_") or p.name.startswith("Tabs_"):
                    if p.stat().st_size >= 20_000:
                        files.append(p)
            files = sorted(set(files), key=lambda p: -p.stat().st_size)[:12]

        for f in files:
            option_id += 1
            try:
                if browser == "firefox" or f.suffix.endswith("lz4") or "jsonlz4" in f.name:
                    parsed = parse_firefox_session(f)
                else:
                    parsed = parse_snss_file(f)
            except Exception as exc:
                parsed = {
                    "path": str(f),
                    "bytes": f.stat().st_size,
                    "error": f"{type(exc).__name__}: {exc}"[:200],
                    "windows": [],
                    "tab_count": 0,
                }
            opt = {
                "id": f"{browser[0].upper()}{option_id:02d}",
                "browser": browser,
                "file": str(f),
                "rel": str(f.relative_to(root)) if f.is_relative_to(root) else f.name,
                "bytes": parsed.get("bytes") or f.stat().st_size,
                "mtime": parsed.get("mtime"),
                "tab_count": parsed.get("tab_count", 0),
                "window_count": len(parsed.get("windows") or []),
                "sample_hosts": parsed.get("sample_hosts"),
                "windows": parsed.get("windows") or [],
                "error": parsed.get("error"),
            }
            out["options"].append(opt)

    # sort: browser, then tab_count desc
    out["options"].sort(key=lambda o: (o["browser"], -(o.get("tab_count") or 0), -o["bytes"]))
    # renumber ids stably per browser
    counters = {"edge": 0, "chrome": 0, "comet": 0, "firefox": 0}
    for o in out["options"]:
        counters[o["browser"]] = counters.get(o["browser"], 0) + 1
        prefix = {"edge": "E", "chrome": "C", "comet": "M", "firefox": "F"}[o["browser"]]
        o["id"] = f"{prefix}{counters[o['browser']]:02d}"
    return out


def to_markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Recoverable browser session options",
        "",
        f"Generated: {data['generated_at']}",
        "",
        "Reply with the option IDs you want restored, e.g. `E01, C02, M01, F01`.",
        "",
    ]
    by_browser: dict[str, list] = {}
    for o in data["options"]:
        by_browser.setdefault(o["browser"], []).append(o)

    for browser in ("edge", "chrome", "comet", "firefox"):
        opts = by_browser.get(browser) or []
        lines.append(f"## {browser.upper()} ({len(opts)} options)")
        lines.append("")
        if not opts:
            lines.append("_none_")
            lines.append("")
            continue
        for o in opts:
            lines.append(
                f"### `{o['id']}` — {o['tab_count']} tabs / {o['window_count']} windows — "
                f"{o['bytes']:,} bytes — {o.get('mtime')}"
            )
            lines.append(f"- file: `{o['rel']}`")
            if o.get("sample_hosts"):
                lines.append(f"- hosts: {', '.join(o['sample_hosts'][:15])}")
            if o.get("error"):
                lines.append(f"- ERROR: {o['error']}")
            for w in o.get("windows") or []:
                lines.append(
                    f"- **Window {w['window_index']}** ({w['tab_count']} tabs)"
                )
                for t in (w.get("tabs") or [])[:40]:
                    title = t.get("title") or ""
                    url = t.get("url") or ""
                    if title:
                        lines.append(f"  - {title} — {url}")
                    else:
                        lines.append(f"  - {url}")
                if (w.get("tab_count") or 0) > 40:
                    lines.append(f"  - … +{w['tab_count']-40} more tabs")
            lines.append("")
    return "\n".join(lines)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = collect_candidates()
    OUT_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")
    md = to_markdown(data)
    OUT_MD.write_text(md, encoding="utf-8")
    print(md)
    print(f"\n# wrote {OUT_MD}")
    print(f"# wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
