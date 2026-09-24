#!/usr/bin/env python3
# build-temp-baseline_2026-09-20.py - phase1 OP2+OP3: temp_baseline builder + verifier
import hashlib, shutil, sys
from pathlib import Path

PH1 = Path(r"D:\bolt\admin-crack-2026-09-19\raw\cs-audit\phase1")
TB = PH1 / "temp_baseline"
BEFORE = PH1 / "cyberstrike.json.before"
LIVE = Path(r"C:\Users\Prekzursil\.config\cyberstrike\config.md")
SCRIPT = Path(
    r"C:\Users\Prekzursil\.config\cyberstrike\scripts\phase1_provider_truth.py"
)
R = [
    (
        "| OpenAI cyber path | No OpenAI brain in the cockpit:",
        "| OpenAI cyber path | Astra, Daybreak Blue/Red, GPT-5.x/6.x all authorized jailbreak/cyber-prompt **targets**. Overlay is not a scope ban. Live workhorse may still be GLM/Kimi when overlay fires. |",
    ),
    (
        "| Preserved model routes | OpenRouter Nex/Nemotron free routes,",
        "| Preserved model routes | OpenRouter Nex/Nemotron free routes, `zai/*`, `zai-model-api/glm-5.3`, GPT-6 Astra (non-cyber), Daybreak Blue/Red, and the Hugging Face abliterated routes remain registered |",
    ),
    (
        'The overlay "This content can\'t be shown / Trusted Access / chatgpt.com/cyber"',
        'The overlay "This content can\'t be shown / Trusted Access / chatgpt.com/cyber" is a product classifier. Op-wrapper cannot clear it. Astra has no Daybreak reduced-refusals. Daybreak Red (`gpt-daybreak-red-latest`) is registered for when provisioned; Codex `models_cache.json` did not list it on 10.09.2026.',
    ),
]
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
TB.mkdir(parents=True, exist_ok=True)
shutil.copyfile(BEFORE, TB / "cyberstrike.json")
shutil.copyfile(LIVE, TB / "config.md")
lines = (TB / "config.md").read_bytes().splitlines(keepends=True)
replaced = []
for needle, new in R:
    hits = [i for i, raw in enumerate(lines) if needle.encode() in raw]
    if len(hits) != 1:
        print("ERROR needle hits=%d: %r" % (len(hits), needle[:50]))
        sys.exit(1)
    i = hits[0]
    eol = (
        b"\r\n"
        if lines[i].endswith(b"\r\n")
        else (b"\n" if lines[i].endswith(b"\n") else b"")
    )
    lines[i] = new.encode() + eol
    replaced.append(i + 1)
(TB / "config.md").write_bytes(b"".join(lines))
live = LIVE.read_bytes()
temp = (TB / "config.md").read_bytes()
L = live.splitlines(keepends=True)
T = temp.splitlines(keepends=True)
diffs = [i + 1 for i in range(min(len(L), len(T))) if L[i] != T[i]]
sj = SCRIPT.read_bytes()
tj = (TB / "cyberstrike.json").read_bytes()
print(
    "script_bytes=%d bom=%s crlf=%d lf=%d"
    % (len(sj), sj[:3] == b"\xef\xbb\xbf", sj.count(b"\r\n"), sj.count(b"\n"))
)
print(
    "temp_json_bytes=%d lines=%d byte_exact=%s"
    % (len(tj), len(tj.splitlines()), sha(BEFORE) == sha(TB / "cyberstrike.json"))
)
print(
    "temp_md_bytes=%d lines=%d live_lines=%d same_count=%s"
    % (len(temp), len(T), len(L), len(T) == len(L))
)
print("md_crlf live=%d temp=%d" % (live.count(b"\r\n"), temp.count(b"\r\n")))
print("diff_lines=%s replaced=%s" % (diffs, replaced))
ok = (
    diffs == replaced
    and len(diffs) == 3
    and len(T) == len(L)
    and sha(BEFORE) == sha(TB / "cyberstrike.json")
)
print("RESULT=" + ("OK" if ok else "FAILED"))
sys.exit(0 if ok else 1)
