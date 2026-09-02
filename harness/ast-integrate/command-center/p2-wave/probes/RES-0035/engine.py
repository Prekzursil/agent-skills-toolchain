#!/usr/bin/env python3
"""RES-0035: apply the frozen definition to snapshot notes."""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SNAP = HERE / "snapshots"
DEFINITION_PATH = HERE / "DEFINITION.json"
WINDOW_END = datetime(2026, 8, 24, tzinfo=timezone.utc)

HEADING_CLAUDE = re.compile(r"^##\s+(\d+\.\d+\.\d+)\s*$")
HEADING_CLINE = re.compile(r"^##\s+\[(\d+\.\d+\.\d+)\]")
HEADING_ROO = re.compile(r"^##\s+\[?(\d+\.\d+\.\d+)\]?")
HEADING_AIDER = re.compile(r"^###\s+Aider\s+v(\d+\.\d+\.\d+)", re.I)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    s = value.strip().replace(" UTC", "+00:00")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    if "T" not in s and " " in s:
        s = s.replace(" ", "T", 1)
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        try:
            dt = datetime.strptime(s, "%a, %d %b %Y %H:%M:%S %z")
        except ValueError:
            try:
                dt = datetime.strptime(s, "%Y-%m-%d")
            except ValueError:
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def load_definition() -> dict[str, Any]:
    doc = json.loads(DEFINITION_PATH.read_text(encoding="utf-8"))
    doc["_sha256"] = sha256_file(DEFINITION_PATH)
    doc["_config_re"] = re.compile(doc["config_surface_regex"], re.I)
    doc["_break_re"] = re.compile(doc["break_signal_regex"], re.I)
    doc["_excl_re"] = re.compile(doc["exclude_regex"], re.I)
    doc["_bullet_re"] = re.compile(doc["bullet_regex"])
    return doc


def in_window(dt: datetime | None, start: datetime, end: datetime) -> bool:
    return dt is not None and start <= dt <= end


def classify_bullet(text: str, definition: dict[str, Any]) -> bool:
    line = text.strip()
    if definition["_excl_re"].search(line):
        return False
    if not definition["_break_re"].search(line):
        return False
    if not definition["_config_re"].search(line):
        return False
    return True


def iter_bullets(body: str, bullet_re: re.Pattern[str]) -> list[str]:
    out: list[str] = []
    for line in body.splitlines():
        if not bullet_re.search(line):
            continue
        item = re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", line).strip()
        if item:
            out.append(item)
    return out


def parse_markdown_sections(
    text: str, heading_re: re.Pattern[str], bullet_re: re.Pattern[str]
) -> list[dict[str, Any]]:
    releases: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    buf: list[str] = []
    for line in text.splitlines():
        m = heading_re.match(line.strip())
        if m:
            if current is not None:
                current["body"] = "\n".join(buf)
                current["bullets"] = iter_bullets(current["body"], bullet_re)
                releases.append(current)
            current = {"version": m.group(1), "heading": line.strip()}
            buf = []
        else:
            buf.append(line)
    if current is not None:
        current["body"] = "\n".join(buf)
        current["bullets"] = iter_bullets(current["body"], bullet_re)
        releases.append(current)
    return releases


def parse_markdown_linear(
    text: str, heading_re: re.Pattern[str], bullet_re: re.Pattern[str]
) -> list[dict[str, Any]]:
    by_ver: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    current_ver: str | None = None
    for line in text.splitlines():
        hm = heading_re.match(line.strip())
        if hm:
            current_ver = hm.group(1)
            if current_ver not in by_ver:
                by_ver[current_ver] = {
                    "version": current_ver,
                    "heading": line.strip(),
                    "bullets": [],
                }
                order.append(current_ver)
            continue
        if current_ver and bullet_re.search(line):
            item = re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", line).strip()
            if item:
                by_ver[current_ver]["bullets"].append(item)
    return [by_ver[v] for v in order]


def normalize_times(blob: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in blob.items():
        out[k] = v
        if k.startswith("v") and re.match(r"v\d", k):
            out[k[1:]] = v
        else:
            out["v" + k] = v
    return out


def lookup_time(version: str, times: dict[str, str]) -> datetime | None:
    for key in (version, f"v{version}", version.lstrip("v")):
        if key in times:
            return parse_dt(times[key])
    return None


def count_releases(
    releases: list[dict[str, Any]],
    times: dict[str, str],
    definition: dict[str, Any],
    start: datetime,
    end: datetime,
    vendor_id: str,
) -> dict[str, Any]:
    times_n = normalize_times(times)
    counted: list[dict[str, Any]] = []
    undated = 0
    out_of_window = 0
    scanned = 0
    for rel in releases:
        ver = str(rel["version"])
        dt = lookup_time(ver, times_n)
        bullets = rel.get("bullets") or []
        scanned += len(bullets)
        if dt is None:
            undated += 1
            continue
        if not in_window(dt, start, end):
            out_of_window += 1
            continue
        for bullet in bullets:
            if classify_bullet(bullet, definition):
                counted.append(
                    {
                        "vendor_id": vendor_id,
                        "version": ver,
                        "published_at": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "item": bullet[:400],
                    }
                )
    return {
        "count": len(counted),
        "items": counted,
        "undated_releases": undated,
        "out_of_window_releases": out_of_window,
        "bullets_scanned": scanned,
        "releases_parsed": len(releases),
    }


def strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p>", "\n", text, flags=re.I)
    text = re.sub(r"</li>", "\n", text, flags=re.I)
    text = re.sub(r"<li[^>]*>", "- ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"[ \t]+\n", "\n", text)


def parse_atom(path: Path) -> list[dict[str, Any]]:
    root = ET.parse(path).getroot()
    entries = list(root.findall("{http://www.w3.org/2005/Atom}entry"))
    out: list[dict[str, Any]] = []
    for ent in entries:
        title_el = ent.find("{http://www.w3.org/2005/Atom}title")
        title = (title_el.text or "").strip() if title_el is not None else ""
        upd_el = ent.find("{http://www.w3.org/2005/Atom}updated")
        updated = (upd_el.text or "") if upd_el is not None else ""
        content_el = ent.find("{http://www.w3.org/2005/Atom}content")
        body = ""
        if content_el is not None:
            body = strip_html(
                "".join(content_el.itertext()) if list(content_el) else (content_el.text or "")
            )
        vm = re.search(r"(\d+\.\d+\.\d+)", title)
        bullets = iter_bullets(body, re.compile(r"^\s*(?:[-*]|\d+\.)\s+"))
        if not bullets:
            bullets = [b.strip() for b in body.split("\n") if b.strip() and len(b.strip()) > 20][:40]
        out.append(
            {
                "version": vm.group(1) if vm else title[:80],
                "published_at": updated,
                "bullets": bullets,
            }
        )
    return out


def parse_rss(path: Path) -> list[dict[str, Any]]:
    tree = ET.parse(path)
    out: list[dict[str, Any]] = []
    for item in tree.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        pub = item.findtext("pubDate") or ""
        desc = (
            item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded")
            or item.findtext("description")
            or ""
        )
        desc = strip_html(desc)
        vm = re.search(r"(\d+\.\d+\.\d+)", title)
        bullets = iter_bullets(desc, re.compile(r"^\s*(?:[-*]|\d+\.)\s+"))
        if not bullets:
            bullets = [ln.strip("- ").strip() for ln in desc.splitlines() if len(ln.strip()) > 40][:40]
        out.append(
            {
                "version": vm.group(1) if vm else title[:80],
                "published_at": pub,
                "bullets": bullets,
            }
        )
    return out


def count_predated(
    releases: list[dict[str, Any]],
    definition: dict[str, Any],
    start: datetime,
    end: datetime,
    vendor_id: str,
) -> dict[str, Any]:
    counted: list[dict[str, Any]] = []
    undated = 0
    out_of_window = 0
    scanned = 0
    for rel in releases:
        dt = parse_dt(rel.get("published_at"))
        bullets = rel.get("bullets") or []
        scanned += len(bullets)
        if dt is None:
            undated += 1
            continue
        if not in_window(dt, start, end):
            out_of_window += 1
            continue
        ver = str(rel.get("version") or "unknown")
        for bullet in bullets:
            if classify_bullet(bullet, definition):
                counted.append(
                    {
                        "vendor_id": vendor_id,
                        "version": ver,
                        "published_at": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "item": bullet[:400],
                    }
                )
    return {
        "count": len(counted),
        "items": counted,
        "undated_releases": undated,
        "out_of_window_releases": out_of_window,
        "bullets_scanned": scanned,
        "releases_parsed": len(releases),
    }


def notes_json_to_releases(path: Path, times: dict[str, str] | None = None) -> list[dict[str, Any]]:
    notes = json.loads(path.read_text(encoding="utf-8"))
    times_n = normalize_times(times or {})
    out: list[dict[str, Any]] = []
    for n in notes:
        tag = str(n.get("tag") or "")
        ver_m = re.search(r"(\d+\.\d+\.\d+)", tag)
        ver = ver_m.group(1) if ver_m else tag
        published = n.get("published_at") or times_n.get(ver) or times_n.get(tag)
        body = n.get("body") or ""
        bullets = iter_bullets(body, re.compile(r"^\s*(?:[-*]|\d+\.)\s+"))
        if not bullets:
            bullets = [ln.strip() for ln in body.splitlines() if ln.strip().startswith("- ")]
        out.append({"version": ver, "published_at": published, "bullets": bullets})
    return out


def cursor_releases(path: Path) -> list[dict[str, Any]]:
    html = path.read_text(encoding="utf-8", errors="replace")
    text = strip_html(html)
    date_re = re.compile(
        r"((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
        r"Dec(?:ember)?)\s+\d{1,2},\s+202[56])"
    )
    chunks = date_re.split(text)
    out: list[dict[str, Any]] = []
    i = 1
    while i + 1 < len(chunks):
        label = chunks[i]
        body = chunks[i + 1]
        i += 2
        parsed = None
        for fmt in ("%b %d, %Y", "%B %d, %Y"):
            try:
                parsed = datetime.strptime(label.replace("Sept", "Sep"), fmt).replace(
                    tzinfo=timezone.utc
                )
                break
            except ValueError:
                continue
        if parsed is None:
            continue
        bullets = iter_bullets(body, re.compile(r"^\s*(?:[-*]|\d+\.)\s+"))
        if not bullets:
            bullets = [ln.strip() for ln in body.splitlines() if 40 < len(ln.strip()) < 400][:30]
        out.append(
            {
                "version": label,
                "published_at": parsed.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "bullets": bullets,
            }
        )
    return out


def _annotate(stats: dict[str, Any], vendor_id: str, filename: str, coverage: str) -> dict[str, Any]:
    stats = dict(stats)
    stats.update(
        {
            "vendor_id": vendor_id,
            "source": f"command-center/p2-wave/probes/RES-0035/snapshots/{filename}",
            "source_sha256": sha256_file(SNAP / filename),
            "coverage": coverage,
        }
    )
    return stats


def measure() -> dict[str, Any]:
    definition = load_definition()
    definition_sha = definition["_sha256"]
    locked_before_enumerate = True
    end = WINDOW_END
    start = end - timedelta(days=int(definition["window"]["days"]))

    claude_md = (SNAP / "claude-code.CHANGELOG.md").read_text(encoding="utf-8")
    claude_times = json.loads((SNAP / "claude-code.npm-times.json").read_text(encoding="utf-8"))
    pass_a = parse_markdown_sections(claude_md, HEADING_CLAUDE, definition["_bullet_re"])
    pass_b = parse_markdown_linear(claude_md, HEADING_CLAUDE, definition["_bullet_re"])
    claude_a = count_releases(pass_a, claude_times, definition, start, end, "anthropic-claude-code")
    claude_b = count_releases(pass_b, claude_times, definition, start, end, "anthropic-claude-code")
    denom = max(claude_a["count"], claude_b["count"], 1)
    rel_delta = abs(claude_a["count"] - claude_b["count"]) / denom

    def md_vendor(
        vid: str,
        filename: str,
        heading: re.Pattern[str],
        times_file: str,
        coverage: str,
    ) -> dict[str, Any]:
        text = (SNAP / filename).read_text(encoding="utf-8")
        times = json.loads((SNAP / times_file).read_text(encoding="utf-8"))
        rels = parse_markdown_sections(text, heading, definition["_bullet_re"])
        return _annotate(
            count_releases(rels, times, definition, start, end, vid),
            vid,
            filename,
            coverage,
        )

    vendors: list[dict[str, Any]] = []
    claude_row = _annotate(
        claude_a,
        "anthropic-claude-code",
        "claude-code.CHANGELOG.md",
        "FULL_CHANGELOG_DATED",
    )
    claude_row["official_count"] = claude_a["count"]
    vendors.append(claude_row)
    vendors.append(
        md_vendor(
            "cline",
            "cline.CHANGELOG.md",
            HEADING_CLINE,
            "cline.version-dates.json",
            "FULL_CHANGELOG_DATED",
        )
    )
    vendors.append(
        md_vendor(
            "roo-code",
            "roo.CHANGELOG.md",
            HEADING_ROO,
            "roo.version-dates.json",
            "FULL_CHANGELOG_DATED",
        )
    )
    vendors.append(
        md_vendor(
            "aider",
            "aider.HISTORY.md",
            HEADING_AIDER,
            "aider.pypi-times.json",
            "FULL_HISTORY_DATED",
        )
    )

    goose_times = json.loads((SNAP / "goose.version-dates.json").read_text(encoding="utf-8"))
    vendors.append(
        _annotate(
            count_predated(
                notes_json_to_releases(SNAP / "goose.release-notes.json", goose_times),
                definition,
                start,
                end,
                "block-goose",
            ),
            "block-goose",
            "goose.release-notes.json",
            "GITHUB_RELEASE_PAGES_DATED",
        )
    )
    oh_times = json.loads((SNAP / "openhands.version-dates.json").read_text(encoding="utf-8"))
    vendors.append(
        _annotate(
            count_predated(
                notes_json_to_releases(SNAP / "openhands.release-notes.json", oh_times),
                definition,
                start,
                end,
                "openhands",
            ),
            "openhands",
            "openhands.release-notes.json",
            "GITHUB_RELEASE_PAGES_DATED",
        )
    )

    for vid, fname, parser, coverage in (
        ("google-gemini-cli", "gemini-cli.releases.atom", parse_atom, "ATOM_HEAD_ONLY"),
        ("continue-dev", "continue.releases.atom", parse_atom, "ATOM_HEAD_ONLY"),
        ("openai-codex", "codex.releases.atom", parse_atom, "ATOM_HEAD_NOTES_THIN"),
        ("github-copilot", "copilot.github-blog.feed.xml", parse_rss, "RSS_HEAD_ONLY"),
    ):
        vendors.append(
            _annotate(
                count_predated(parser(SNAP / fname), definition, start, end, vid),
                vid,
                fname,
                coverage,
            )
        )

    vendors.append(
        _annotate(
            count_predated(
                cursor_releases(SNAP / "cursor.changelog.html"),
                definition,
                start,
                end,
                "cursor",
            ),
            "cursor",
            "cursor.changelog.html",
            "HTML_CHANGELOG_PAGES_PARTIAL",
        )
    )

    rows = []
    for v in vendors:
        rows.append(
            {
                "vendor_id": v["vendor_id"],
                "count": v["count"],
                "coverage": v["coverage"],
                "source_sha256": v["source_sha256"],
                "source": v["source"],
                "bullets_scanned": v["bullets_scanned"],
                "releases_parsed": v["releases_parsed"],
                "undated_releases": v["undated_releases"],
                "out_of_window_releases": v["out_of_window_releases"],
                "items": v["items"],
            }
        )

    dated_full = [
        r for r in rows if r["coverage"].startswith("FULL") or r["coverage"].startswith("GITHUB")
    ]
    ranked = sorted(dated_full, key=lambda r: r["count"], reverse=True)
    top = ranked[0] if ranked else {"vendor_id": "none", "count": 0}
    implication = (
        "Adapter maintenance cost tracks dated, definition-matching config-surface breaks. "
        f"Highest measured rate among fully dated sources: {top['vendor_id']} "
        f"n={top['count']} in 365d. "
        "A vendor at 0 under this definition is not 'stable forever'; it may omit breaking labels. "
        "Budget adapter churn on the labeled rate plus a residual for unlabeled schema drift."
    )
    return {
        "definition_sha256": definition_sha,
        "definition_id": definition["id"],
        "definition_locked_hash_before_enumerate": locked_before_enumerate,
        "window_start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "two_pass": {
            "vendor_id": "anthropic-claude-code",
            "pass_a": "section_split",
            "pass_b": "linear_heading_walk",
            "pass_a_count": claude_a["count"],
            "pass_b_count": claude_b["count"],
            "relative_delta": rel_delta,
            "within_10_percent": rel_delta <= 0.10,
            "pass_a_items": claude_a["items"],
            "pass_b_items": claude_b["items"],
        },
        "vendors": rows,
        "maintenance_implication": implication,
        "same_rule_all_vendors": True,
    }


def fixture_both_states(definition: dict[str, Any] | None = None) -> dict[str, Any]:
    definition = definition or load_definition()
    planted = (
        "Breaking change: Removed deprecated `autoMode` key from `.claude/settings.json`; "
        "adapters must read `~/.claude/settings.json` instead."
    )
    noise = "Fixed a regression that was breaking ASCII tables in the chat UI."
    added = "Added optional `theme` setting in settings.json with a backward-compatible default."
    return {
        "planted_break_counted": classify_bullet(planted, definition),
        "noise_excluded": not classify_bullet(noise, definition),
        "optional_add_excluded": not classify_bullet(added, definition),
        "planted": planted,
        "noise": noise,
        "added": added,
    }


if __name__ == "__main__":
    result = measure()
    print(
        json.dumps(
            {
                "definition_sha256": result["definition_sha256"],
                "two_pass": {
                    k: result["two_pass"][k]
                    for k in (
                        "vendor_id",
                        "pass_a_count",
                        "pass_b_count",
                        "relative_delta",
                        "within_10_percent",
                    )
                },
            },
            indent=2,
        )
    )
    for v in result["vendors"]:
        print(f"{v['vendor_id']:24} count={v['count']} cov={v['coverage']} scanned={v['bullets_scanned']}")
    print("fixtures", fixture_both_states())
