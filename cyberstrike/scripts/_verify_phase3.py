#!/usr/bin/env python3
"""Phase-3 post-switch verification: T-1 (static proxy), T-2, T-13, drift gates.
Full T-1 (fresh-session prompt dump) + step-5 manifest smoke are DEFERRED to the owner
TUI-restart event (TUI not running at lane time). Emits verdict JSON to stdout."""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/.config/cyberstrike")
HOME = Path(r"C:/Users/Prekzursil/AGENTS.md")
LIVE = [REPO / "AGENTS.md", REPO / "CONTEXT.md"]
v = {"verdicts": [], "raw": {}}


def verdict(name, ok, detail):
    v["verdicts"].append({"id": name, "ok": bool(ok), "detail": detail})


def read(p):
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


live_text = [read(p) for p in LIVE]
payload = "\n".join(live_text)
home_text = read(HOME)

# --- T-1 static proxy ---
cfg = json.loads((REPO / "cyberstrike.json").read_text(encoding="utf-8"))
instr = cfg.get("instructions", [])
verdict("T1-static.instructions-count==1", instr == ["{file:~/.config/cyberstrike/CONTEXT.md}"], f"instructions={instr}")
verdict("T1-static.no-double-load(config.md not loaded)", "{file:~/.config/cyberstrike/config.md}" not in instr, f"instr_len={len(instr)}")
verdict("T1-static.single-AGENTS-copy", (REPO / "AGENTS.md").exists() and not (REPO / "AGENTS.new.md").exists(), "AGENTS.md present, AGENTS.new.md removed")
bak_cfg = read(REPO / "backups/phase3_20260920-1542/cyberstrike.json")
verdict("T1-static.control-pre-switch-had-4-entries", bak_cfg.count("{file:") == 4, f"pre-switch file-refs={bak_cfg.count('{file:')} (both-states control present)")
v["raw"]["t1_full_session_dump"] = "DEFERRED-to-TUI-restart (owner event; TUI PID 19684 not running)"

# --- T-2 budget + stale payload ---
b = sum(p.stat().st_size for p in LIVE)
verdict("T2.budget<=7500", b <= 7500, f"AGENTS.md+CONTEXT.md = {b} B")
for marker in ["ses_f9c9ab90", "FINAL-REPORT_2026-09-03", "Daybreak Red"]:
    n = payload.count(marker)
    verdict(f"T2.stale[{marker}]==0", n == 0, f"hits={n}")

# --- T-13 redundancy regression (raw + scoped, both reported) ---
nr_hyph = payload.count("NEVER-ROTATE")
nr_semantic = payload.lower().count("never rotate") + nr_hyph
verdict("T13.NEVER-ROTATE-canonical==1", nr_semantic == 1, f"hyphenated_token={nr_hyph}, 'never rotate'+hyph={nr_semantic} (A1 floor row is the single statement; new contract spells it 'NEVER rotate/modify/revoke')")
surf_payload = payload.count("MQTT matrix"); surf_home = home_text.count("MQTT matrix")
verdict("T13.research-surface-list-not-duplicated-in-payload", surf_payload == 0 and surf_home == 1, f"payload hits={surf_payload}, HOME hits={surf_home} (enumeration elevated to HOME exactly once)")
o925_raw = payload.count("925"); o925_enum = payload.count("CreateUserApiKey") + payload.count("enterprises/AuthKit"); o925_home = home_text.count("org 925") + home_text.count("925")
verdict("T13.org925-enumeration-moved-to-HOME", o925_enum == 0, f"payload enum-signature hits={o925_enum}; raw '925' in payload={o925_raw} (1 = the S1 POINTER mention, by design in the pointer section); HOME mentions={o925_home}")

# --- drift gates ---
r1 = subprocess.run([sys.executable, str(REPO / "scripts/gen_context.py"), "--check"], capture_output=True, text=True, cwd=str(REPO))
verdict("drift.gen_context--check", r1.returncode == 0, (r1.stdout + r1.stderr).strip())
same = (REPO / "CONTEXT.md").read_bytes() == (REPO / "CONTEXT.new.md").read_bytes()
verdict("drift.CONTEXT.md==CONTEXT.new.md", same, f"bytes-identical={same}")
r2 = subprocess.run([sys.executable, str(REPO / "scripts/gen_migration.py")], capture_output=True, text=True, cwd=str(REPO))
verdict("drift.gen_migration-post-switch-EXPECTED-nonzero", r2.returncode != 0, f"exit={r2.returncode} EXPECTED per plan step-4 note (live files replaced; frozen map archived at backups/phase3_20260920-1542/migration_map.phase2-3-record.json); tail={(r2.stdout + r2.stderr).strip()[-200:]}")

ok_all = all(x["ok"] for x in v["verdicts"])
print(json.dumps(v, indent=1))
print(("SUCCESS:phase3-verify " if ok_all else "FAILED:phase3-verify ") + f"{sum(x['ok'] for x in v['verdicts'])}/{len(v['verdicts'])} verdicts ok")
sys.exit(0 if ok_all else 1)
