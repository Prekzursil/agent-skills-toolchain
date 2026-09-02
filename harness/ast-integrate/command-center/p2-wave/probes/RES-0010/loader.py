"""Replica of the live Cursor agent 2026.08.11-e8db854 skill/rule loader.

Source: /root/.local/share/cursor-agent/versions/2026.08.11-e8db854/index.js
sha256: f6fd4e6bf3d6ecbf66cc2dcabcf708b8a7c37b400d10c82a58658b5e331c36d0

Functions mirrored (minified names from that build):
  yl / nSO  glob list normalizer
  as        alwaysApply === true
  ls        SKILL.md -> CursorRule (global vs agentFetched)
  us        SKILL.md -> AgentSkill proto (paths ?? globs, disable-model-invocation)
  ss        metadata.surfaces filter
  ps        custom .mdc frontmatter parser (NOT gray-matter)
  As        .mdc load-mode: alwaysApply / globs / description / manual
  js        .mdc file -> As(ps(content))
  Y         model-invocation filter: !disableModelInvocation || plugin
  is        description cap 1536
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

CLIENT_INDEX = Path(__file__).resolve().parent / "fixtures" / "cursor-agent" / "index.js"
CLIENT_SHA256 = "f6fd4e6bf3d6ecbf66cc2dcabcf708b8a7c37b400d10c82a58658b5e331c36d0"
CLIENT_VERSION = "2026.08.11-e8db854"
NEEDLE_SKILL_PATHS = "n.data?.paths??n.data?.globs"
NEEDLE_ALWAYS_APPLY = "function as(e){return!0===e.data?.alwaysApply}"
NEEDLE_RULE_GLOBS = "e.frontmatter.globs"
DESC_CAP = 1536

# Frontmatter keys the SKILL.md gray-matter path actually consumes.
SKILL_FRONTMATTER_FIELDS_READ = (
    "name",
    "description",
    "alwaysApply",
    "paths",
    "globs",
    "disable-model-invocation",
    "environments",
    "disabled-environments",
    "metadata.environments",
    "metadata.disabledEnvironments",
    "metadata.scopedTo",
    "metadata.surfaces",
    "user-invocable",
)

# Frontmatter keys the .mdc ps()+As() path actually consumes for load_mode.
RULE_FRONTMATTER_FIELDS_READ = (
    "alwaysApply",
    "globs",
    "description",
    "metadata.environments",
    "metadata.disabledEnvironments",
    "metadata.scopedTo",
)


def client_source_ok() -> dict[str, Any]:
    exists = CLIENT_INDEX.is_file()
    text = CLIENT_INDEX.read_text(encoding="utf-8", errors="ignore") if exists else ""
    import hashlib

    digest = hashlib.sha256(CLIENT_INDEX.read_bytes()).hexdigest() if exists else ""
    return {
        "path": str(CLIENT_INDEX),
        "exists": exists,
        "bytes": CLIENT_INDEX.stat().st_size if exists else 0,
        "sha256": digest,
        "sha256_expected": CLIENT_SHA256,
        "sha256_match": digest == CLIENT_SHA256,
        "version": CLIENT_VERSION,
        "needle_skill_paths": NEEDLE_SKILL_PATHS in text,
        "needle_always_apply": NEEDLE_ALWAYS_APPLY in text,
        "needle_rule_globs": NEEDLE_RULE_GLOBS in text,
        "offset_skill_paths": text.find(NEEDLE_SKILL_PATHS) if text else -1,
        "offset_always_apply": text.find(NEEDLE_ALWAYS_APPLY) if text else -1,
        "offset_rule_mode": text.find("if(!0===e.frontmatter.alwaysApply)") if text else -1,
    }


def split_frontmatter(text: str) -> tuple[str, str]:
    raw = text.replace("\r\n", "\n")
    if not raw.startswith("---"):
        return "", raw
    rest = raw[3:]
    if rest.startswith("\n"):
        rest = rest[1:]
    end = rest.find("\n---")
    if end < 0:
        return "", raw
    fm = rest[:end]
    body = rest[end + 4 :]
    if body.startswith("\n"):
        body = body[1:]
    return fm, body


def parse_skill_gray_matter(text: str) -> dict[str, Any]:
    """js-yaml / gray-matter path used for SKILL.md (qt.be)."""
    fm, body = split_frontmatter(text)
    data: dict[str, Any] = {}
    if fm.strip():
        loaded = yaml.safe_load(fm)
        if isinstance(loaded, dict):
            data = loaded
    return {"data": data, "content": body, "raw": text}


def _ms(value: str) -> Any:
    t = value.strip()
    if t == "true":
        return True
    if t == "false":
        return False
    if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")):
        return t[1:-1]
    return t


def parse_mdc_ps(text: str) -> dict[str, Any] | None:
    """Replica of minified ps() — custom .mdc parser, not gray-matter."""
    t = text.lstrip()
    if not t.startswith("---"):
        return None
    parts = [p for p in t.split("---") if p]
    if len(parts) < 2:
        return None
    raw_fm = parts[0].strip()
    body = "---".join(parts[1:]).strip()
    fm: dict[str, Any] = {}
    nest_key: str | None = None
    list_key: str | None = None
    for line in raw_fm.split("\n"):
        line = line.replace("\r", "")
        m = re.match(r"^\s+-\s+(.*)$", line)
        if m and list_key:
            item = m.group(1).strip()
            if (item.startswith('"') and item.endswith('"')) or (
                item.startswith("'") and item.endswith("'")
            ):
                item = item[1:-1]
            cur = fm.get(list_key)
            if isinstance(cur, list):
                cur.append(item)
            continue
        indented = line.startswith("  ") or line.startswith("\t")
        if nest_key and indented:
            inner = line.strip()
            colon = inner.find(":")
            if colon < 0:
                continue
            sub = inner[:colon].strip()
            rest = inner[colon + 1 :].strip()
            coerced = _ms(rest)
            key = f"{nest_key}.{sub}"
            if rest == "":
                fm[key] = []
                list_key = key
            elif key in {
                "metadata.environments",
                "metadata.disabledEnvironments",
                "metadata.scopedTo",
            }:
                fm[key] = [p.strip() for p in str(coerced).split(",") if p.strip()]
                list_key = None
            else:
                fm[key] = coerced
                list_key = None
            continue
        nest_key = None
        list_key = None
        colon = line.find(":")
        if colon < 0:
            continue
        key = line[:colon].strip()
        rest = line[colon + 1 :].strip()
        if rest == "" and key == "metadata":
            nest_key = key
            continue
        if key == "globs" and rest == "":
            fm["globs"] = []
            list_key = "globs"
            continue
        coerced = _ms(rest)
        if key in {
            "metadata.environments",
            "metadata.disabledEnvironments",
            "metadata.scopedTo",
        }:
            fm[key] = [p.strip() for p in str(coerced).split(",") if p.strip()]
        else:
            fm[key] = coerced
    return {
        "frontmatter": fm,
        "rawFrontmatter": f"---\n{raw_fm}\n---",
        "body": body,
    }


def normalize_globs(value: Any) -> list[str] | None:
    """Replica of yl / nSO."""
    if isinstance(value, str):
        parts: list[str] = []
        start = 0
        depth = 0
        for i, ch in enumerate(value):
            if ch == "{":
                depth += 1
            elif ch == "}" and depth > 0:
                depth -= 1
            elif ch == "," and depth == 0:
                piece = value[start:i].strip()
                if piece:
                    parts.append(piece)
                start = i + 1
        tail = value[start:].strip()
        if tail:
            parts.append(tail)
        return parts or None
    if isinstance(value, list):
        parts = [str(x).strip() for x in value if isinstance(x, str) and str(x).strip()]
        return parts or None
    return None


def cap_desc(value: str) -> str:
    return value[:DESC_CAP]


def surfaces_of(data: dict[str, Any]) -> list[str]:
    meta = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    raw = meta.get("surfaces") if isinstance(meta, dict) else None
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, str)]
    if isinstance(raw, str):
        return [p.strip() for p in raw.split(",") if p.strip()]
    return []


def skip_for_surface(data: dict[str, Any], surface: str = "cli") -> bool:
    surf = surfaces_of(data)
    return bool(surf) and surface not in surf


def user_invocable_false(data: dict[str, Any]) -> bool:
    raw = data.get("user-invocable")
    if raw is False:
        return True
    if isinstance(raw, str) and raw.strip().lower() == "false":
        return True
    return False


def model_invocable(disable_model_invocation: bool, plugin: bool = False) -> bool:
    """Replica of Y(): !disableModelInvocation || plugin/marketplace."""
    return (not disable_model_invocation) or plugin


def classify_skill(path: str, text: str, surface: str = "cli") -> dict[str, Any]:
    parsed = parse_skill_gray_matter(text)
    data = parsed["data"]
    if skip_for_surface(data, surface):
        return {
            "kind": "skill",
            "path": path,
            "skipped_surface": True,
            "rule_type": None,
            "agent_skill": False,
            "globs": [],
            "fields_present": sorted(str(k) for k in data.keys()),
        }
    always = data.get("alwaysApply") is True
    desc = data.get("description") if isinstance(data.get("description"), str) else ""
    name = data.get("name") if isinstance(data.get("name"), str) else Path(path).parent.name
    globs = normalize_globs(data.get("paths") if data.get("paths") is not None else data.get("globs")) or []
    dmi = data.get("disable-model-invocation") is True
    rule_type = "global" if always else "agentFetched"
    return {
        "kind": "skill",
        "path": path,
        "skipped_surface": False,
        "name": name,
        "description": cap_desc(desc) if desc else "",
        "description_required_ok": bool(desc),
        "alwaysApply": always,
        "rule_type": rule_type,
        "agent_skill": not always,
        "globs": globs,
        "paths_key_present": "paths" in data,
        "globs_key_present": "globs" in data,
        "disable_model_invocation": dmi,
        "model_invocable": model_invocable(dmi, plugin=False),
        "user_invocable_false": user_invocable_false(data),
        "fields_present": sorted(str(k) for k in data.keys()),
        "fields_read_intersect": sorted(
            k for k in SKILL_FRONTMATTER_FIELDS_READ if k.split(".")[0] in data or k in data
        ),
    }


def classify_rule(path: str, text: str) -> dict[str, Any]:
    parsed = parse_mdc_ps(text)
    if parsed is None:
        return {
            "kind": "rule",
            "path": path,
            "parse_error": "Failed to parse .mdc rule file",
            "rule_type": "manuallyAttached",
            "globs": [],
            "body_injected_at_turn_0": False,
        }
    fm = parsed["frontmatter"]
    if fm.get("alwaysApply") is True:
        rule_type = "global"
        globs: list[str] = []
    else:
        globs = normalize_globs(fm.get("globs")) or []
        desc = fm.get("description")
        if globs:
            rule_type = "fileGlobbed"
        elif isinstance(desc, str) and desc.strip():
            rule_type = "agentFetched"
        else:
            rule_type = "manuallyAttached"
    return {
        "kind": "rule",
        "path": path,
        "rule_type": rule_type,
        "globs": globs,
        "paths_key_present": "paths" in fm,
        "globs_key_present": "globs" in fm,
        "alwaysApply": fm.get("alwaysApply") is True,
        "description": fm.get("description") if isinstance(fm.get("description"), str) else "",
        "frontmatter_keys": sorted(str(k) for k in fm.keys()),
        "body_injected_at_turn_0": rule_type == "global",
        "catalog_present_at_turn_0": rule_type in {"global", "agentFetched", "fileGlobbed"},
    }


_BRACE = re.compile(r"\{([^{}]+)\}")


def _expand_braces(pat: str) -> list[str]:
    m = _BRACE.search(pat)
    if not m:
        return [pat]
    alts = [a.strip() for a in m.group(1).split(",") if a.strip()]
    prefix, suffix = pat[: m.start()], pat[m.end() :]
    out: list[str] = []
    for alt in alts or [""]:
        out.extend(_expand_braces(prefix + alt + suffix))
    return out or [pat]


def _glob_to_rx(pat: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(pat):
        if pat.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pat.startswith("**", i):
            out.append(".*")
            i += 2
        elif pat[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pat[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pat[i]))
            i += 1
    return "".join(out)


def glob_match(pattern: str, relpath: str) -> bool:
    path = relpath.replace("\\", "/").lstrip("./")
    for pat in _expand_braces(pattern.replace("\\", "/")):
        rx = re.compile("^" + _glob_to_rx(pat) + "$")
        if rx.match(path) or rx.match(path.split("/")[-1]):
            return True
    return False


def any_glob_match(globs: list[str], relpath: str) -> bool:
    return any(glob_match(g, relpath) for g in globs)


def observation_for_skill(rec: dict[str, Any], touch: str | None) -> dict[str, Any]:
    catalog_t0 = bool(rec.get("agent_skill")) and rec.get("model_invocable") is True
    if rec.get("rule_type") == "global":
        body_t0 = True
        catalog_t0 = True
    else:
        body_t0 = False
    body_after = body_t0
    # CLI us() stores globs on the proto; ls() does not fileGlob the skill.
    # Local instrument: matching touch does not inject the skill body.
    if touch and rec.get("globs") and any_glob_match(list(rec.get("globs") or []), touch):
        skill_glob_matched = True
    else:
        skill_glob_matched = False
    return {
        "id": rec.get("name") or Path(str(rec.get("path") or "")).stem,
        "kind": "skill",
        "path": rec.get("path"),
        "rule_type": rec.get("rule_type"),
        "globs": rec.get("globs") or [],
        "turn0_catalog": "loaded" if catalog_t0 else "not-loaded",
        "turn0_body": "loaded" if body_t0 else "not-loaded",
        "after_touch_catalog": "loaded" if catalog_t0 else "not-loaded",
        "after_touch_body": "loaded" if body_after else "not-loaded",
        "touch": touch,
        "glob_matched_touch": skill_glob_matched,
        "cli_injects_skill_body_on_glob": False,
    }


def observation_for_rule(rec: dict[str, Any], touch: str | None) -> dict[str, Any]:
    rtype = rec.get("rule_type")
    t0_body = rtype == "global"
    # agentFetched: description listed at turn 0. fileGlobbed: withheld until match.
    t0_catalog = rtype in {"global", "agentFetched"}
    matched = False
    after_body = t0_body
    after_catalog = t0_catalog
    if rtype == "fileGlobbed" and touch:
        matched = any_glob_match(list(rec.get("globs") or []), touch)
        after_body = matched
        after_catalog = matched
    return {
        "id": Path(str(rec.get("path") or "")).name,
        "kind": "rule",
        "path": rec.get("path"),
        "rule_type": rtype,
        "globs": rec.get("globs") or [],
        "paths_key_present": rec.get("paths_key_present"),
        "turn0_catalog": "loaded" if t0_catalog else "not-loaded",
        "turn0_body": "loaded" if t0_body else "not-loaded",
        "after_touch_catalog": "loaded" if after_catalog else "not-loaded",
        "after_touch_body": "loaded" if after_body else "not-loaded",
        "touch": touch,
        "glob_matched_touch": matched,
    }
