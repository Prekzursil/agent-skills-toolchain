#!/usr/bin/env python3
"""Quick health/freshness check for SWFOC reference sources.

Usage:
  python3 scripts/check_sources.py
  python3 scripts/check_sources.py --only-errors
  python3 scripts/check_sources.py --filter steamcommunity.com
"""

from __future__ import annotations

import argparse
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    name: str
    url: str
    tier: str


SOURCES = [
    Source("Petroglyph mod support", "https://www.petroglyphgames.com/eawmodtool/", "official"),
    Source("Debug kit", "https://www.petroglyphgames.com/eawmodtool/EAW_FOC_Debug_Kit_64.zip", "official"),
    Source("Workshop uploader", "https://www.petroglyphgames.com/eawmodtool/eaw_workshop_uploader.zip", "official"),
    Source("Terrain editor", "https://www.petroglyphgames.com/eawmodtool/EAW_Terrain_Editor_b.zip", "official"),
    Source("FOC shaders", "https://www.petroglyphgames.com/eawmodtool/foc_shaders.zip", "official"),
    Source("Petrolution tools", "https://modtools.petrolution.net/", "docs"),
    Source("Creating a mod", "https://modtools.petrolution.net/articles/Creating_A_Mod", "docs"),
    Source("Formats", "https://modtools.petrolution.net/docs/Formats", "docs"),
    Source("Steam allnews", "https://steamcommunity.com/app/32470/allnews/", "official"),
    Source("2024 patch", "https://steamcommunity.com/games/32470/announcements/detail/4551542220607036511", "official"),
    Source("2023 patch", "https://steamcommunity.com/games/32470/announcements/detail/5455609499987684897", "official"),
    Source("Steam modding guide", "https://steamcommunity.com/sharedfiles/filedetails/?id=2812662575", "community"),
    Source("Revora XML guide", "https://forums.revora.net/topic/109328-eaw-coding-tutorial-coding-in-xml-for-dummies/", "community"),
    Source("ModDB beginner tutorial", "https://www.moddb.com/games/star-wars-empire-at-war/tutorials/beginners-tutorial-for-modding-empire-at-war-forces-of-corruption", "community"),
]


def fetch_headers(url: str, timeout: int = 20) -> tuple[str, dict[str, str]]:
    ctx = ssl.create_default_context()
    headers = {"User-Agent": "swfoc-modding-source-check/1.0"}
    req = urllib.request.Request(url, method="HEAD", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return str(resp.status), {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as exc:
        # Some hosts block HEAD. Fall back to GET for headers.
        if exc.code not in {403, 405}:
            return str(exc.code), {k.lower(): v for k, v in exc.headers.items()}
        req = urllib.request.Request(url, method="GET", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return str(resp.status), {k.lower(): v for k, v in resp.headers.items()}
        except urllib.error.HTTPError as get_exc:
            return str(get_exc.code), {k.lower(): v for k, v in get_exc.headers.items()}
    except Exception as exc:  # noqa: BLE001
        return f"ERR:{type(exc).__name__}", {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check SWFOC source URL health and freshness headers")
    parser.add_argument("--only-errors", action="store_true", help="Show only non-200 results")
    parser.add_argument("--filter", default="", help="Substring filter applied to source name/url")
    args = parser.parse_args()

    filt = args.filter.lower().strip()

    rows: list[tuple[Source, str, str, str, str]] = []
    for src in SOURCES:
        if filt and filt not in src.name.lower() and filt not in src.url.lower():
            continue
        status, headers = fetch_headers(src.url)
        last_modified = headers.get("last-modified", "-")
        etag = headers.get("etag", "-")
        content_length = headers.get("content-length", "-")
        rows.append((src, status, last_modified, etag, content_length))

    print("tier\tstatus\tlast_modified\tcontent_length\tname\turl")
    for src, status, last_modified, _etag, content_length in rows:
        if args.only_errors and status == "200":
            continue
        print(f"{src.tier}\t{status}\t{last_modified}\t{content_length}\t{src.name}\t{src.url}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
