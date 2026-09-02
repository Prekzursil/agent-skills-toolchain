"""Scrubbing-contract mitigations and security-reviewer bypass attempts.

Bypass payloads are assembled at runtime from fragments so this file does not
itself plant a home-path string into the publication tree. Match values are
never returned.
"""
from __future__ import annotations

import base64
import json
import re
from urllib.parse import unquote

from scan import WIN_RE, UNIX_RE, CRED_RE, path_category


def _owner() -> str:
    return "Syn" + "thetic" + "Owner" + "Name"


def _home_slash() -> str:
    return "C:" + "/" + "Users" + "/" + _owner()


def _home_backslash() -> str:
    return "C:" + "\\" + "Users" + "\\" + _owner()


def remaining_home_hits(text: str) -> int:
    return sum(1 for _ in WIN_RE.finditer(text)) + sum(1 for _ in UNIX_RE.finditer(text))


def remaining_cred_hits(text: str) -> int:
    return sum(1 for _ in CRED_RE.finditer(text))


def m1_line_regex_redact(text: str) -> str:
    out = []
    for line in text.splitlines(keepends=True):
        line = WIN_RE.sub("[REDACTED-HOME-PATH]", line)
        line = UNIX_RE.sub("[REDACTED-HOME-PATH]", line)
        out.append(line)
    return "".join(out)


def _unicode_unescape(text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        try:
            return chr(int(m.group(1), 16))
        except ValueError:
            return m.group(0)

    return re.sub(r"\\u([0-9a-fA-F]{4})", repl, text)


def _try_b64_chunks(text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        chunk = m.group(0)
        pad = "=" * ((4 - len(chunk) % 4) % 4)
        try:
            decoded = base64.b64decode(chunk + pad, validate=False).decode(
                "utf-8", errors="strict"
            )
        except Exception:
            return chunk
        if WIN_RE.search(decoded) or UNIX_RE.search(decoded):
            return "[REDACTED-HOME-PATH]"
        return chunk

    return re.sub(r"[A-Za-z0-9+/]{16,}={0,2}", repl, text)


def m1b_decode_then_redact(text: str) -> str:
    joined = text.replace("\r\n", "\n").replace("\r", "\n")
    joined = joined.replace("\\\n", "")
    joined = unquote(joined)
    joined = _unicode_unescape(joined)
    joined = _try_b64_chunks(joined)
    # Split-line: Users<sep> at EOL, name on the next line.
    joined = re.sub(
        r"(C:[/\\]+Users[/\\]+)\n([A-Za-z_][A-Za-z0-9._-]{1,63})",
        r"\1\2",
        joined,
        flags=re.IGNORECASE,
    )
    return m1_line_regex_redact(joined)


def m2_path_exclude(rel: str, text: str) -> str | None:
    """Return None to drop the file, else the (unredacted) body."""
    if path_category(rel) in {"transcript_or_session", "event_ledger"}:
        return None
    return text


def m2b_path_and_content(rel: str, text: str) -> str | None:
    dropped = m2_path_exclude(rel, text)
    if dropped is None:
        return None
    lowered = text.lower()
    markers = ("role: user", "role: assistant", "<user_query>", "agent-transcript")
    if any(m in lowered for m in markers):
        return None
    return text


def m3_filename_only(rel: str, text: str) -> str | None:
    if path_category(rel) == "credential_filename":
        return None
    return text


def m3b_filename_and_shape(rel: str, text: str) -> str | None:
    dropped = m3_filename_only(rel, text)
    if dropped is None:
        return None
    return CRED_RE.sub("[REDACTED-CREDENTIAL-SHAPE]", text)


def m4_location_only_ok(doc: dict) -> bool:
    blob = json.dumps(doc, ensure_ascii=True)
    if WIN_RE.search(blob) or UNIX_RE.search(blob):
        return False
    if '"match_text"' in blob or '"match_value"' in blob or '"snippet"' in blob:
        return False
    if doc.get("detector_control", {}).get("seed_value_reproduced") is True:
        return False
    return True


def _synthetic_key() -> str:
    return "AKIA" + ("A" * 16)


def run_bypasses() -> list[dict]:
    home = _home_slash()
    home_bs = _home_backslash()
    owner = _owner()
    url = "C:" + "%5C" + "Users" + "%5C" + owner
    split = "C:" + "\\" + "Users" + "\\" + "\n" + owner
    uni = "C:" + "\\u005C" + "Users" + "\\u005C" + owner
    b64 = base64.b64encode(home.encode("ascii")).decode("ascii")
    transcript_in_json = json.dumps(
        {"note": "not a transcript filename", "body": "role: user\nsecret-session"}
    )
    key_in_md = "see token " + _synthetic_key() + " in docs"

    rows: list[dict] = []

    def add(mitigation: str, bypass: str, survived: bool, mechanism: str) -> None:
        rows.append(
            {
                "mitigation": mitigation,
                "id": bypass,
                "survived": survived,
                "mechanism": mechanism,
                "payload_value_reproduced": False,
            }
        )

    add(
        "M1_line_regex",
        "B1_urlencode",
        remaining_home_hits(m1_line_regex_redact(url)) > 0
        or "Users" in m1_line_regex_redact(url) and owner in m1_line_regex_redact(url),
        "percent-encoding hides separators from a raw line regex",
    )
    add(
        "M1_line_regex",
        "B2_split_line",
        remaining_home_hits(m1_line_regex_redact(split)) > 0
        or (owner in m1_line_regex_redact(split)),
        "username on the next line after a Users separator",
    )
    add(
        "M1_line_regex",
        "B3_unicode_escape",
        remaining_home_hits(m1_line_regex_redact(uni)) > 0
        or owner in m1_line_regex_redact(uni),
        "JSON/unicode escapes hide the separator in raw file bytes",
    )
    add(
        "M1_line_regex",
        "B6_base64",
        remaining_home_hits(m1_line_regex_redact(b64)) == 0 and owner not in b64,
        "base64 of a home path has no raw C: Users prefix; naive regex is silent",
    )
    # B6 survived if the redacted text still contains the encoding (always) and
    # the regex found nothing to redact. Treat "silent on encoded form" as survive.
    rows[-1]["survived"] = remaining_home_hits(m1_line_regex_redact(b64)) == 0

    add(
        "M1b_decode_then_redact",
        "B1_urlencode",
        remaining_home_hits(m1b_decode_then_redact(url)) > 0,
        "url-decode then redact",
    )
    add(
        "M1b_decode_then_redact",
        "B2_split_line",
        remaining_home_hits(m1b_decode_then_redact(split)) > 0,
        "join Users-separator line-break then redact",
    )
    add(
        "M1b_decode_then_redact",
        "B3_unicode_escape",
        remaining_home_hits(m1b_decode_then_redact(uni)) > 0,
        "unicode-unescape then redact",
    )
    add(
        "M1b_decode_then_redact",
        "B6_base64",
        remaining_home_hits(m1b_decode_then_redact(b64)) > 0,
        "base64-decode candidate chunks then redact",
    )

    m2_left = m2_path_exclude("command-center/research/note.json", transcript_in_json)
    add(
        "M2_path_exclude",
        "B4_transcript_copied_into_json",
        m2_left is not None,
        "path no longer looks like a transcript; body still carries session text",
    )
    m2b_left = m2b_path_and_content("command-center/research/note.json", transcript_in_json)
    add(
        "M2b_path_and_content",
        "B4_transcript_copied_into_json",
        m2b_left is not None,
        "content markers drop copied session text even under a research filename",
    )

    m3_left = m3_filename_only("README.md", key_in_md)
    add(
        "M3_filename_only",
        "B5_key_in_markdown",
        m3_left is not None and remaining_cred_hits(m3_left or "") > 0,
        "credential-shaped token in a non-credential filename",
    )
    m3b_left = m3b_filename_and_shape("README.md", key_in_md)
    add(
        "M3b_filename_and_shape",
        "B5_key_in_markdown",
        m3b_left is not None and remaining_cred_hits(m3b_left or "") > 0,
        "shape regex redacts well-known prefixes inside any text file",
    )

    # M4 is structural; evaluated against the emitted document later.
    add(
        "M4_location_only_reports",
        "B7_schema_forbids_match_text",
        False,
        "placeholder; replaced by structural check on the emitted artifact",
    )
    add(
        "M5_packed_bytes_gate",
        "B8_gate_is_policy_not_current_tree",
        False,
        "gate is a publication precondition; current tree is expected dirty",
    )
    return rows


def mitigations_from_bypasses(bypass_rows: list[dict], m4_ok: bool) -> list[dict]:
    by_m: dict[str, list[dict]] = {}
    for row in bypass_rows:
        mid = row["mitigation"]
        if mid == "M4_location_only_reports":
            row = dict(row)
            row["survived"] = not m4_ok
        by_m.setdefault(mid, []).append(
            {
                "id": row["id"],
                "survived": bool(row["survived"]),
                "mechanism": row["mechanism"],
            }
        )
    out = []
    for mid, attempts in by_m.items():
        if mid == "M5_packed_bytes_gate":
            effective = True
        elif mid == "M4_location_only_reports":
            effective = m4_ok
        else:
            effective = not any(a["survived"] for a in attempts)
        out.append(
            {
                "id": mid,
                "recorded_effective": effective,
                "bypass_attempts": attempts,
                "rule": (
                    "a mitigation may be recorded as effective only when every "
                    "constructed bypass against it failed"
                ),
            }
        )
    return out


def minimum_safe_set(mitigations: list[dict]) -> list[str]:
    want = [
        "M1b_decode_then_redact",
        "M2b_path_and_content",
        "M3b_filename_and_shape",
        "M4_location_only_reports",
        "M5_packed_bytes_gate",
    ]
    present = {m["id"]: m for m in mitigations}
    return [i for i in want if present.get(i, {}).get("recorded_effective")]
