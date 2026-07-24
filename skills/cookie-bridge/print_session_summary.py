import json
import re
from pathlib import Path

data = json.loads(
    Path.home()
    .joinpath(".crcp/cookie-bridge/session_options.json")
    .read_text(encoding="utf-8")
)


def theme(hosts, urls):
    h = " ".join(hosts or []).lower()
    u = " ".join(urls[:40]).lower()
    tags = []
    mapping = [
        (
            "work/dev",
            [
                "github",
                "codacy",
                "codecov",
                "sonar",
                "snyk",
                "hubspot",
                "console.cloud",
                "databricks",
                "chatgpt.com",
                "claude.ai",
                "grok.com",
                "gemini",
                "modal.com",
            ],
        ),
        (
            "google",
            [
                "google.com",
                "drive.google",
                "accounts.google",
                "gmail",
                "business.gemini",
            ],
        ),
        ("social", ["whatsapp", "telegram", "discord", "reddit"]),
        ("adult", ["xhamster", "faphouse", "onlyfans", "coomer", "gaymale", "pornhub"]),
        (
            "research",
            ["doi.org", "z-lib", "mendeley", "scholar", "pubmed", "arxiv", "unibuc"],
        ),
    ]
    for label, keys in mapping:
        if any(k in h or k in u for k in keys):
            tags.append(label)
    return tags or ["mixed"]


lines = []
lines.append("ID   | Browser  | Win | Tabs | MB    | When                | Themes")
lines.append("-----|----------|-----|------|-------|---------------------|--------")
for o in data["options"]:
    urls = []
    for w in o.get("windows") or []:
        for t in w.get("tabs") or []:
            if t.get("url"):
                urls.append(t["url"])
    hosts = o.get("sample_hosts") or []
    if not hosts:
        hosts = sorted(
            {
                re.sub(r"^https?://([^/]+).*", r"\1", u)
                for u in urls
                if u.startswith("http")
            }
        )[:12]
    tags = theme(hosts, urls)
    wins = o.get("windows") or []
    wsum = "; ".join(f"W{w['window_index']}:{w['tab_count']}t" for w in wins[:8])
    mtime = str(o.get("mtime") or "")[:19]
    lines.append(
        f"{o['id']:4} | {o['browser']:8} | {o['window_count']:3} | {o['tab_count']:4} | "
        f"{o['bytes'] / 1e6:5.2f} | {mtime:19} | {', '.join(tags)}"
    )
    lines.append(f"     windows: {wsum}")
    lines.append(f"     file: {o['rel']}")

text = "\n".join(lines)
Path.home().joinpath(".crcp/cookie-bridge/session_options_summary.txt").write_text(
    text, encoding="utf-8"
)
print(text)
