#!/usr/bin/env python3
"""Generate CONTEXT.new.md (machine facts) from LIVE sources (G-4=C, G-5=B).

Sources of truth:
  - ~/.config/cyberstrike/cyberstrike.json   (canonical config; renamed opencode.json)
  - D:/opt/cyberstrike-mcp/mcp-ssot.json     (fleet supervisor/profiles/catalogs)
  - data dir facts (db, skill roots) under ~/.local/share/cyberstrike

Emits CONTEXT.new.md <= ~1.0 KB (model-facing byte budget: AGENTS.new + CONTEXT.new
<= 7500 B total per G-5). --check regenerates in memory and diffs the on-disk file
(exit 1 on drift). Never hand-edit the output.
"""

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parent.parent
CFG = REPO / "cyberstrike.json"
SSOT = Path(r"D:\opt\cyberstrike-mcp\mcp-ssot.json")
DATA = Path.home() / ".local" / "share" / "cyberstrike"
OUT = REPO / "CONTEXT.new.md"


def ports(urls):
    out = []
    for u in urls:
        p = urlparse(u).port
        if p:
            out.append(p)
    return out


def build() -> str:
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    ssot = json.loads(SSOT.read_text(encoding="utf-8")) if SSOT.exists() else {}
    mcp = cfg.get("mcp", {})
    urls = [v.get("url", "") for v in mcp.values() if isinstance(v, dict)]
    band = [p for p in ports(urls) if 30000 <= p < 40000]
    lo, hi = (min(band), max(band)) if band else (0, 0)
    others = sorted({p for p in ports(urls) if p not in band})
    shims = [
        m
        for m in (cfg.get("provider", {}).get("nvidia", {}).get("models", {})).values()
        if isinstance(m, dict) and str(m.get("id", "")) == "moonshotai/kimi-k3"
    ]
    local = sorted(
        {
            urlparse(v["options"]["baseURL"]).netloc
            for v in cfg.get("provider", {}).values()
            if isinstance(v, dict)
            and v.get("options", {}).get("baseURL", "").startswith("http://127.0.0.1")
        }
    )
    db = DATA / "cyberstrike.db"
    skills_data = (
        len(list((DATA / "skill").iterdir())) if (DATA / "skill").is_dir() else 0
    )
    skills_cfg = (
        len(list((REPO / "skill").iterdir())) if (REPO / "skill").is_dir() else 0
    )
    lines = [
        "# CONTEXT.md — CyberStrike machine facts (GENERATED — do not hand-edit)",
        "",
        f"Regen: `python scripts/gen_context.py` (drift check: `--check`). Truth = live config, not prose.",
        "",
        f"- db (canonical): `{db}` — other cyberstrike.db copies are ghosts",
        f"- skills: {skills_data} data roots + {skills_cfg} repo root (fork lazy-loads both)",
        f"- MCP: {len(mcp)} servers, band {lo}-{hi}, exceptions {others}; `bolt-lab` rides the `bolt:` section (:3001), not `mcp:`",
        f"- supervisor: `{Path(ssot.get('supervisor', '')).name}` profiles {','.join(ssot.get('profiles', {}))} · hexstrike-ai :{ssot.get('hexstrike_internal', {}).get('port', '?')}",
        f"- model: `{cfg.get('model')}` / small `{cfg.get('small_model')}` · disabled: {','.join(cfg.get('disabled_providers', []))} · permission `{cfg.get('permission')}`",
        f"- kimi-shims ({len(shims)}): `gpt-6.0-astra`/`gpt-5.6-daybreak-blue-latest` -> `moonshotai/kimi-k3` — no OpenAI brain in cockpit; real OpenAI cyber path = external (ChatGPT web)",
        f"- local lanes: {', '.join(local)} (dbx needs gateway.py; :18319 rotator, key-state on D:)",
        f"- instructions[]: {len(cfg.get('instructions', []))} entries; AGENTS.md loads natively (Global.Path.config)",
        "",
    ]
    return "\n".join(lines)


def gateway_routes_check() -> int:
    """Drift gate extension (wiring_plan gateway_skeleton_milestone): the generated
    routing table must equal a fresh SSOT regeneration. Fail-OPEN with a warning if
    the SSOT (D: drive) or the generated artifact is absent — gen_context must not
    newly break on a D:-less box; fail-CLOSED on actual drift."""
    import importlib.util

    gr = REPO / "gateway" / "gen_routes.py"
    if not gr.exists() or not Path(r"D:\opt\cyberstrike-mcp\mcp-ssot.json").exists():
        print("NOT-CHECKED:gateway-routes ssot or generator absent (D: unmounted?)")
        return 0
    spec = importlib.util.spec_from_file_location("gen_routes", gr)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        return mod.check(mod.build_routes(mod.load_ssot()))
    except Exception as e:  # corrupt ssot/artifact is drift, not a crash
        print(f"FAILED:gateway-routes-drift check raised {type(e).__name__}: {e}")
        return 1


def main():
    text = build()
    if "--check" in sys.argv:
        rc = 0
        disk = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if disk != text:
            print(
                "FAILED:context-drift CONTEXT.new.md differs from live-config regeneration"
            )
            rc = 1
        else:
            print("SUCCESS:context-check CONTEXT.new.md == live config")
        rc |= gateway_routes_check()
        return rc
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"SUCCESS:gen-context wrote {OUT} ({len(text.encode('utf-8'))} B)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
