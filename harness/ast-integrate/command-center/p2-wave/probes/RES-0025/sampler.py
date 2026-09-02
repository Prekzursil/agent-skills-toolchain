"""Sample public Cursor rule files; classify documented vs used; never drop unparsed."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CAPTURES = HERE / "fixtures" / "captures"
META = CAPTURES / "fetch-meta.json"
FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", re.S)

DOCUMENTED_FEATURES = (
    "mdc_extension",
    "yaml_frontmatter",
    "description",
    "globs",
    "alwaysApply",
    "apply_mode_always",
    "apply_mode_glob",
    "apply_mode_intelligent",
    "apply_mode_manual",
    "nested_folders",
    "plain_md_ignored_by_cursor",
    "agents_md",
    "team_rules_dashboard",
    "user_rules_settings",
    "create_rule_slash",
    "remote_github_import",
    "at_mention_apply",
    "at_file_include",
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _parse_scalar(v: str) -> Any:
    v = v.strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    if v.lower() in ("null", "~", ""):
        return ""
    return v


def parse_frontmatter_block(block: str) -> dict[str, Any]:
    """Small YAML subset used by public .mdc files. Raises on garbage."""
    keys: dict[str, Any] = {}
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        if line.startswith((" ", "\t")):
            raise ValueError(f"orphan-indent:{line!r}")
        if ":" not in line:
            raise ValueError(f"no-colon:{line!r}")
        k, rest = line.split(":", 1)
        k = k.strip()
        if not k or " " in k:
            raise ValueError(f"bad-key:{k!r}")
        rest = rest.strip()
        if rest == "|":
            raise ValueError("literal-block-unsupported")
        if rest.startswith("[") and "]" not in rest:
            buf = rest
            i += 1
            while i < len(lines) and "]" not in buf:
                buf += " " + lines[i].strip()
                i += 1
            rest = buf
            if "]" not in rest:
                raise ValueError("unclosed-flow-list")
        elif rest == "":
            items: list[str] = []
            j = i + 1
            while j < len(lines) and re.match(r"^[\t ]*- ", lines[j]):
                items.append(_parse_scalar(lines[j].lstrip()[2:]))
                j += 1
            keys[k] = items if items else ""
            i = j
            continue
        i += 1
        if rest.startswith("[") and rest.endswith("]"):
            inner = rest[1:-1].strip()
            if not inner:
                keys[k] = []
            else:
                parts: list[str] = []
                cur = ""
                q = None
                for ch in inner:
                    if q:
                        if ch == q:
                            q = None
                        cur += ch
                    elif ch in ("'", '"'):
                        q = ch
                        cur += ch
                    elif ch == ",":
                        parts.append(_parse_scalar(cur))
                        cur = ""
                    else:
                        cur += ch
                if cur.strip():
                    parts.append(_parse_scalar(cur))
                keys[k] = [p for p in parts if p != ""]
        else:
            keys[k] = _parse_scalar(rest)
    return keys


def glob_nonempty(value: Any) -> bool:
    if value is True or value is False:
        return False
    if value is None:
        return False
    if isinstance(value, list):
        return any(str(x).strip() for x in value)
    return bool(str(value).strip())


def infer_apply_mode(fm: dict[str, Any]) -> str:
    always = fm.get("alwaysApply")
    desc = str(fm.get("description") or "").strip()
    globs = glob_nonempty(fm.get("globs"))
    if always is True:
        return "always"
    if globs:
        return "glob"
    if desc:
        return "intelligent"
    return "manual"


def classify_text(path: str, text: str) -> dict[str, Any]:
    """Parse one rule file. On failure, parsed=False and reason set — never silent-drop."""
    rec: dict[str, Any] = {
        "path": path,
        "parsed": False,
        "unparse_reason": None,
        "extension": Path(path).suffix.lower(),
        "frontmatter": {},
        "features": {},
        "apply_mode": None,
        "sha256": sha256_bytes(text.encode("utf-8")),
        "bytes": len(text.encode("utf-8")),
    }
    m = FM_RE.match(text)
    if not m:
        rec["unparse_reason"] = "no-yaml-frontmatter"
        rec["features"] = {k: False for k in DOCUMENTED_FEATURES}
        rec["features"]["mdc_extension"] = path.endswith(".mdc")
        rec["features"]["plain_md_ignored_by_cursor"] = path.endswith(".md")
        return rec
    try:
        fm = parse_frontmatter_block(m.group(1))
    except Exception as exc:
        rec["unparse_reason"] = f"frontmatter-parse:{exc}"
        rec["features"] = {k: False for k in DOCUMENTED_FEATURES}
        rec["features"]["mdc_extension"] = path.endswith(".mdc")
        rec["features"]["yaml_frontmatter"] = True
        return rec
    mode = infer_apply_mode(fm)
    rec["parsed"] = True
    rec["frontmatter"] = fm
    rec["apply_mode"] = mode
    rec["features"] = {
        "mdc_extension": path.endswith(".mdc"),
        "yaml_frontmatter": True,
        "description": bool(str(fm.get("description") or "").strip()),
        "globs": glob_nonempty(fm.get("globs")),
        "alwaysApply": "alwaysApply" in fm,
        "apply_mode_always": mode == "always",
        "apply_mode_glob": mode == "glob",
        "apply_mode_intelligent": mode == "intelligent",
        "apply_mode_manual": mode == "manual",
        "nested_folders": "/" in path.replace("\\", "/") and path.replace("\\", "/").count("/") >= 1,
        "plain_md_ignored_by_cursor": path.endswith(".md"),
        "agents_md": False,
        "team_rules_dashboard": False,
        "user_rules_settings": False,
        "create_rule_slash": False,
        "remote_github_import": False,
        "at_mention_apply": mode == "manual",
        "at_file_include": "@" in text.split("---", 2)[-1] if text.count("---") >= 2 else "@" in text,
    }
    return rec


def classify_file(path: Path, logical_path: str | None = None) -> dict[str, Any]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return {
            "path": logical_path or path.name,
            "parsed": False,
            "unparse_reason": f"not-utf8:{exc}",
            "extension": path.suffix.lower(),
            "frontmatter": {},
            "features": {k: False for k in DOCUMENTED_FEATURES},
            "apply_mode": None,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
    rec = classify_text(logical_path or path.name, text)
    rec["sha256"] = sha256_bytes(raw)
    rec["bytes"] = len(raw)
    return rec


def load_sample_meta() -> list[dict[str, Any]]:
    data = json.loads(META.read_text(encoding="utf-8"))
    return list(data["sample"])


def sample_public_rules(extra_files: list[tuple[Path, str]] | None = None) -> dict[str, Any]:
    """Run the contracted 20-file sample. extra_files are appended, never replacing.

    Unparsed files stay in `files` with parsed=False. They are counted, not dropped.
    """
    meta_rows = load_sample_meta()
    files: list[dict[str, Any]] = []
    for row in meta_rows:
        saved = REPO / row["saved_as"]
        rec = classify_file(saved, row["path"])
        rec["http_status"] = row.get("http_status")
        rec["fetch_timestamp"] = row.get("fetch_timestamp")
        rec["permalink"] = row.get("permalink")
        rec["raw_url"] = row.get("raw_url")
        rec["capture_sha256"] = row.get("sha256")
        rec["repo"] = row.get("repo")
        files.append(rec)
    if extra_files:
        for path, logical in extra_files:
            files.append(classify_file(path, logical))

    n = len(files)
    parsed = [f for f in files if f["parsed"]]
    unparsed = [f for f in files if not f["parsed"]]
    # Control invariant: nothing is dropped.
    if len(parsed) + len(unparsed) != n:
        raise RuntimeError("sampler-dropped-files")

    counts: dict[str, int] = {k: 0 for k in DOCUMENTED_FEATURES}
    mode_counts = {"always": 0, "glob": 0, "intelligent": 0, "manual": 0}
    for f in parsed:
        for k, v in f["features"].items():
            if v:
                counts[k] = counts.get(k, 0) + 1
        if f["apply_mode"] in mode_counts:
            mode_counts[f["apply_mode"]] += 1

    public_n = len(meta_rows)
    table = feature_table(counts, parsed_n=len(parsed), public_n=public_n)
    return {
        "attempted": n,
        "public_sample_size": public_n,
        "parsed_count": len(parsed),
        "unparsed_count": len(unparsed),
        "unparsed_paths": [u["path"] for u in unparsed],
        "unparsed": [
            {"path": u["path"], "reason": u["unparse_reason"], "sha256": u["sha256"]}
            for u in unparsed
        ],
        "mode_counts": mode_counts,
        "feature_counts": counts,
        "feature_table": table,
        "files": files,
        "dropped_files": 0,
        "control": "unparsed files are listed and counted; they are not omitted from files[]",
    }


def this_program_rule_system() -> dict[str, Any]:
    recon = REPO / "tools/plugin/registration_reconciler.py"
    a2_rule = (
        REPO
        / "command-center/p2-wave/probes/ARC-0016/fixtures/hatch-run/hatch/rules/rule.no-secrets.md"
    )
    a1_census = (
        REPO
        / "command-center/p2-wave/probes/ARC-0005/fixtures/census/repo/rules/common/security.md"
    )
    recon_text = recon.read_text(encoding="utf-8")
    md_only = 'path.suffix.lower() != ".md"' in recon_text
    no_frontmatter = "alwaysApply" not in recon_text and "globs:" not in recon_text
    a2_text = a2_rule.read_text(encoding="utf-8")
    census_text = a1_census.read_text(encoding="utf-8")
    return {
        "loader": "tools/plugin/registration_reconciler.py:_rule_id_from_path",
        "accepts_extension": ".md only ( .mdc returns None )",
        "md_only_check_present": md_only,
        "parses_yaml_frontmatter": False,
        "alwaysApply_in_loader": False,
        "globs_in_loader": False,
        "identity": "relative path under rules/",
        "nested_directories": "organizational path segments only (common/, project/)",
        "generated_rule_provenance": "HTML comment, not YAML frontmatter",
        "a2_rule_has_yaml_frontmatter": a2_text.startswith("---"),
        "a2_rule_has_html_comment_provenance": a2_text.lstrip().startswith("<!--"),
        "census_rule_has_frontmatter": census_text.startswith("---"),
        "no_frontmatter_strings_in_loader": no_frontmatter,
        "sha256_loader": sha256_file(recon),
        "sha256_a2_rule": sha256_file(a2_rule),
        "sha256_census_rule": sha256_file(a1_census),
        "loader_line_snippet": next(
            line
            for line in recon_text.splitlines()
            if 'suffix.lower() != ".md"' in line
        ),
    }


def feature_table(counts: dict[str, int], parsed_n: int, public_n: int) -> list[dict[str, Any]]:
    """Documented-from-used table. used_count is among successfully parsed public files."""
    prog = {
        "mdc_extension": False,
        "yaml_frontmatter": False,
        "description": False,
        "globs": False,
        "alwaysApply": False,
        "apply_mode_always": True,  # every indexed .md is in the tree; no per-file attach
        "apply_mode_glob": False,
        "apply_mode_intelligent": False,
        "apply_mode_manual": False,
        "nested_folders": True,
        "plain_md_ignored_by_cursor": False,  # this program requires .md
        "agents_md": False,
        "team_rules_dashboard": False,
        "user_rules_settings": False,
        "create_rule_slash": False,
        "remote_github_import": False,
        "at_mention_apply": False,
        "at_file_include": False,
    }
    documented = {k: True for k in DOCUMENTED_FEATURES}
    # "used" here means observed in the public file sample, not in Cursor UI.
    ui_only = {
        "team_rules_dashboard",
        "user_rules_settings",
        "create_rule_slash",
        "remote_github_import",
        "agents_md",
    }
    portable = {
        "mdc_extension": False,  # other clients typically load .md
        "yaml_frontmatter": True,
        "description": True,  # as data; intelligent attach is not
        "globs": True,  # as metadata; matching is client-specific
        "alwaysApply": True,  # as metadata
        "apply_mode_always": True,
        "apply_mode_glob": True,
        "apply_mode_intelligent": False,
        "apply_mode_manual": False,
        "nested_folders": True,
        "plain_md_ignored_by_cursor": False,
        "agents_md": True,
        "team_rules_dashboard": False,
        "user_rules_settings": False,
        "create_rule_slash": False,
        "remote_github_import": False,
        "at_mention_apply": False,
        "at_file_include": False,
    }
    notes = {
        "mdc_extension": "Cursor docs: project rules must be .mdc. This program indexes .md only.",
        "yaml_frontmatter": "Cursor: description/globs/alwaysApply. This program has no frontmatter parser.",
        "description": "Documented for Apply Intelligently. Used in 20/20 sampled files even when globs also set.",
        "globs": "Documented auto-attach. Dominant used attach mechanism in this sample.",
        "alwaysApply": "Documented always-on. Rare in sample (explicit true on 1 file).",
        "apply_mode_always": "Documented. Used when alwaysApply: true.",
        "apply_mode_glob": "Documented. Dominant in sample, including globs: **/* as always-on workaround.",
        "apply_mode_intelligent": "Documented (description, no globs, alwaysApply false). Unused in this 20-file sample.",
        "apply_mode_manual": "Documented (@-mention). Unused in this 20-file sample.",
        "nested_folders": "Documented under .cursor/rules/frontend/. Sample paths are mostly rules-mdc/ corpora.",
        "plain_md_ignored_by_cursor": "Documented: .md in .cursor/rules is ignored. Sample includes one .md with frontmatter.",
        "agents_md": "Documented alternative. Not a .mdc file feature; not in this file sample.",
        "team_rules_dashboard": "Documented dashboard/enforce. Not file-based. Not in this program.",
        "user_rules_settings": "Documented in Customize. Not a project file. Not in this program.",
        "create_rule_slash": "Documented /create-rule. Cursor UI. Not portable.",
        "remote_github_import": "Documented Customize import. Cursor UI. Not portable.",
        "at_mention_apply": "Documented manual apply. Cursor chat UI. Not portable.",
        "at_file_include": "Documented @filename in rule body. Client context inclusion. Not portable.",
    }
    denom = parsed_n if parsed_n else 1
    rows = []
    for feat in DOCUMENTED_FEATURES:
        used = counts.get(feat, 0)
        rows.append(
            {
                "feature": feat,
                "documented": documented[feat],
                "used_in_sample_count": None if feat in ui_only else used,
                "used_in_sample": False if feat in ui_only else used > 0,
                "used_rate_among_parsed": None if feat in ui_only else round(used / denom, 4),
                "in_this_program": prog[feat],
                "portable_as_file_based_rule": portable[feat],
                "cursor_expresses_this_program_does_not": documented[feat] and not prog[feat],
                "note": notes[feat],
                "public_sample_size": public_n,
                "parsed_n": parsed_n,
            }
        )
    return rows
