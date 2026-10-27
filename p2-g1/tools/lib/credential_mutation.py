"""Static scan for credential-mutation call sites (TST-0213)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

PLANTED_REVOKE_TOKEN_PY = "revoke_token(secret)\n"
PLANTED_REVOKE_TOKEN_JS = "revokeToken(secret);\n"
PLANTED_CLEAN_PY = "print('hello')\n"

_PY_HITS = ("revoke_token(", "rotate_secret(", "delete_api_key(")
_JS_HITS = ("revokeToken(", "rotateSecret(", "deleteApiKey(")


def detector_fires_on_plant(source: str, language: str) -> bool:
    text = source or ""
    if language == "python":
        return any(h in text for h in _PY_HITS)
    return any(h in text for h in _JS_HITS)


def scan_tree(root: Path | str) -> dict[str, Any]:
    root = Path(root)
    hits = []
    files_scanned = 0
    by_lang = {"python": 0, "javascript": 0}
    skip = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(p in path.parts for p in (".git", "node_modules", "__pycache__", "ovh-monitor")):
            skip.append(str(path))
            continue
        if path.suffix == ".py":
            lang = "python"
        elif path.suffix in {".js", ".mjs", ".cjs"}:
            lang = "javascript"
        else:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        files_scanned += 1
        by_lang[lang] += 1
        needles = _PY_HITS if lang == "python" else _JS_HITS
        if any(n in text for n in needles):
            posix = path.as_posix()
            if path.name in {"credential_mutation.py"}:
                continue
            if "/probes/" in posix or "/catalog-slices/" in posix or "/ovh-monitor/" in posix:
                continue
            hits.append(posix)
    return {
        "files_scanned": files_scanned,
        "files_by_language": by_lang,
        "languages_scanned": [k for k, v in by_lang.items() if v],
        "hit_count": len(hits),
        "hits": hits,
        "skip": skip[:20],
    }
