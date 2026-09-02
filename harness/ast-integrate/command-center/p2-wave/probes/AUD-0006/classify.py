"""AUD-0006 classifiers: path-only strawman vs body classifier.

Resumed from command-center/p2-wave/_build_AUD0006.py. The catalog requires
classification of the file BODY (imports, tests, docstrings), not the path,
because a scratch-looking path can hold real work and vice versa.

git-hygiene Config is ABSENT on this worktree (hooks/git-hygiene/check.py
missing). Path-only falls back to the builder's scratch-token list plus a
declared exclude/vendor set so the strawman still runs.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

READ_CAP = 65536

SCRATCH_PATH_TOKENS = (
    "tmp",
    "temp",
    "scratch",
    "cache",
    "sandbox",
    "junk",
    "throwaway",
    "_out",
    "backup",
)

FALLBACK_EXCLUDE_DIRS = {
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".git",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
}
FALLBACK_VENDOR_MARKERS = ("vendor", "third_party", "_vendor", "third-party")


def load_hygiene_config() -> tuple[dict[str, Any], str]:
    """Return (config dict, source note). Never raises."""
    hook = Path(__file__).resolve().parents[3] / "hooks" / "git-hygiene" / "check.py"
    # parents[3] is command-center; repo root is parents[4]
    hook = Path(__file__).resolve().parents[4] / "hooks" / "git-hygiene" / "check.py"
    if not hook.is_file():
        return {
            "exclude_dirs": sorted(FALLBACK_EXCLUDE_DIRS),
            "vendor_markers": list(FALLBACK_VENDOR_MARKERS),
            "exclude_patterns": [],
        }, f"ABSENT:{hook.as_posix()} — using fallback scratch/vendor tokens"
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("gh_check", hook)
        if spec is None or spec.loader is None:
            raise ImportError("no loader")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cfg = mod.Config()
        return {
            "exclude_dirs": sorted(getattr(cfg, "exclude_dirs", FALLBACK_EXCLUDE_DIRS)),
            "vendor_markers": list(getattr(cfg, "vendor_markers", FALLBACK_VENDOR_MARKERS)),
            "exclude_patterns": list(getattr(cfg, "exclude_patterns", [])),
        }, "hooks/git-hygiene/check.py::Config"
    except Exception as exc:  # noqa: BLE001
        return {
            "exclude_dirs": sorted(FALLBACK_EXCLUDE_DIRS),
            "vendor_markers": list(FALLBACK_VENDOR_MARKERS),
            "exclude_patterns": [],
        }, f"UNAVAILABLE:{type(exc).__name__}: {exc}"


def path_only_verdict(rel: str, cfg: dict[str, Any] | None = None) -> str:
    """Strawman: decide from path tokens only."""
    if cfg is None:
        cfg, _ = load_hygiene_config()
    low = rel.replace("\\", "/").lower()
    parts = set(low.split("/"))
    exclude = set(cfg.get("exclude_dirs") or [])
    if parts & exclude:
        return "SCRATCH"
    markers = cfg.get("vendor_markers") or []
    if any(m.strip("/") in parts for m in markers):
        return "VENDORED"
    if any(t in low for t in SCRATCH_PATH_TOKENS):
        return "SCRATCH"
    return "REAL-WORK"


def content_verdict(rel: str, data: bytes) -> tuple[str, list[str]]:
    """Classify on the BODY. Returns (verdict, signal names) — never file contents."""
    sig: list[str] = []
    if not data:
        return "SCRATCH", ["empty"]
    if b"\x00" in data[:8192]:
        return "SCRATCH", ["binary"]
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return "SCRATCH", ["undecodable"]
    solid = "".join(text.split())
    if len(solid) < 40:
        return "SCRATCH", [f"near-empty({len(solid)})"]
    if len(set(solid)) < 8:
        return "SCRATCH", [f"degenerate-charset({len(set(solid))})"]

    suffix = Path(rel).suffix.lower()
    if suffix in (".py", ".pyi"):
        if re.search(r"^\s*(def|class)\s+\w", text, re.M):
            sig.append("defines-function-or-class")
        if re.search(r"^\s*(import|from)\s+\w", text, re.M):
            sig.append("imports")
        if re.search(r"^\s*(\"\"\"|''')", text, re.M):
            sig.append("module-docstring")
        if re.search(r"\bdef test_|\bassert\b|\bpytest\b", text):
            sig.append("carries-a-test-or-assertion")
    elif suffix in (".md", ".markdown"):
        if len(re.findall(r"^#{1,6}\s+\S", text, re.M)) >= 2:
            sig.append("markdown-structure")
        if len(solid) >= 400:
            sig.append("substantive-prose")
    elif suffix == ".json":
        try:
            parsed = json.loads(text)
            n = len(parsed) if isinstance(parsed, (dict, list)) else 0
            if n >= 3:
                sig.append(f"structured-json({n})")
        except Exception:  # noqa: BLE001
            sig.append("json-parse-error")
    if not sig and len(solid) >= 400 and len(set(solid)) >= 20:
        sig.append("substantive-text")

    if any(s.startswith("json-parse-error") for s in sig) and len(sig) == 1:
        return "UNDECIDED", sig
    return ("REAL-WORK", sig) if sig else ("UNDECIDED", ["no-real-work-signal"])


def classify_path(repo: Path, rel: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    fp = repo / rel
    data = b""
    size = 0
    mtime = None
    if fp.is_file():
        st = fp.stat()
        size = st.st_size
        mtime = st.st_mtime
        data = fp.read_bytes()[:READ_CAP]
    cv, sig = content_verdict(rel, data)
    pv = path_only_verdict(rel, cfg)
    return {
        "path": rel.replace("\\", "/"),
        "bytes": size,
        "mtime": mtime,
        "content_verdict": cv,
        "path_only_verdict": pv,
        "signals": sig,
        "disagreement": cv != pv,
    }
