"""Census of Gemini CLI extension manifest and GEMINI.md surface.

Two mechanically different measurements of frozen captures:
  R1 — TypeScript ExtensionConfig + DEFAULT_CONTEXT_FILENAME (source)
  R2 — official docs markdown (prose + example JSON)

A planted invented key must not appear in either census. Feeding a mutant
that inserts the key must make the parser report it (both-states).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CAPTURES = HERE / "captures"
PLANTED_KEY = "res0024InventedManifestKey"
DOC_SECTION_END = "### Extension settings"

MANIFEST_BULLET_RE = re.compile(r"^- `([A-Za-z_][A-Za-z0-9]*)`:", re.M)
INTERFACE_RE = re.compile(
    r"export interface ExtensionConfig \{([\s\S]*?)\n\}",
)
TOP_PROP_RE = re.compile(r"^  ([A-Za-z_][A-Za-z0-9_]*)\??\s*:")
CONST_RE = re.compile(
    r"export const DEFAULT_CONTEXT_FILENAME = '([^']+)'"
)


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def load_capture(name: str) -> dict[str, Any]:
    body = CAPTURES / f"{name}.body"
    meta_path = CAPTURES / f"{name}.meta.json"
    if not body.is_file() or not meta_path.is_file():
        raise FileNotFoundError(f"capture missing: {name}")
    raw = body.read_bytes()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    live = digest_bytes(raw)
    if str(meta.get("sha256") or "") != live:
        raise ValueError(f"capture sha mismatch {name}: meta={meta.get('sha256')} live={live}")
    status = int(meta.get("http_status") or 0)
    if status != 200:
        raise ValueError(f"capture http {status} for {name}")
    text = raw.decode("utf-8")
    return {
        "name": name,
        "text": text,
        "sha256": live,
        "bytes": len(raw),
        "http_status": status,
        "fetched_at": meta.get("fetched_at"),
        "request_url": meta.get("request_url"),
        "final_url": meta.get("final_url"),
        "permalink": meta.get("request_url"),
    }


def source_manifest_keys(text: str) -> list[str]:
    match = INTERFACE_RE.search(text)
    if not match:
        raise ValueError("ExtensionConfig interface not found")
    keys: list[str] = []
    for line in match.group(1).splitlines():
        prop = TOP_PROP_RE.match(line)
        if prop:
            keys.append(prop.group(1))
    if "name" not in keys or "version" not in keys:
        raise ValueError(f"required keys missing: {keys}")
    return keys


def docs_example_keys(text: str) -> list[str]:
    block = re.search(r"```json\n(\{[\s\S]*?\n\})\n```", text)
    if not block:
        raise ValueError("gemini-extension.json example block not found")
    obj = json.loads(block.group(1))
    if not isinstance(obj, dict):
        raise ValueError("example JSON is not an object")
    return list(obj.keys())


def docs_bullet_keys(text: str) -> list[str]:
    start = text.find("### `gemini-extension.json`")
    if start < 0:
        start = text.find("### gemini-extension.json")
    if start < 0:
        raise ValueError("manifest section heading not found")
    end = text.find(DOC_SECTION_END, start)
    section = text[start:end] if end > start else text[start:]
    keys = MANIFEST_BULLET_RE.findall(section)
    if "name" not in keys:
        raise ValueError(f"docs bullets missing name: {keys}")
    return keys


def docs_mentions_settings_and_themes(text: str) -> dict[str, bool]:
    return {
        "settings": bool(re.search(r"add a `settings` array", text)),
        "themes": "`themes` array in `gemini-extension.json`" in text
        or "defined in the `themes` array" in text,
    }


def directory_conventions(text: str) -> list[dict[str, str]]:
    rows = []
    patterns = (
        ("commands/", "custom slash-command TOML"),
        ("hooks/hooks.json", "hooks (not a gemini-extension.json field)"),
        ("skills/", "agent skills SKILL.md"),
        ("agents/", "sub-agent markdown (preview)"),
        ("policies/", "policy-engine TOML"),
    )
    for rel, role in patterns:
        rows.append({"path": rel, "documented": rel in text, "role": role})
    return rows


def default_context_filename(text: str) -> str:
    match = CONST_RE.search(text)
    if not match:
        raise ValueError("DEFAULT_CONTEXT_FILENAME not found")
    return match.group(1)


def docs_hierarchy(text: str) -> list[dict[str, str]]:
    levels = []
    mapping = (
        ("Global context file", "global", "~/.gemini/GEMINI.md"),
        ("Environment and workspace context files", "workspace", "workspace and parents"),
        ("Just-in-time (JIT) context files", "jit", "tool-access ancestors to trusted root"),
    )
    for label, ident, location in mapping:
        if label not in text:
            raise ValueError(f"docs hierarchy missing {label}")
        levels.append({"id": ident, "label": label, "location": location})
    return levels


def source_memory_functions(text: str) -> list[str]:
    needed = (
        "getGlobalMemoryPaths",
        "getEnvironmentMemoryPaths",
        "getExtensionMemoryPaths",
        "getUserProjectMemoryPaths",
        "loadJitSubdirectoryMemory",
        "categorizeAndConcatenate",
    )
    missing = [n for n in needed if f"function {n}" not in text and f"export async function {n}" not in text and f"export function {n}" not in text]
    if missing:
        raise ValueError(f"memoryDiscovery missing {missing}")
    return list(needed)


def census() -> dict[str, Any]:
    ext_ts = load_capture("extension_ts")
    ext_md = load_capture("extension_ref_md")
    gem_md = load_capture("gemini_md_doc")
    mem_ts = load_capture("memory_discovery")
    mem_tool = load_capture("memory_tool")

    source_keys = source_manifest_keys(ext_ts["text"])
    example_keys = docs_example_keys(ext_md["text"])
    bullet_keys = docs_bullet_keys(ext_md["text"])
    extra = docs_mentions_settings_and_themes(ext_md["text"])
    docs_keys = sorted(set(example_keys) | set(bullet_keys) | {k for k, ok in extra.items() if ok})
    source_set = set(source_keys)
    docs_set = set(docs_keys)
    default_name = default_context_filename(mem_tool["text"])
    hierarchy = docs_hierarchy(gem_md["text"])
    mem_fns = source_memory_functions(mem_ts["text"])
    dirs = directory_conventions(ext_md["text"])
    if not all(d["documented"] for d in dirs):
        raise ValueError(f"directory convention miss: {dirs}")
    if default_name != "GEMINI.md":
        raise ValueError(f"unexpected default context filename {default_name!r}")
    if PLANTED_KEY in source_keys or PLANTED_KEY in docs_keys:
        raise ValueError("planted invented key leaked into real census")

    return {
        "source_manifest_keys": source_keys,
        "docs_example_keys": example_keys,
        "docs_bullet_keys": bullet_keys,
        "docs_manifest_keys": docs_keys,
        "docs_only": sorted(docs_set - source_set),
        "source_only": sorted(source_set - docs_set),
        "agreed_keys": sorted(source_set & docs_set),
        "directory_conventions": dirs,
        "default_context_filename": default_name,
        "docs_hierarchy": hierarchy,
        "source_memory_functions": mem_fns,
        "extension_load_root": "<home>/.gemini/extensions/<name>/gemini-extension.json",
        "context_file_name_type": "string | string[] (source); string in docs example",
        "captures": {
            cap["name"]: {
                "sha256": cap["sha256"],
                "bytes": cap["bytes"],
                "http_status": cap["http_status"],
                "fetched_at": cap["fetched_at"],
                "permalink": cap["permalink"],
            }
            for cap in (ext_ts, ext_md, gem_md, mem_ts, mem_tool)
        },
        "planted_key": PLANTED_KEY,
        "planted_key_absent_from_real_census": True,
    }


def planted_key_both_states() -> dict[str, Any]:
    """Parser must stay silent on the real file and fire on a mutant insert."""
    ext_ts = load_capture("extension_ts")
    real = source_manifest_keys(ext_ts["text"])
    needle = "  migratedTo?: string;\n}"
    if needle not in ext_ts["text"]:
        raise ValueError("cannot plant mutant: migratedTo closing not found")
    mutant_text = ext_ts["text"].replace(
        needle,
        f"  migratedTo?: string;\n  {PLANTED_KEY}?: string;\n}}",
        1,
    )
    mutant = source_manifest_keys(mutant_text)
    discriminates = (PLANTED_KEY not in real) and (PLANTED_KEY in mutant)
    return {
        "planted_key": PLANTED_KEY,
        "real_has_planted": PLANTED_KEY in real,
        "mutant_has_planted": PLANTED_KEY in mutant,
        "discriminates": discriminates,
        "real_keys": real,
        "mutant_keys": mutant,
    }


def pinned_commit() -> dict[str, Any]:
    path = CAPTURES / "github_main_commit.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    sha = data.get("sha")
    date = ((data.get("commit") or {}).get("committer") or {}).get("date")
    html = data.get("html_url")
    return {
        "repo": "google-gemini/gemini-cli",
        "sha": sha,
        "committed_at": date,
        "html_url": html,
        "ref": "main",
    }
