"""AUD-0014 live drift: path-set + LF-normalized content, frontmatter model field.

Probe 1 compares repo vs live trees by relative path and LF-normalized bytes.
Probe 2 reads the YAML frontmatter `model` field only — a body mention of
`sonnet` is not an assignment. The opus floor applies to declared models:
undeclared is not a violation; sonnet/haiku (and any other non-opus-family
declared model) is.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0014"
OUT_REL = "command-center/audit/AUD-0014-agents-commands-drift.json"
SCHEMA_REL = "command-center/schema/audit-drift.schema.json"
SCHEMA_REL = SCHEMA_REL
UNIT = UNIT
OUT_REL = OUT_REL
SENTINEL = (
    "SUCCESS:AUD-0014 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "Which agent definitions and slash commands exist live but not in the repo, "
    "differ in content, or declare a model that violates the "
    "opus-for-substantive-subagents floor?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0014/probe1_path_content.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0014/probe2_frontmatter_model.py"
)
P1 = P1
P2 = P2

MENTION_REL = (
    "command-center/p2-wave/probes/AUD-0014/fixtures/body-mention-only.md"
)
SONNET_REL = (
    "command-center/p2-wave/probes/AUD-0014/fixtures/frontmatter-sonnet.md"
)
MENTION_REL = MENTION_REL
SONNET_REL = SONNET_REL
_path_dir = HERE / "fixtures" / "path-control"
if not (_path_dir / "repo").is_dir():
    _path_dir = HERE / "fixtures" / "path-control"
PATH_REPO = _path_dir / "repo"
PATH_LIVE = _path_dir / "live"
PATH_REPO = PATH_REPO
PATH_LIVE = PATH_LIVE

OPUS_PREFIXES = ("opus", "claude-opus")
UNDECLARED_MODELS = frozenset({"", "inherit", "default"})


def live_config_root() -> Path:
    env = (os.environ.get("CLAUDE_CONFIG_DIR") or "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".claude"


def host_surfaces() -> dict[str, tuple[Path, Path]]:
    live = live_config_root()
    return {
        "agents": (REPO / "agents", live / "agents"),
        "commands": (REPO / "commands", live / "commands"),
    }


def lf_bytes(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(lf_bytes(raw)).hexdigest()


def list_md(root: Path) -> dict[str, Path]:
    if not root.is_dir():
        return {}
    out: dict[str, Path] = {}
    for path in sorted(root.rglob("*.md")):
        if path.is_file():
            out[path.relative_to(root).as_posix()] = path
    return out


def compare_trees(repo_root: Path, live_root: Path) -> dict[str, Any]:
    repo_map = list_md(repo_root)
    live_map = list_md(live_root)
    repo_keys = set(repo_map)
    live_keys = set(live_map)
    repo_only = sorted(repo_keys - live_keys)
    live_only = sorted(live_keys - repo_keys)
    common = sorted(repo_keys & live_keys)
    equal: list[str] = []
    different: list[dict[str, str]] = []
    for rel in common:
        r_sha = sha256_bytes(repo_map[rel].read_bytes())
        l_sha = sha256_bytes(live_map[rel].read_bytes())
        if r_sha == l_sha:
            equal.append(rel)
        else:
            different.append(
                {
                    "path": rel,
                    "repo_sha256": r_sha,
                    "live_sha256": l_sha,
                }
            )
    return {
        "repo_path": str(repo_root),
        "live_path": str(live_root),
        "repo_is_dir": repo_root.is_dir(),
        "live_is_dir": live_root.is_dir(),
        "repo_count": len(repo_map),
        "live_count": len(live_map),
        "repo_only": repo_only,
        "live_only": live_only,
        "content_equal": equal,
        "content_different": different,
        "n_repo_only": len(repo_only),
        "n_live_only": len(live_only),
        "n_equal": len(equal),
        "n_different": len(different),
    }


def split_frontmatter(text: str) -> tuple[str | None, str]:
    if not text.startswith("---"):
        return None, text
    rest = text[3:]
    if rest.startswith("\r\n"):
        rest = rest[2:]
    elif rest.startswith("\n"):
        rest = rest[1:]
    else:
        return None, text
    nl = rest.find("\n---")
    if nl < 0:
        return None, text
    block = rest[:nl]
    after = rest[nl + 1 :]
    if after.startswith("---"):
        after = after[3:]
        if after.startswith("\r\n"):
            after = after[2:]
        elif after.startswith("\n"):
            after = after[1:]
    return block, after


def parse_model_field(text: str) -> str | None:
    block, _body = split_frontmatter(text)
    if block is None:
        return None
    try:
        loaded = yaml.safe_load(block) if block.strip() else {}
    except yaml.YAMLError:
        return None
    if not isinstance(loaded, dict):
        return None
    raw = loaded.get("model")
    if raw is None:
        return None
    if isinstance(raw, (int, float, bool)):
        return str(raw)
    if isinstance(raw, str):
        stripped = raw.strip().strip("\"'")
        token = stripped.split()[0] if stripped else ""
        return token or None
    return None


def opus_family(model: str | None) -> bool:
    if model is None:
        return True
    norm = model.strip().lower()
    if norm in UNDECLARED_MODELS:
        return True
    if norm.startswith("claude-opus"):
        return True
    return any(
        norm == prefix or norm.startswith(prefix + "-") or norm.startswith(prefix + "_")
        for prefix in OPUS_PREFIXES
    )


def violates_opus_floor(model: str | None) -> bool:
    return not opus_family(model)


def body_grep_sonnet(text: str) -> bool:
    return "sonnet" in text.lower()


def scan_models(root: Path) -> dict[str, Any]:
    files = list_md(root)
    declared: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    undeclared: list[str] = []
    parse_failures: list[str] = []
    for rel, path in files.items():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            parse_failures.append(rel)
            continue
        model = parse_model_field(text)
        row = {
            "path": rel,
            "model": model,
            "violates_opus_floor": violates_opus_floor(model),
        }
        declared.append(row)
        if model is None:
            undeclared.append(rel)
        if violates_opus_floor(model):
            violations.append(row)
    return {
        "root": str(root),
        "is_dir": root.is_dir(),
        "file_count": len(files),
        "undeclared_count": len(undeclared),
        "undeclared": undeclared,
        "violation_count": len(violations),
        "violations": violations,
        "parse_failure_count": len(parse_failures),
        "parse_failures": parse_failures,
        "definitions": declared,
    }


def use_vs_mention() -> dict[str, Any]:
    mention_text = (REPO / MENTION_REL).read_text(encoding="utf-8")
    sonnet_text = (REPO / SONNET_REL).read_text(encoding="utf-8")
    mention_model = parse_model_field(mention_text)
    sonnet_model = parse_model_field(sonnet_text)
    mention_front = violates_opus_floor(mention_model)
    sonnet_front = violates_opus_floor(sonnet_model)
    mention_grep = body_grep_sonnet(mention_text)
    sonnet_grep = body_grep_sonnet(sonnet_text)
    silent_on_mention = mention_front is False
    fires_on_frontmatter = sonnet_front is True
    return {
        "mention_fixture": MENTION_REL,
        "sonnet_fixture": SONNET_REL,
        "mention_model": mention_model,
        "sonnet_model": sonnet_model,
        "frontmatter_flags_mention": mention_front,
        "frontmatter_flags_sonnet": sonnet_front,
        "body_grep_flags_mention": mention_grep,
        "body_grep_flags_sonnet": sonnet_grep,
        "silent_on_mention": silent_on_mention,
        "fires_on_frontmatter": fires_on_frontmatter,
        "grep_would_flag_mention": mention_grep,
        "both_states_ok": silent_on_mention and fires_on_frontmatter,
        "use_vs_mention_discriminates": silent_on_mention
        and fires_on_frontmatter
        and mention_grep,
        "frontmatter_flags_mention": mention_front,
        "grep_would_flag_mention": mention_grep,
        "both_states_ok": silent_on_mention and fires_on_frontmatter,
    }


def path_control() -> dict[str, Any]:
    cmp_ = compare_trees(PATH_REPO, PATH_LIVE)
    expect_equal = {"keep.md"}
    expect_diff = {"changed.md"}
    expect_repo = {"repo-only.md"}
    expect_live = {"live-only.md"}
    got_equal = set(cmp_["content_equal"])
    got_diff = {row["path"] for row in cmp_["content_different"]}
    got_repo = set(cmp_["repo_only"])
    got_live = set(cmp_["live_only"])
    ok = (
        got_equal == expect_equal
        and got_diff == expect_diff
        and got_repo == expect_repo
        and got_live == expect_live
    )
    vacuous = not got_diff and not got_repo and not got_live
    return {
        **cmp_,
        "expect_equal": sorted(expect_equal),
        "expect_different": sorted(expect_diff),
        "expect_repo_only": sorted(expect_repo),
        "expect_live_only": sorted(expect_live),
        "ok": ok,
        "vacuous": vacuous,
        "fired_on_bad_state": ok and not vacuous,
        "vacuous": vacuous,
        "fired_on_bad_state": ok and not vacuous,
        "content_equal": cmp_["content_equal"],
    }


def measure() -> dict[str, Any]:
    surfaces = host_surfaces()
    host: dict[str, Any] = {}
    models: dict[str, Any] = {}
    for name, (repo_p, live_p) in surfaces.items():
        host[name] = compare_trees(repo_p, live_p)
        models[f"repo_{name}"] = scan_models(repo_p)
        models[f"live_{name}"] = scan_models(live_p)
    uvm = use_vs_mention()
    pctl = path_control()
    n_live_only = host["agents"]["n_live_only"] + host["commands"]["n_live_only"]
    n_repo_only = host["agents"]["n_repo_only"] + host["commands"]["n_repo_only"]
    n_diff = host["agents"]["n_different"] + host["commands"]["n_different"]
    host_violations: list[dict[str, Any]] = []
    for key in ("repo_agents", "live_agents", "repo_commands", "live_commands"):
        for row in models[key]["violations"]:
            host_violations.append({"tree": key, **row})
    any_host_dir = any(
        host[name][side]
        for name in ("agents", "commands")
        for side in ("repo_is_dir", "live_is_dir")
    )
    return {
        "host": host,
        "models": models,
        "use_vs_mention": uvm,
        "path_control": pctl,
        "n_live_only": n_live_only,
        "n_repo_only": n_repo_only,
        "n_content_different": n_diff,
        "n_host_floor_violations": len(host_violations),
        "host_floor_violations": host_violations,
        "any_host_tree_present": any_host_dir,
        "n_host_floor_violations": len(host_violations),
        "any_host_tree_present": any_host_dir,
        "use_vs_mention": uvm,
        "controls_ok": bool(uvm["both_states_ok"] and pctl["ok"]),
        "live_root": str(live_config_root()),
        "repo_root": str(REPO),
    }
