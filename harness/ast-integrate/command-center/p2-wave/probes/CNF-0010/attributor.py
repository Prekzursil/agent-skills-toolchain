"""Attribute a confirmer/implementer disagreement to environment vs code."""

from __future__ import annotations

from copy import deepcopy

from contract import CI_RUFF_PIN, FORCED_RUFF


def _tool_map(manifest: dict) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for row in manifest.get("tools") or []:
        if isinstance(row, dict) and row.get("name"):
            out[str(row["name"])] = row.get("version")
    return out


def flatten_env(manifest: dict) -> dict[str, str]:
    os_ = manifest.get("os") or {}
    git = manifest.get("git") or {}
    py = manifest.get("python") or {}
    node = manifest.get("node") or {}
    loc = manifest.get("locale") or {}
    flat = {
        "os.family": str(os_.get("family") or ""),
        "os.build": str(os_.get("build") or ""),
        "git.autocrlf": str(git.get("autocrlf") or ""),
        "python.version": str(py.get("version") or ""),
        "node.version": str(node.get("version") or ""),
        "locale.lang": str(loc.get("lang") or ""),
        "locale.code_page": str(loc.get("code_page") or ""),
    }
    for name, ver in _tool_map(manifest).items():
        flat[f"tools.{name}.version"] = str(ver or "")
    return flat


def manifest_delta(a: dict, b: dict) -> list[str]:
    fa, fb = flatten_env(a), flatten_env(b)
    keys = sorted(set(fa) | set(fb))
    return [k for k in keys if fa.get(k) != fb.get(k)]


def attribute(
    implementer: dict,
    confirmer: dict,
    *,
    implementer_source_sha: str,
    confirmer_source_sha: str,
) -> dict:
    delta = manifest_delta(implementer, confirmer)
    source_same = implementer_source_sha == confirmer_source_sha
    if delta and source_same:
        verdict = "environment"
    elif (not delta) and (not source_same):
        verdict = "code"
    elif delta and (not source_same):
        verdict = "mixed"
    else:
        verdict = "unknown"
    return {
        "attribution": verdict,
        "delta_fields": delta,
        "source_sha_same": source_same,
        "explained_by_manifest_delta_alone": verdict == "environment",
    }


def set_tool_version(manifest: dict, name: str, version: str) -> dict:
    clone = deepcopy(manifest)
    found = False
    for row in clone.get("tools") or []:
        if row.get("name") == name:
            row["version"] = version
            found = True
    if not found:
        tools = list(clone.get("tools") or [])
        tools.append(
            {
                "name": name,
                "resolved_by": "powershell-resolver",
                "resolved_path": None,
                "version": version,
            }
        )
        clone["tools"] = tools
    return clone


def forced_mismatch(live: dict) -> dict:
    """Force ruff 0.15.17 vs 0.15.22 on identical source bytes."""
    pinned = set_tool_version(live, "ruff", CI_RUFF_PIN)
    forced = set_tool_version(live, "ruff", FORCED_RUFF)
    sha = "same-source-bytes-control"
    result = attribute(
        pinned,
        forced,
        implementer_source_sha=sha,
        confirmer_source_sha=sha,
    )
    return {
        "tool": "ruff",
        "pinned_version": CI_RUFF_PIN,
        "forced_version": FORCED_RUFF,
        "source_sha_same": True,
        "attribution": result["attribution"],
        "not_code": result["attribution"] != "code",
        "delta_fields": result["delta_fields"],
        "explained_by_manifest_delta_alone": result["explained_by_manifest_delta_alone"],
    }


def code_control(live: dict) -> dict:
    """Same environment, different source digest → code, not environment."""
    return attribute(
        live,
        live,
        implementer_source_sha="aaa",
        confirmer_source_sha="bbb",
    )
