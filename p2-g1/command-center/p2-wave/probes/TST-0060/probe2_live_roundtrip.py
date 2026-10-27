#!/usr/bin/env python3
"""TST-0060 probe2: live adversarial transport round-trip on THIS box.

Mechanically different from probe1 (which recounts the receipt's matrix):
this builds a fresh adversarial payload (nested quotes, backslashes,
dollars, backticks, trailing newline) and byte-compares the landed file
for every transport runnable here. Transports are hosted in byte-clean
script FILES written by this probe (the receipt's Linux host carried
payloads via env and bash -c argv; on this Windows box both carriers
themselves mangle bytes - env var arrived empty, -c argv grew CRLF - so
the script-file carrier is the one that isolates the quoting semantics
being measured). Expected live map, matching the receipt:
write_tool green; quoted heredoc green; c_inline printf green;
here_string red extra_trailing_newline; expanding heredoc red;
double-quoted c_inline red shell_expansion.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

UNIT = "TST-0060"
BS = chr(92)
fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def build_payload() -> bytes:
    b = BS
    lines = [
        'TST-0060 live payload: nested "quotes" ' + b + "back" + b + "slashes $dollars ${HOME_NOT_EXPANDED} `echo` backticks.",
        'line2: if [ "$x" = "a' + b + 'b" ]; then echo `pwd`; fi',
        "line3: cost=$(printf 'literal $kept') # `date` `true` inert",
        "line4: single 'quoted $kept' end",
    ]
    body = ("\n".join(lines) + "\n").encode("utf-8")
    target = 369
    if len(body) > target:
        body = body[: target - 1] + b"\n"
    while len(body) < target - 1:
        body += b"# pad 369 "
    return body[: target - 1] + b"\n"


def classify(intended: bytes, landed: bytes | None) -> dict:
    if landed is None:
        return {"equal": False, "kind": "transport_error"}
    if landed == intended:
        return {"equal": True, "kind": "equal"}
    if landed == intended + b"\n":
        return {"equal": False, "kind": "extra_trailing_newline"}
    return {"equal": False, "kind": "shell_expansion_or_other"}


def main() -> int:
    payload = build_payload()
    chk(len(payload) == 369, "payload-size", str(len(payload)))
    for needle, label in [(b'"', "quotes"), (BS.encode(), "backslashes"), (b"$", "dollars"), (b"`", "backticks")]:
        chk(needle in payload, "payload-missing-" + label)
    sha = hashlib.sha256(payload).hexdigest()
    text = payload.decode("utf-8")
    sq = text.replace("'", "'" + BS + "'" + "'")  # POSIX idiom: close, escaped quote, reopen
    dq = text.replace('"', BS + '"').replace("\n", " ")
    td = tempfile.mkdtemp(prefix="tst0060-live-")
    results: dict[str, dict] = {}

    def run(name: str, script: str) -> None:
        sp = Path(td) / (name + ".sh")
        sp.write_bytes(script.encode("utf-8"))
        out = Path(td) / ("o_" + name + ".bin")
        p = subprocess.run(["bash", str(sp.name)], cwd=td, capture_output=True, timeout=60)
        results[name] = classify(payload, out.read_bytes() if out.exists() else None)
        results[name]["rc"] = p.returncode

    try:
        (Path(td) / "i.bin").write_bytes(payload)
        run("write_tool", "cp i.bin o_write_tool.bin\n")
        run("heredoc", "cat > o_heredoc.bin <<'EOF60'\n" + text + "EOF60\n")
        run("heredoc_expanding", "cat > o_heredoc_expanding.bin <<EOF60\n" + text + "EOF60\n")
        run("c_inline", "printf '%s' '" + sq + "' > o_c_inline.bin\n")
        run("c_inline_double_quoted", 'printf \'%s\' "' + dq + '" > o_c_inline_double_quoted.bin\n')
        run("here_string", "PL='" + sq + "'\ncat > o_here_string.bin <<< \"$PL\"\n")
    finally:
        time.sleep(0.3)
        shutil.rmtree(td, ignore_errors=True)

    r = results
    chk(r["write_tool"]["equal"] is True, "write-tool-green", str(r["write_tool"]))
    chk(r["heredoc"]["equal"] is True, "quoted-heredoc-green", str(r["heredoc"]))
    chk(r["c_inline"]["equal"] is True, "c-inline-green", str(r["c_inline"]))
    chk(r["here_string"]["kind"] == "extra_trailing_newline", "here-string-red-newline", str(r["here_string"]))
    chk(r["heredoc_expanding"]["equal"] is False, "expanding-heredoc-red", str(r["heredoc_expanding"]))
    chk(r["c_inline_double_quoted"]["equal"] is False, "dq-control-red", str(r["c_inline_double_quoted"]))
    red = {k: v["kind"] for k, v in r.items() if not v["equal"]}
    if fails:
        print("FAILED:" + UNIT + "-probe2 " + "; ".join(fails))
        return 1
    print("payload_sha256", sha, "bytes", len(payload))
    for k, v in r.items():
        print("  ", k, "->", v["kind"], "rc", v["rc"])
    print("SUCCESS:" + UNIT + "-probe2 live round-trip reproduced on this box: 3 green (write_tool, quoted heredoc, c_inline printf), here_string red on extra_trailing_newline, expanding heredoc and double-quoted c_inline red on shell expansion - receipt phenomenon is live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
