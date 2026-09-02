"""A6 vendor-output sanitizer / quarantine (ARC-0041).

Trust boundary: a second vendor's last-message is untrusted DATA and a
prompt-injection carrier, never instructions. Apply this on the RETURN
path after parse and before any Claude-side agent reads ``parsed``.

Fail-closed: an exception quarantines an empty payload; it never returns
the raw vendor object. Fail-open is a probe-only mutant.
"""
from __future__ import annotations

import base64
import html
import json
import os
import re
from typing import Any, Mapping

KIND = "untrusted-vendor-data"
REDACTED = "[REDACTED-NEVER-FORWARD]"
CANARY_ENV = "ARC0041_CANARY_SECRET"
CANARY_VALUE = "canary-arc0041-7e1d9c4b-NOT-A-KEY"

OUTBOUND_ALLOW = frozenset(
    {
        "unit_id",
        "vendor",
        "adapter",
        "state",
        "classification",
        "sentinel",
        "error",
        "invocation",
        "parsed",
        "quarantine",
        "leaks",
    }
)
NEVER_FORWARD_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "api-key",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "secret",
        "password",
        "credentials",
        "credential",
        "tool_permissions",
        "tool_permission_grants",
        "permission_grants",
        "hooks",
        "hook_configuration",
        "hook_config",
        "hooks_json",
        "credential_store_path",
        "absolute_credential_path",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "CODEX_API_KEY",
        CANARY_ENV,
    }
)
CRED_PATH_RE = re.compile(
    r"(?i)(?:^|[\"'\s])(?:/root|/home/[^/\s]+|/Users/[^/\s]+|"
    r"[A-Za-z]:\\Users\\[^\\]+)"
    r"(?:/\.claude|/\.codex|/\.config/anthropic|/\.config/openai|"
    r"\\\.claude|\\\.codex)"
    r"[^\s\"']*"
)
MENTION_RES = (
    re.compile(r"MENTION-BEGIN.*?MENTION-END", re.S),
    re.compile(r"```injection-example.*?```", re.S),
)
ROLE_SPOOF_RES = tuple(
    re.compile(p)
    for p in (
        r"(?im)^(?:system|developer|assistant|root)\s*:",
        r"(?i)you are now (?:the )?(?:system|root|unrestricted|privileged)",
        r"(?i)<\|im_start\|>\s*system",
        r"(?i)<<SYS>>",
        r"(?i)forget you are an assistant",
        r"(?i)role\s*:\s*system\b",
        r"(?i)\[INST\].{0,80}system",
    )
)
OVERRIDE_RES = tuple(
    re.compile(p)
    for p in (
        r"(?i)ignore (?:all )?(?:previous|prior|your) instructions",
        r"(?i)disregard all (?:prior|previous|earlier) (?:rules|instructions)",
        r"(?i)override:?\s*do not follow",
        r"(?i)new instructions follow",
        r"(?i)stop following (?:the )?(?:developer|system|original) "
        r"(?:message|prompt|instructions)",
        r"(?i)new policy supersedes",
        r"(?i)do not follow your original",
        r"(?i)ignore your instructions",
    )
)
B64_RE = re.compile(r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{16,}={0,2}(?![A-Za-z0-9+/])")
HEX_RE = re.compile(r"(?<![0-9a-fA-F])(?:[0-9a-fA-F]{2}){12,}(?![0-9a-fA-F])")
UNI_RE = re.compile(r"(?:\\u[0-9a-fA-F]{4}){8,}")
HTML_RE = re.compile(r"(?:&#\d{2,3};){8,}")


def mention_mask(text: str) -> str:
    out = text
    for cre in MENTION_RES:
        out = cre.sub(" ", out)
    return out


def _role_hits(text: str) -> list[dict[str, str]]:
    hits = []
    for cre in ROLE_SPOOF_RES:
        m = cre.search(text)
        if m:
            hits.append({"class": "role-spoof", "span": m.group(0)[:80]})
    return hits


def _override_hits(text: str) -> list[dict[str, str]]:
    hits = []
    for cre in OVERRIDE_RES:
        m = cre.search(text)
        if m:
            hits.append({"class": "instruction-override", "span": m.group(0)[:80]})
    return hits


def _try_b64(blob: str) -> str | None:
    pad = (-len(blob)) % 4
    try:
        raw = base64.b64decode(blob + ("=" * pad), validate=False)
    except Exception:
        return None
    if not raw:
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if not any(ch.isprintable() or ch in "\n\r\t" for ch in text):
        return None
    if sum(ch.isprintable() or ch in "\n\r\t" for ch in text) < 0.8 * len(text):
        return None
    return text


def _try_hex(blob: str) -> str | None:
    if len(blob) % 2:
        return None
    try:
        raw = bytes.fromhex(blob)
        return raw.decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None


def _decode_layers(text: str, depth: int = 0) -> list[tuple[str, str]]:
    if depth >= 3:
        return []
    found: list[tuple[str, str]] = []
    for m in B64_RE.finditer(text):
        decoded = _try_b64(m.group(0))
        if decoded and decoded != m.group(0):
            found.append(("b64", decoded))
            found.extend(_decode_layers(decoded, depth + 1))
    for m in HEX_RE.finditer(text):
        decoded = _try_hex(m.group(0))
        if decoded:
            found.append(("hex", decoded))
            found.extend(_decode_layers(decoded, depth + 1))
    for m in UNI_RE.finditer(text):
        try:
            decoded = bytes(m.group(0), "utf-8").decode("unicode_escape")
        except Exception:
            decoded = None
        if decoded and decoded != m.group(0):
            found.append(("unicode-escape", decoded))
            found.extend(_decode_layers(decoded, depth + 1))
    for m in HTML_RE.finditer(text):
        decoded = html.unescape(m.group(0))
        if decoded and decoded != m.group(0):
            found.append(("html-entities", decoded))
            found.extend(_decode_layers(decoded, depth + 1))
    return found


def scan_instruction_hits(text: str) -> list[dict[str, str]]:
    surface = mention_mask(text)
    hits = _role_hits(surface) + _override_hits(surface)
    for encoding, decoded in _decode_layers(surface):
        inner = _role_hits(decoded) + _override_hits(decoded)
        for hit in inner:
            hits.append(
                {
                    "class": "encoded",
                    "encoding": encoding,
                    "inner_class": hit["class"],
                    "span": hit["span"],
                }
            )
    # de-dupe by (class, span, inner_class)
    seen: set[tuple[str, str, str]] = set()
    uniq: list[dict[str, str]] = []
    for hit in hits:
        key = (hit["class"], hit.get("span", ""), hit.get("inner_class", ""))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(hit)
    return uniq


def env_secrets(env: Mapping[str, str] | None = None) -> list[str]:
    src = env if env is not None else os.environ
    out: list[str] = []
    for key, val in src.items():
        if not val or not isinstance(val, str):
            continue
        ku = key.upper()
        if key == CANARY_ENV or any(tok in ku for tok in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            if len(val) >= 8:
                out.append(val)
    return out


def redact_text(text: str, secrets: list[str]) -> tuple[str, list[str]]:
    stripped: list[str] = []
    out = text
    for secret in secrets:
        if secret and secret in out:
            out = out.replace(secret, REDACTED)
            stripped.append("credential-canary")
    def _path_sub(m: re.Match[str]) -> str:
        stripped.append("credential-store-path")
        return REDACTED

    out2 = CRED_PATH_RE.sub(_path_sub, out)
    return out2, stripped


def strip_never_forward(obj: Any, secrets: list[str]) -> tuple[Any, list[str]]:
    stripped: list[str] = []
    if isinstance(obj, dict):
        kept: dict[str, Any] = {}
        for key, val in obj.items():
            if str(key) in NEVER_FORWARD_KEYS:
                if str(key) in {
                    "tool_permissions",
                    "tool_permission_grants",
                    "permission_grants",
                }:
                    stripped.append("tool-permission-grant")
                elif str(key) in {
                    "hooks",
                    "hook_configuration",
                    "hook_config",
                    "hooks_json",
                }:
                    stripped.append("hook-configuration")
                elif str(key) in {"credential_store_path", "absolute_credential_path"}:
                    stripped.append("credential-store-path")
                else:
                    stripped.append("credential-field")
                continue
            child, child_stripped = strip_never_forward(val, secrets)
            kept[key] = child
            stripped.extend(child_stripped)
        return kept, stripped
    if isinstance(obj, list):
        items = []
        for val in obj:
            child, child_stripped = strip_never_forward(val, secrets)
            items.append(child)
            stripped.extend(child_stripped)
        return items, stripped
    if isinstance(obj, str):
        red, marks = redact_text(obj, secrets)
        return red, marks
    return obj, stripped


def as_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, sort_keys=True, default=str)


def quarantine_vendor_output(
    payload: Any,
    *,
    env: Mapping[str, str] | None = None,
    source_vendor: str = "openai",
    fail_open: bool = False,
) -> dict[str, Any]:
    if fail_open:
        # Probe-only mutant: treat vendor output as instructions and copy
        # the env canary. Production must never take this branch.
        src = env if env is not None else os.environ
        return {
            "kind": "fail-open-passthrough",
            "instructions_forbidden": False,
            "payload": payload,
            "env_canary": src.get(CANARY_ENV, ""),
            "fail_closed": False,
        }
    try:
        secrets = env_secrets(env)
        text = as_text(payload)
        hits = scan_instruction_hits(text)
        cleaned, nf = strip_never_forward(payload, secrets)
        if isinstance(cleaned, str):
            cleaned, extra = redact_text(cleaned, secrets)
            nf.extend(extra)
        envelope = {
            "kind": KIND,
            "instructions_forbidden": True,
            "source_vendor": source_vendor,
            "hits": hits,
            "never_forward_stripped": sorted(set(nf)),
            "payload": cleaned,
            "quarantined": True,
            "fail_closed": True,
        }
        return envelope
    except Exception as exc:
        return {
            "kind": KIND,
            "instructions_forbidden": True,
            "source_vendor": source_vendor,
            "hits": [{"class": "fail-closed", "span": type(exc).__name__}],
            "never_forward_stripped": ["sanitizer-exception"],
            "payload": "",
            "quarantined": True,
            "fail_closed": True,
            "error": "sanitizer-exception",
        }


def _scrub_invocation(inv: Any, secrets: list[str]) -> dict[str, Any]:
    if not isinstance(inv, dict):
        return {}
    keep = {
        "prompt_file",
        "prompt_file_on_argv",
        "prompt_body_on_argv",
        "output_last_message_file",
        "ignore_user_config",
        "exit_code",
        "retry_count",
        "timed_out",
        "stdout_bytes",
        "stderr_bytes",
        "output_bytes",
        "stdout_not_used_as_result",
    }
    out: dict[str, Any] = {}
    for key in keep:
        if key not in inv:
            continue
        val, _ = strip_never_forward(inv[key], secrets)
        out[key] = val
    return out


def seal_adapter_result(
    result: Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    fail_open: bool = False,
) -> dict[str, Any]:
    """Copy only allowlisted outbound fields; replace parsed with quarantine."""
    secrets = env_secrets(env)
    vendor = str(result.get("vendor") or "openai")
    sealed: dict[str, Any] = {}
    for key in OUTBOUND_ALLOW:
        if key not in result:
            continue
        if key == "parsed":
            continue
        if key == "invocation":
            sealed[key] = _scrub_invocation(result.get(key), secrets)
            continue
        val, _ = strip_never_forward(result[key], secrets)
        sealed[key] = val
    envelope = quarantine_vendor_output(
        result.get("parsed"),
        env=env,
        source_vendor=vendor,
        fail_open=fail_open,
    )
    sealed["parsed"] = envelope
    sealed["quarantine"] = {
        "applied": not fail_open,
        "kind": envelope.get("kind"),
        "fail_closed": envelope.get("fail_closed"),
        "locus": "vendor-return-path-before-claude-side-read",
    }
    return sealed


def walk_strings(obj: Any) -> list[str]:
    found: list[str] = []
    if isinstance(obj, str):
        found.append(obj)
    elif isinstance(obj, dict):
        for key, val in obj.items():
            found.append(str(key))
            found.extend(walk_strings(val))
    elif isinstance(obj, list):
        for val in obj:
            found.extend(walk_strings(val))
    elif obj is not None and not isinstance(obj, (int, float, bool)):
        found.append(str(obj))
    return found


def canary_present_walk(obj: Any, canary: str) -> bool:
    return any(canary in item for item in walk_strings(obj))


def canary_present_dump(obj: Any, canary: str) -> bool:
    blob = json.dumps(obj, sort_keys=True, default=str)
    return canary in blob
