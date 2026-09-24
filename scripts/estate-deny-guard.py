#!/usr/bin/env python3
"""Estate deny-guard: AUTO-BLOCK forbidden actions. Allow everything else.

Runtimes:
  --runtime claude  Claude Code PreToolUse (JSON permissionDecision deny)
  --runtime grok    Grok PreToolUse ({"decision":"deny","reason":...})
  --runtime cursor  Cursor beforeShellExecution ({"permission":"deny"|"allow"})

Fail-open: malformed stdin, missing fields, or any exception -> allow
(except Cursor, which must emit ASCII JSON or the 3.13.10 client blocks).
UTF-8 no BOM. Decision JSON is the FIRST and only stdout on the hot path.
"""
from __future__ import annotations

import json
import os
import re
import sys

REASON = {
    "never-rotate": (
        "NEVER-ROTATE (28.08.2026): do not rotate, revoke, regenerate, or touch "
        "a credential-rotation manifest. Owner handles credential lifecycle."
    ),
    "repo-public": (
        "PRIVATE-ONLY: refusing gh visibility=public on agent-skills-toolchain "
        "(or any gh repo edit --visibility public). That is a credential leak."
    ),
    "force-push": (
        "Refusing git push --force / --force-with-lease / -f. Protected history."
    ),
    "no-verify": (
        "Refusing git --no-verify (commit or push). Hooks are the safety layer."
    ),
    "secret-file": (
        "Refusing commit/add/write of raw secret files "
        "(*.key, *.pem, *token*, local.json) OUTSIDE the private vault. "
        "Owner policy 24.09.2026: inside the private agent-skills-toolchain "
        "checkout everything may be stored in plain text; this rule now "
        "protects the OTHER estate repos, several of which are public."
    ),
}

ROTATE_RE = re.compile(
    r"(credential[_\-]?rotation[_\-]?manifest"
    r"|rotate[_\-]?credentials?"
    r"|gh\s+auth\s+refresh"
    r"|aws\s+iam\s+(create|delete|update)-access-key"
    r"|az\s+ad\s+app\s+credential\s+(reset|delete)"
    r"|gcloud\s+iam\s+service-accounts\s+keys\s+(create|delete)"
    r"|oauth2?.*token.*revoke"
    r"|revoke[_\-]?token)",
    re.I,
)
PUBLIC_RE = re.compile(
    r"gh\s+repo\s+edit\b[\s\S]{0,200}--visibility\s+public"
    r"|gh\s+repo\s+create\b[\s\S]{0,200}(--public\b|--visibility\s+public)"
    r"|visibility['\"]?\s*[:=]\s*['\"]?public",
    re.I,
)
TOOLCHAIN_RE = re.compile(r"agent-skills-toolchain", re.I)

# Owner policy, 24.09.2026: the PRIVATE agent-skills-toolchain repo is the
# estate's durable store. Everything may live there in plain text -- credentials
# included -- EXCEPT cache and build residue. What makes this safe is PUBLIC_RE
# above (refusing to flip the repo public), NOT censoring what goes in.
# Do not weaken PUBLIC_RE; it is now load-bearing.
PRIVATE_VAULT_ROOTS = (
    os.path.join(os.path.expanduser("~"), ".agents"),
    os.path.join("C:\\", "suite", "payload", "Users", "Prekzursil", ".agents"),
    os.path.join(os.path.expanduser("~"), "source", "agent-skills-toolchain"),
)


def _norm(p: str) -> str:
    q = p.strip().strip('"').strip("'")
    return os.path.normcase(os.path.normpath(q)).replace("\\", "/")


def _in_private_vault(path: str, cwd: str = "") -> bool:
    """True if path, resolved against cwd, sits inside a private-vault checkout."""
    if not path and not cwd:
        return False
    try:
        cand = path or ""
        if cand and not os.path.isabs(cand) and cwd:
            cand = os.path.join(cwd, cand)
        cand = _norm(cand or cwd)
        for root in PRIVATE_VAULT_ROOTS:
            r = _norm(root)
            if cand == r or cand.startswith(r + "/"):
                return True
    except Exception:
        return False
    return False


# L-11 fix. The old code split the ENTIRE command string and tested every
# whitespace fragment as a candidate path, so ordinary prose in a heredoc or a
# -m message tripped the secret-file rule on any git write (it blocked three
# legitimate operations on 2026-09-23). Strip message and heredoc bodies first,
# then consider only tokens that actually look like paths.
_HEREDOC_RE = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?[\s\S]*?^\1\s*$", re.M)
_MSG_RE = re.compile(r"(?:-m|--message)\s+('[^']*'|\"[^\"]*\"|\S+)")
_HD_TAG_RE = re.compile(r"<<-?\s*['\"]?\w+['\"]?")
_PATHY_RE = re.compile(r"[\/]|\.[A-Za-z0-9]{1,8}$")


# Use-vs-mention fix, 24.09.2026. Every rule below matches the literal text of
# the command. Writing a file whose CONTENT mentions a forbidden command -- a
# test, a runbook, a policy note -- therefore tripped the rule and blocked the
# write. That is the "agent freaks out about its own documentation" failure, and
# it blocked five legitimate writes across 2026-09-23/24.
#
# A heredoc fed to a FILE SINK is data, not code, so strip it before matching.
# A heredoc fed to an INTERPRETER (bash/sh/pwsh/python) IS code and is NOT
# stripped, so a forbidden command smuggled inside an executed heredoc still
# blocks. Same treatment for -m/--message bodies, which are never executed.
_SINK_RE = re.compile(
    r"(?:^|[|;&]\s*)\s*(?:cat|tee)\s*>{1,2}"
    r"|git\s+(?:commit|tag|notes)\b[^\n]*\s-F\b",
    re.I,
)
_HD_OPEN_RE = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")


def _strip_data_heredocs(cmd: str) -> str:
    """Remove heredoc bodies that are written to a file rather than executed."""
    out, pos = [], 0
    for m in _HD_OPEN_RE.finditer(cmd):
        if m.start() < pos:
            continue
        line_start = cmd.rfind("\n", 0, m.start()) + 1
        line = cmd[line_start:m.start()]
        tag = m.group(2)
        end = re.search(r"^%s\s*$" % re.escape(tag), cmd[m.end():], re.M)
        body_end = m.end() + (end.end() if end else len(cmd) - m.end())
        if _SINK_RE.search(line):
            out.append(cmd[pos:m.end()])
            pos = body_end
    out.append(cmd[pos:])
    return "".join(out)


def _executable_text(cmd: str) -> str:
    """The part of a command that will actually run. Rules match THIS."""
    if not cmd:
        return ""
    t = _strip_data_heredocs(cmd)
    t = _MSG_RE.sub(" ", t)
    return t


def _git_path_tokens(cmd: str) -> list[str]:
    body = _HEREDOC_RE.sub(" ", cmd)
    body = _MSG_RE.sub(" ", body)
    body = _HD_TAG_RE.sub(" ", body)
    out = []
    for tok in re.split(r"[\s\"']+", body):
        t = tok.strip()
        if not t or t.startswith("-"):
            continue
        if _PATHY_RE.search(t):
            out.append(t)
    return out
FORCE_PUSH_RE = re.compile(
    r"git\s+push\b[^\n]*((--force-with-lease|--force\b)|(?<![-\w])-f(?![-\w]))",
    re.I,
)
NO_VERIFY_RE = re.compile(
    r"git\s+(commit|push|merge)\b[^\n]*--no-verify\b"
    r"|git\s+commit\b[^\n]*\s-n(?![a-zA-Z])",
    re.I,
)
SECRET_NAME_RE = re.compile(
    r"(?:^|[\\/])(local\.json)$"
    r"|(?:^|[\\/])[^\\/]*\.pem$"
    r"|(?:^|[\\/])[^\\/]*\.key$"
    r"|(?:^|[\\/])[^\\/]*\.p12$"
    r"|(?:^|[\\/])[^\\/]*\.pfx$"
    r"|(?:^|[\\/])(?!.*tokeniz)[^\\/]*token[^\\/]*$",
    re.I,
)
GIT_WRITE_RE = re.compile(r"\bgit\s+(add|commit|rm|update-index)\b", re.I)


def _strip_bom(raw: str) -> str:
    if raw and raw[0] == "\ufeff":
        return raw[1:]
    if raw.startswith("\xef\xbb\xbf"):
        return raw[3:]
    return raw


def _secret_basename_ok_to_block(path: str) -> bool:
    if not path:
        return False
    p = path.strip().strip("\"'").replace("\\", "/")
    base = os.path.basename(p)
    if not base:
        return False
    low = base.lower()
    if low in (".env.example", ".env.template", ".env.sample"):
        return False
    if "tokeniz" in low:
        return False
    return bool(SECRET_NAME_RE.search(base) or SECRET_NAME_RE.search(p))


def classify_command(cmd: str, cwd: str = "") -> tuple[str | None, str]:
    if not cmd:
        return None, ""
    cmd = _executable_text(cmd)
    if not cmd.strip():
        return None, ""
    if ROTATE_RE.search(cmd):
        return "never-rotate", REASON["never-rotate"]
    if PUBLIC_RE.search(cmd):
        return "repo-public", REASON["repo-public"]
    if FORCE_PUSH_RE.search(cmd):
        return "force-push", REASON["force-push"]
    if NO_VERIFY_RE.search(cmd):
        return "no-verify", REASON["no-verify"]
    if GIT_WRITE_RE.search(cmd):
        for tok in _git_path_tokens(cmd):
            if _secret_basename_ok_to_block(tok) and not _in_private_vault(tok, cwd):
                return "secret-file", REASON["secret-file"]
    return None, ""


def classify_path(path: str, cwd: str = "") -> tuple[str | None, str]:
    if not path:
        return None, ""
    low = path.replace("\\", "/").lower()
    if "credential_rotation_manifest" in low or "rotate-credential" in low:
        return "never-rotate", REASON["never-rotate"]
    if _secret_basename_ok_to_block(path) and not _in_private_vault(path, cwd):
        return "secret-file", REASON["secret-file"]
    return None, ""


def _payload_command_and_path(data: dict) -> tuple[str, str]:
    if not isinstance(data, dict):
        return "", ""
    cmd = data.get("command") or ""
    path = data.get("file_path") or data.get("path") or ""
    ti = data.get("tool_input") or data.get("toolInput") or {}
    if isinstance(ti, dict):
        cmd = cmd or ti.get("command") or ti.get("cmd") or ""
        path = path or ti.get("file_path") or ti.get("filePath") or ti.get(
            "path"
        ) or ti.get("notebook_path") or ""
        edits = ti.get("edits")
        if not path and isinstance(edits, list) and edits:
            e0 = edits[0]
            if isinstance(e0, dict):
                path = e0.get("file_path") or e0.get("path") or path
    return str(cmd), str(path)


def decide(data: dict) -> tuple[str | None, str]:
    cmd, path = _payload_command_and_path(data)
    cwd = str(data.get("cwd") or data.get("workingDirectory") or "")
    code, reason = classify_command(cmd, cwd)
    if code:
        return code, reason
    return classify_path(path, cwd)


def _emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, separators=(",", ":")))
    sys.stdout.flush()


def _log(runtime: str, code: str | None, data: dict) -> None:
    try:
        log_dir = os.path.join(os.path.expanduser("~"), ".agents", "logs")
        os.makedirs(log_dir, exist_ok=True)
        cmd, path = _payload_command_and_path(data)
        excerpt = (cmd or path)[:300]
        line = json.dumps(
            {
                "hook": "estate-deny-guard",
                "runtime": runtime,
                "verdict": code or "allow",
                "excerpt": excerpt,
            },
            separators=(",", ":"),
        )
        with open(
            os.path.join(log_dir, "estate-deny-guard.jsonl"),
            "a",
            encoding="utf-8",
            newline="\n",
        ) as f:
            f.write(line + "\n")
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    runtime = "claude"
    args = argv if argv is not None else sys.argv[1:]
    if "--runtime" in args:
        i = args.index("--runtime")
        if i + 1 < len(args):
            runtime = args[i + 1].strip().lower()
    raw = sys.stdin.read() if not sys.stdin.isatty() else "{}"
    raw = _strip_bom(raw or "{}").strip() or "{}"
    try:
        data = json.loads(raw)
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    code, reason = decide(data)
    try:
        if runtime == "cursor":
            if code:
                _emit(
                    {
                        "permission": "deny",
                        "agent_message": reason,
                        "user_message": reason,
                    }
                )
            else:
                _emit({"permission": "allow"})
        elif runtime == "grok":
            if code:
                _emit({"decision": "deny", "reason": reason})
        else:
            if code:
                _emit(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "deny",
                            "permissionDecisionReason": reason,
                        }
                    }
                )
    finally:
        _log(runtime, code, data)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        if "--runtime" in sys.argv and "cursor" in sys.argv:
            try:
                sys.stdout.write('{"permission":"allow"}')
                sys.stdout.flush()
            except Exception:
                pass
        sys.exit(0)
