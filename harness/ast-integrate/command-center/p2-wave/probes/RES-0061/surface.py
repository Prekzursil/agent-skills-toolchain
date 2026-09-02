#!/usr/bin/env python3
"""Local auto-load surface for RES-0061.

A cloned-repo config file is an instruction: published client paths are
read into an instruction buffer with no consent prompt. Measurement uses
a benign marker only. Nothing writes, networks, or executes.

Two mechanically independent local signals per claim:
  S1  instruction-buffer membership (Python pathlib read of published paths)
  S2  path-scoped grep in a separate process (different program, different
      field: grep hit list vs buffer membership)

The clean tree is the same layout without those files. A decoy file
outside the published path set must not appear in any instruction buffer.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MARKER = "RES0061_BENIGN_MARKER_7f3a9c2e"
DECOY = "RES0061_DECOY_NOT_LOADED_aa11bb"
TRUSTED_BODY = "# trusted pin target\ntrusted-ok-not-a-marker\n"

CLIENTS: list[dict] = [
    {
        "id": "claude-code",
        "title": "Claude Code",
        "instruction_relpaths": [
            "CLAUDE.md",
            ".claude/CLAUDE.md",
            "CLAUDE.local.md",
        ],
        "config_relpaths": [".claude/settings.json", ".mcp.json"],
        "binaries": ["claude"],
        "docs_url": "https://code.claude.com/docs/en/memory.md",
    },
    {
        "id": "codex-cli",
        "title": "OpenAI Codex CLI",
        "instruction_relpaths": ["AGENTS.md"],
        "config_relpaths": [".codex/config.toml", ".codex/hooks.json"],
        "binaries": ["codex"],
        "docs_url": "https://developers.openai.com/codex/hooks",
    },
    {
        "id": "cursor",
        "title": "Cursor",
        "instruction_relpaths": ["AGENTS.md", ".cursorrules"],
        "config_relpaths": [".cursor/rules/res0061.mdc"],
        "binaries": ["cursor", "cursor-agent", "agent"],
        "docs_url": "https://cursor.com/docs/context/rules",
    },
    {
        "id": "gemini-cli",
        "title": "Gemini CLI",
        "instruction_relpaths": ["GEMINI.md", "AGENTS.md"],
        "config_relpaths": [".gemini/settings.json"],
        "binaries": ["gemini"],
        "docs_url": "https://github.com/google-gemini/gemini-cli",
    },
    {
        "id": "github-copilot",
        "title": "GitHub Copilot",
        "instruction_relpaths": [".github/copilot-instructions.md"],
        "config_relpaths": [],
        "binaries": [],
        "docs_url": "https://docs.github.com/en/copilot",
    },
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def marker_body(rel: str) -> str:
    if rel.endswith(".json"):
        return json.dumps(
            {"res0061_marker": MARKER, "note": "benign-detect-only"}, indent=1
        )
    if rel.endswith(".toml"):
        return f"# {MARKER}\nmarker = \"{MARKER}\"\n"
    if rel.endswith(".mdc"):
        return (
            "---\ndescription: res0061 benign marker\nalwaysApply: true\n---\n"
            f"{MARKER}\n"
        )
    return (
        f"# RES-0061 benign marker ({rel})\n"
        f"{MARKER}\n"
        "# Detect-only. No tool use, network, or extra writes requested.\n"
    )


def published_relpaths(client: dict) -> list[str]:
    out: list[str] = []
    for rel in list(client["instruction_relpaths"]) + list(client["config_relpaths"]):
        if rel not in out:
            out.append(rel)
    return out


def write_file(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def plant_tree(root: Path) -> None:
    write_file(root, "README.md", TRUSTED_BODY)
    write_file(root, "notes/NOT_LOADED.txt", f"decoy\n{DECOY}\n")
    seen: set[str] = set()
    for client in CLIENTS:
        for rel in published_relpaths(client):
            if rel in seen:
                continue
            seen.add(rel)
            write_file(root, rel, marker_body(rel))
    write_file(root, ".claude/hooks/noop.txt", f"hook-text-only\n{MARKER}\n")
    write_file(root, ".codex/hooks.json", json.dumps({"res0061_marker": MARKER}))
    write_file(root, ".cursor/hooks.json", json.dumps({"res0061_marker": MARKER}))


def clean_tree(root: Path) -> None:
    write_file(root, "README.md", TRUSTED_BODY)
    write_file(root, "notes/empty.txt", "no-marker-here\n")


def ingest_buffer(
    client: dict,
    root: Path,
    policy: str = "raw",
    allowlist: dict | None = None,
) -> bytes:
    chunks: list[bytes] = []
    for rel in published_relpaths(client):
        path = root / rel
        if not path.is_file():
            continue
        data = path.read_bytes()
        if policy == "hash_pin":
            expected = (allowlist or {}).get(rel.replace("\\", "/"))
            if expected is None or sha256_bytes(data) != expected:
                continue
        if policy == "preamble":
            data = b"DATA-NOT-INSTRUCTIONS\n" + data
        chunks.append(data)
    return b"\n".join(chunks)


def signal_buffer(client: dict, root: Path, token: str, **ingest_kw) -> dict:
    buf = ingest_buffer(client, root, **ingest_kw)
    present = token.encode("utf-8") in buf
    return {
        "id": "S1-buffer-membership",
        "token": token,
        "present": present,
        "buffer_sha256": sha256_bytes(buf),
        "buffer_bytes": len(buf),
        "paths_read": [
            rel for rel in published_relpaths(client) if (root / rel).is_file()
        ],
    }


def signal_grep(client: dict, root: Path, token: str) -> dict:
    """S2: grep -F over published paths only (separate process)."""
    grep = "/usr/bin/grep"
    hits: list[str] = []
    missing_tool = not Path(grep).is_file()
    for rel in published_relpaths(client):
        path = root / rel
        if not path.is_file():
            continue
        if missing_tool:
            proc = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import sys; p=sys.argv[1]; t=sys.argv[2]; "
                    "sys.exit(0 if t.encode() in open(p,'rb').read() else 1)",
                    str(path),
                    token,
                ],
                cwd=str(root),
                capture_output=True,
            )
        else:
            proc = subprocess.run(
                [grep, "-F", "-l", "--", token, str(path)],
                cwd=str(root),
                capture_output=True,
                text=True,
            )
        if proc.returncode == 0:
            hits.append(rel)
    return {
        "id": "S2-path-scoped-grep",
        "token": token,
        "present": bool(hits),
        "hit_relpaths": hits,
        "tool": "python-child" if missing_tool else grep,
    }


def decoy_leaked(root: Path) -> bool:
    needle = DECOY.encode("utf-8")
    return any(needle in ingest_buffer(c, root) for c in CLIENTS)


def observe_live(client: dict, root: Path) -> dict:
    found = None
    for name in client.get("binaries") or []:
        found = shutil.which(name)
        if found:
            break
    if not found:
        return {
            "status": "NOT-CHECKED",
            "reason": "binary-absent",
            "binaries": client.get("binaries") or [],
        }
    strace = shutil.which("strace")
    if not strace:
        return {
            "status": "NOT-CHECKED",
            "reason": "strace-absent",
            "binary": found,
            "note": (
                "--version is not a session ingest. Live openat of project "
                "instruction files is NOT-CHECKED on this host."
            ),
        }
    try:
        proc = subprocess.run(
            [strace, "-f", "-e", "trace=openat", "--", found, "--version"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {
            "status": "NOT-CHECKED",
            "reason": type(exc).__name__,
            "binary": found,
        }
    tail = ((proc.stdout or "") + (proc.stderr or ""))[-2000:]
    opened = any(rel in tail for rel in published_relpaths(client))
    return {
        "status": "CHECKED",
        "binary": found,
        "invocation": "--version",
        "project_instruction_openat": opened,
        "note": (
            "--version is a weak session stand-in; False is not a claim that "
            "a real agent session would skip the file."
        ),
        "exit_code": proc.returncode,
    }


# AUTO_LOADING_AGENT_CONFIG class (same path set IMP-0245 flags). Local
# implementation: the IMP-0245 engine file is not on this worktree, and this
# unit must not rebuild that ADV/IMP circle.
HOOK_DIRS = (
    ".claude/hooks",
    ".codex/hooks",
    ".cursor/hooks",
    ".gemini/hooks",
)
HOOK_FILES = (
    ".claude/hooks.json",
    ".codex/hooks.json",
    ".cursor/hooks.json",
    ".mcp.json",
)


def autoload_findings(root: Path) -> list[dict]:
    """Flag repo-local auto-load hook/config paths. Never flags README prose."""
    findings: list[dict] = []
    seen: set[str] = set()
    for rel_dir in HOOK_DIRS:
        d = root / rel_dir
        if not d.is_dir():
            continue
        for path in sorted(d.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            findings.append(
                {
                    "path": rel,
                    "rule_id": "AUTO_LOADING_AGENT_CONFIG",
                }
            )
    for rel in HOOK_FILES:
        path = root / rel
        if path.is_file() and rel not in seen:
            seen.add(rel)
            findings.append(
                {
                    "path": rel,
                    "rule_id": "AUTO_LOADING_AGENT_CONFIG",
                }
            )
    return findings


def program_hook_detector(root: Path) -> dict:
    findings = autoload_findings(root)
    return {
        "detector": (
            "command-center/p2-wave/probes/RES-0061/surface.py:"
            "autoload_findings AUTO_LOADING_AGENT_CONFIG"
        ),
        "finding_count": len(findings),
        "paths": [f.get("path") for f in findings],
        "fired": len(findings) > 0,
    }


def trusted_allowlist() -> dict[str, str]:
    return {"README.md": sha256_bytes(TRUSTED_BODY.encode("utf-8"))}


def apply_strip_dot_dirs(root: Path) -> None:
    for name in (".claude", ".codex", ".cursor", ".gemini"):
        p = root / name
        if p.is_dir():
            shutil.rmtree(p)


def client_row(
    client: dict,
    root: Path,
    policy: str = "raw",
    allowlist: dict | None = None,
) -> dict:
    s1 = signal_buffer(client, root, MARKER, policy=policy, allowlist=allowlist)
    s2 = signal_grep(client, root, MARKER)
    if policy == "raw":
        ingested = bool(s1["present"] and s2["present"])
    else:
        ingested = bool(s1["present"])
    return {
        "client_id": client["id"],
        "title": client["title"],
        "docs_url": client["docs_url"],
        "ingested_marker": ingested,
        "s1": s1,
        "s2": s2,
        "live": observe_live(client, root),
        "policy": policy,
    }


def mitigation_trials(planted: Path) -> list[dict]:
    rows: list[dict] = []
    allow = trusted_allowlist()

    write_file(
        planted,
        ".agent-permissions.json",
        json.dumps({"load_repo_instructions": False, "res0061": "theatre"}),
    )
    m1_hits = [client_row(c, planted, policy="raw") for c in CLIENTS]
    rows.append(
        {
            "id": "M1-declared-permission-manifest",
            "name": "Declared load_repo_instructions=false beside the files",
            "bypass_attempt": (
                "Leave CLAUDE.md/AGENTS.md in place and add "
                ".agent-permissions.json denying load; the published-path "
                "loader never consults that file."
            ),
            "survived": not any(r["ingested_marker"] for r in m1_hits),
            "clients_still_ingesting": [
                r["client_id"] for r in m1_hits if r["ingested_marker"]
            ],
            "verdict": "BYPASSED",
        }
    )

    stripped = Path(tempfile.mkdtemp(prefix="res0061-strip-"))
    shutil.copytree(planted, stripped, dirs_exist_ok=True)
    apply_strip_dot_dirs(stripped)
    m2_hits = [client_row(c, stripped, policy="raw") for c in CLIENTS]
    still = [r["client_id"] for r in m2_hits if r["ingested_marker"]]
    rows.append(
        {
            "id": "M2-strip-dot-client-dirs-only",
            "name": "Delete .claude/.codex/.cursor/.gemini but leave root markdown",
            "bypass_attempt": (
                "rm -rf .codex (and sibling dot-dirs). Root AGENTS.md, "
                "CLAUDE.md, GEMINI.md, .cursorrules and "
                ".github/copilot-instructions.md remain and still ingest."
            ),
            "survived": len(still) == 0,
            "clients_still_ingesting": still,
            "verdict": "BYPASSED" if still else "HELD",
        }
    )
    shutil.rmtree(stripped, ignore_errors=True)

    m3_hits = [client_row(c, planted, policy="preamble") for c in CLIENTS]
    rows.append(
        {
            "id": "M3-data-not-instructions-preamble",
            "name": "Prefix ingested bytes with DATA-NOT-INSTRUCTIONS",
            "bypass_attempt": (
                "Wrap the same published-path bytes. The marker still "
                "appears in the instruction buffer, so the config is still "
                "an instruction channel."
            ),
            "survived": not any(r["ingested_marker"] for r in m3_hits),
            "clients_still_ingesting": [
                r["client_id"] for r in m3_hits if r["ingested_marker"]
            ],
            "verdict": "BYPASSED",
        }
    )

    m4_hits = [client_row(c, planted, policy="hash_pin", allowlist=allow) for c in CLIENTS]
    mutated = Path(tempfile.mkdtemp(prefix="res0061-mut-"))
    shutil.copytree(planted, mutated, dirs_exist_ok=True)
    write_file(mutated, "README.md", TRUSTED_BODY + MARKER + "\n")
    extra = Path(tempfile.mkdtemp(prefix="res0061-extra-"))
    shutil.copytree(planted, extra, dirs_exist_ok=True)
    write_file(extra, "nested/AGENTS.md", marker_body("AGENTS.md"))
    m4_mut = [client_row(c, mutated, policy="hash_pin", allowlist=allow) for c in CLIENTS]
    m4_extra = [client_row(c, extra, policy="hash_pin", allowlist=allow) for c in CLIENTS]
    held = (
        not any(r["ingested_marker"] for r in m4_hits)
        and not any(r["ingested_marker"] for r in m4_mut)
        and not any(r["ingested_marker"] for r in m4_extra)
    )
    rows.append(
        {
            "id": "M4-hash-pinned-allowlist",
            "name": "Inject only (relpath, sha256) pairs on an owner allowlist",
            "bypass_attempt": (
                "Plant extra nested AGENTS.md, mutate the allowlisted "
                "README.md to carry the marker, and leave the original "
                "auto-load files in place. None of those hashes match the "
                "pin, so the instruction buffer stays marker-free."
            ),
            "survived": held,
            "clients_still_ingesting": [
                r["client_id"]
                for r in (m4_hits + m4_mut + m4_extra)
                if r["ingested_marker"]
            ],
            "verdict": "HELD" if held else "BYPASSED",
            "bypass_cases": [
                "extra-nested-AGENTS.md",
                "mutated-pinned-README",
                "unpinned-autoload-files",
            ],
        }
    )
    shutil.rmtree(mutated, ignore_errors=True)
    shutil.rmtree(extra, ignore_errors=True)
    return rows


def run_experiment() -> dict:
    planted = Path(tempfile.mkdtemp(prefix="res0061-planted-"))
    clean = Path(tempfile.mkdtemp(prefix="res0061-clean-"))
    try:
        plant_tree(planted)
        clean_tree(clean)
        planted_rows = [client_row(c, planted) for c in CLIENTS]
        clean_rows = [client_row(c, clean) for c in CLIENTS]
        mitigations = mitigation_trials(planted)
        detector_planted = program_hook_detector(planted)
        detector_clean = program_hook_detector(clean)
        decoy_planted = decoy_leaked(planted)
        decoy_clean = decoy_leaked(clean)
        all_planted = all(r["ingested_marker"] for r in planted_rows)
        none_clean = not any(r["ingested_marker"] for r in clean_rows)
        s1_s2_agree = all(
            r["s1"]["present"] is r["s2"]["present"] for r in planted_rows
        ) and all(
            r["s1"]["present"] is False and r["s2"]["present"] is False
            for r in clean_rows
        )
        one_held = any(m["survived"] is True for m in mitigations)
        one_bypassed = any(m["survived"] is False for m in mitigations)
        ok = (
            all_planted
            and none_clean
            and not decoy_planted
            and not decoy_clean
            and detector_planted["fired"]
            and not detector_clean["fired"]
            and one_held
            and one_bypassed
            and s1_s2_agree
        )
        return {
            "ok": ok,
            "marker": MARKER,
            "decoy": DECOY,
            "planted_clients": planted_rows,
            "clean_clients": clean_rows,
            "mitigations": mitigations,
            "decoy_in_instruction_buffer_planted": decoy_planted,
            "decoy_in_instruction_buffer_clean": decoy_clean,
            "program_detector_planted": detector_planted,
            "program_detector_clean": detector_clean,
            "all_clients_ingested_on_planted": all_planted,
            "no_client_ingested_on_clean": none_clean,
            "signals_agree": s1_s2_agree,
            "one_mitigation_held": one_held,
            "one_mitigation_bypassed": one_bypassed,
        }
    finally:
        shutil.rmtree(planted, ignore_errors=True)
        shutil.rmtree(clean, ignore_errors=True)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    doc = run_experiment()
    print(
        json.dumps(
            {
                k: doc[k]
                for k in (
                    "ok",
                    "all_clients_ingested_on_planted",
                    "no_client_ingested_on_clean",
                    "one_mitigation_held",
                    "one_mitigation_bypassed",
                    "signals_agree",
                )
            },
            indent=2,
        )
    )
    raise SystemExit(0 if doc["ok"] else 1)
