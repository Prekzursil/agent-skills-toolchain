"""Load the RES-0014 issue corpus: live captures + seeded control + keyword decoy."""
from __future__ import annotations

import json
from pathlib import Path

from digest import digest_file

HERE = Path(__file__).resolve().parent
CAPTURES = HERE / "fixtures" / "captures"
SEEDED = HERE / "fixtures" / "seeded_issue.json"
DECOY = HERE / "fixtures" / "decoy_keyword_only.json"


def _blob(issue: dict, comments: list) -> str:
    parts = [
        str(issue.get("title") or ""),
        str(issue.get("body") or ""),
        str(issue.get("state") or ""),
    ]
    for c in comments:
        if isinstance(c, dict):
            parts.append(str(c.get("body") or ""))
    return "\n".join(parts)


def _load_api(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"unparseable issue api {path}")
    return data


def _load_comments(path: Path) -> list:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def load_corpus() -> list[dict]:
    rows: list[dict] = []
    for api_path in sorted(CAPTURES.glob("issue-*.api.json")):
        n = api_path.name.split("-", 1)[1].split(".", 1)[0]
        html_path = CAPTURES / f"issue-{n}.html"
        comments_path = CAPTURES / f"issue-{n}.comments.json"
        issue = _load_api(api_path)
        comments = _load_comments(comments_path)
        api_sha, api_bytes = digest_file(api_path)
        html_sha, html_bytes = digest_file(html_path)
        number = int(issue.get("number") or n)
        rows.append(
            {
                "number": number,
                "id": f"anthropics/claude-code#{number}",
                "title": issue.get("title") or "",
                "state": issue.get("state") or "",
                "html_url": issue.get("html_url") or issue.get("html_url") or "",
                "body": issue.get("body") or "",
                "comments": comments,
                "blob": _blob(issue, comments),
                "seeded": False,
                "decoy": False,
                "api_path": str(api_path.relative_to(HERE.parents[3])),
                "html_path": str(html_path.relative_to(HERE.parents[3])),
                "api_permalink": (
                    issue.get("url")
                    or f"https://api.github.com/repos/anthropics/claude-code/issues/{number}"
                ),
                "html_permalink": (
                    issue.get("html_url")
                    or f"https://github.com/anthropics/claude-code/issues/{number}"
                ),
                "api_sha256": api_sha,
                "api_bytes": api_bytes,
                "html_sha256": html_sha,
                "html_bytes": html_bytes,
                "created_at": issue.get("created_at"),
                "closed_at": issue.get("closed_at"),
                "updated_at": issue.get("updated_at"),
                "labels": [
                    (lab.get("name") if isinstance(lab, dict) else str(lab))
                    for lab in (issue.get("labels") or [])
                ],
            }
        )

    def load_fixture(path: Path, *, seeded: bool, decoy: bool) -> dict:
        issue = json.loads(path.read_text(encoding="utf-8"))
        sha, nbytes = digest_file(path)
        rel = str(path.relative_to(HERE.parents[3]))
        return {
            "number": int(issue["number"]),
            "id": issue["id"],
            "title": issue["title"],
            "state": issue["state"],
            "html_url": issue["html_url"],
            "body": issue["body"],
            "comments": [],
            "blob": _blob(issue, []),
            "seeded": seeded,
            "decoy": decoy,
            "api_path": rel,
            "html_path": rel,
            "api_permalink": issue["html_url"],
            "html_permalink": issue["html_url"],
            "api_sha256": sha,
            "api_bytes": nbytes,
            "html_sha256": sha,
            "html_bytes": nbytes,
            "created_at": None,
            "closed_at": None,
            "updated_at": None,
            "labels": issue.get("labels") or [],
        }

    rows.append(load_fixture(SEEDED, seeded=True, decoy=False))
    rows.append(load_fixture(DECOY, seeded=False, decoy=True))
    return rows
