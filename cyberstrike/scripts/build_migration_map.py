#!/usr/bin/env python3
"""One-shot authorship build for scripts/migration_map.json.

Pairs the human mapping decisions (DESTS below, in dump order = file,line order)
with the content hashes computed by gen_migration.py from the LIVE files.
The emitted map is content-keyed: any later edit to a live file changes its
hash, gen_migration.py then reports the key as unmapped and exits 1 (T-11).
"""
import json

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MAP_PATH = REPO / "scripts" / "migration_map.json"

# dest shorthand
A0, A1, A2, A3, A5, A7 = ("AGENTS.new §0 (precedence/truth model)",
                          "AGENTS.new §1 (authorization pointer)",
                          "AGENTS.new §2 (deterministic boundary)",
                          "AGENTS.new §3 (session manifest)",
                          "AGENTS.new §5 (artifact contract + orphan sweep)",
                          "AGENTS.new §7 (execution posture + budgets + routing)")
CG = "CONTEXT.new (script-generated)"
CJ = "cyberstrike.json (machine config, not prose)"
HE1 = "HOME-ELEVATION class 1 (attestation + create-up use-conditions)"
HE2 = "HOME-ELEVATION class 2 (SSOT row schema + harvest instruments)"
HE3 = "HOME-ELEVATION class 3 (six standing research surfaces)"
HE4 = "HOME-ELEVATION class 4 (human-targeting boundary)"

DESTS = [
    # --- AGENTS.md (indices 0..63, dump order file:line) ---
    (A7, "execute/pivot posture consolidated"),
    (A7, "tool-routing chain kept as one compact line"),
    ("DROPPED", "Claude/Codex research-plane wiring receipt; cockpit never routes it"),
    ("DROPPED", "research-plane receipt (same class as sci-hub row)"),
    ("DROPPED", "superseded quarantine note, historical"),
    ("DROPPED", "research-plane receipt"),
    ("DROPPED", "clause itself states it is out of cockpit scope"),
    (CG, "permission/tool-surface knob facts are generated; posture sentence in §7"),
    (A1, "standing grant collapses into ONE pointer (HOME + estate-offensive-doctrine skill)"),
    (A1, "scope enumeration -> HOME/skill; §1 keeps pointer only"),
    (A1, "Bolt/Databricks enumeration -> HOME pointer"),
    (A1, "Cursor enumeration -> HOME pointer"),
    (A1, "AWS/IdP enumeration -> HOME pointer"),
    (A1, "OpenAI grant enumeration -> HOME pointer"),
    (A1, "Anthropic grant enumeration -> HOME pointer"),
    (A1, "Z.AI enumeration -> HOME pointer"),
    (A1, "catch-all enumeration -> HOME pointer"),
    (A1, "public-recon intel list -> HOME pointer"),
    (A2, "credential-presence estate test named in §2; pivot scope = OWNER-PENDING e3"),
    ("DROPPED", "file navigation chrome; new file carries its own header"),
    (HE1, "operator attestation (verbatim proposal text class 1)"),
    (HE1, "attested identities list header"),
    (HE1, "attested identity: costin.ionescu"),
    (HE1, "attested identity: prekzursil1993"),
    (HE1, "attested identity: ngo PAT"),
    (HE1, "attested identity: alv PAT"),
    (HE1, "attested identity: andre.fenti session"),
    (HE1, "attestation extension to all discovered secrets; bounded by §2 A5 victim ban"),
    (HE1, "use-conditions header"),
    (HE1, "full-spectrum use + create-up + NEVER-ROTATE (A1 restates the rule once)"),
    (HE1, "create-up doctrine, all credential classes"),
    (HE4, "no deception attacks on credential holders (human-targeting boundary)"),
    (A7, "rate discipline + disagreement-surfacing protocol consolidated"),
    (HE2, "secret pursuit as first-class objective"),
    (HE2, "SSOT row schema (sha8 AND plaintext, supersede-only)"),
    (A7, "transcript hygiene: chat carries sha8 + shapes"),
    (HE2, "harvest instruments: harvest-miner, quota-canary, firewatch"),
    (HE4, "boundary applies to HOW secrets are obtained"),
    (HE3, "standing research surfaces intro"),
    (HE3, "surface 1 BFF SMS-send (tier itself = OWNER-PENDING e1)"),
    (HE3, "surface 2 email-existence oracle"),
    (HE3, "surface 3 Streamlit/JFrog fingerprints"),
    (HE3, "surface 4 Dev-lake PII 78/115"),
    (HE3, "surface 5 guardgap A2"),
    (HE3, "surface 6 4-persona MQTT matrix"),
    (HE3, "standing-not-wave directive"),
    (CG, "jb-library availability is generated from live MCP map"),
    ("DROPPED", "single-copy path receipt; skill index owns SSOT pointers"),
    (CG, "skill roots are generated facts"),
    (A1, "carrier classes covered by scope pointer"),
    (A1, "jailbreak-target grant covered by scope pointer"),
    (A7, "anti-refusal posture line"),
    (A7, "rate discipline + overlay log-and-pivot"),
    (A0, "single canonical posture banner (was x3 across files)"),
    (A7, "overlay = measured product classifier (CS-01 truth, Phase-1 fixed)"),
    (CG, "brain/wire table -> generated provider truth incl. kimi-shims"),
    (CG, "Astra row -> generated provider truth"),
    (CG, "Daybreak Blue row -> generated provider truth"),
    (CG, "Anthropic row -> generated provider truth"),
    (CG, "Z.AI row -> generated provider truth"),
    (CG, "default-workhorse row -> generated provider truth"),
    (A7, "overlay handling: log outcome, pivot technique/brain"),
    (A2, "§2 Tier A/B enumeration replaces 'refuse surface EMPTY' prose (CS-04/07 collision fix)"),
    (A2, "process-only exceptions -> A1 never-rotate, A4 no-unsolicited-send, isolated-profile rule"),
    # --- CONTEXT.md (64..71) ---
    (A7, "tool surface one line"),
    (A1, "cyber-target scope -> pointer"),
    (CG, "abliteration lane facts generated"),
    (CG, "default model facts generated"),
    ("DROPPED", "file chrome"),
    (A1, "Cursor plane -> HOME standing-scope pointer"),
    (HE3, "six surfaces consolidated once at HOME"),
    (A1, "Full-Surface Grant -> pointer"),
    # --- config.md (72..150) ---
    ("DROPPED", "table chrome; rows map individually"),
    (CG, "dbx model id generated"),
    (CG, "dbx model id generated"),
    (CG, "dbx model id generated"),
    (CG, "dbx alias generated"),
    ("DROPPED", "one-shot wiring receipt (re-apply script)"),
    ("DROPPED", "credential-location receipt; SSOT owns locations, §7 owns hygiene rule"),
    (CG, "default model paragraph -> generated"),
    (CG, "small_model + no-duplicate gotcha -> generated annotation"),
    (CG, "preserved routes -> generated"),
    ("DROPPED", "launch recipe; scripts/launch-glm53.ps1 + memory own it"),
    ("DROPPED", "launch recipe (dbx variant)"),
    (CJ, "knob value duplicated in prose; json owns it"),
    (A5, "singleton discipline via manifest liveness (G-12)"),
    (CG, "bolt-lab section derived from live config"),
    (CG, "port band derived from LIVE mcp map (live json spans 31100-31140; stale prose said -19)"),
    (CJ, "knob value; json owns it"),
    (A5, "orphan-sweep budget: scoped, supervisor-aware, never blind"),
    (CJ, "knob value; json owns it"),
    (A2, "Tier A/B list replaces removed-ban + empty-refuse prose"),
    ("DROPPED", "navigation"),
    ("DROPPED", "navigation"),
    ("DROPPED", "navigation"),
    ("DROPPED", "navigation"),
    (CJ, "knob value; json owns it"),
    ("DROPPED", "navigation (HOME pointer restated in §1)"),
    (CJ, "knob value; json owns it"),
    (CG, "abliteration endpoint/model generated; rotator history (SSE fix, key pool, autostart) -> memory"),
    (CG, "lane-3 model ids generated from live json"),
    (CG, "kimi-shim truth generated (CS-01 regression guard)"),
    (CG, "preserved routes generated"),
    (CJ, "knob value; json owns it"),
    (CJ, "knob value; json owns it"),
    (CJ, "knob value; json owns it"),
    (CJ, "knob value; json owns it"),
    (CJ, "posture knob lives in agent prompt (json)"),
    (A0, "S0 truth model: knob drift is fixed in json + regenerate, never prose-patched"),
    ("DROPPED", "load-path chrome; deploy-phase3.md owns wiring"),
    (A1, "Cursor plane bullets -> HOME standing-scope pointer"),
    (A1, "Cursor plane bullets -> pointer"),
    (A1, "Cursor plane bullets -> pointer"),
    (A1, "Cursor plane bullets -> pointer"),
    (A1, "Cursor plane bullets -> pointer"),
    (A1, "owner/employer estate -> HOME pointer"),
    (A1, "owner/employer estate -> HOME pointer"),
    (A1, "owner/employer estate -> HOME pointer"),
    (A1, "owner/employer estate -> HOME pointer"),
    (HE3, "surface 1"),
    (HE3, "surface 2"),
    (HE3, "surface 3"),
    (HE3, "surface 4"),
    (HE3, "surface 5"),
    (HE3, "surface 6"),
    (A1, "OpenAI full surface -> pointer"),
    (A1, "Anthropic full surface -> pointer"),
    (A1, "Z.AI full surface -> pointer"),
    (A2, "tool stop-rules never add scope bans; §2 is the only exclusion surface"),
    (A1, "grant status one line; history in HOME"),
    (A7, "overlay classifier (consolidated single copy)"),
    (A7, "overlay -> pivot to workhorse"),
    ("DROPPED", "superseded-ban history record (zero-authority-data)"),
    ("DROPPED", "owner-action receipt (apply flow)"),
    ("DROPPED", "SSOT path receipt"),
    ("DROPPED", "wiring receipt [x]"),
    ("DROPPED", "wiring receipt [x]"),
    ("DROPPED", "wiring receipt [x]"),
    ("DROPPED", "wiring receipt [x]"),
    ("DROPPED", "wiring receipt [x]"),
    ("DROPPED", "wiring receipt [x]"),
    ("DROPPED", "stale unchecked box (CS-06 class); bridge config not active"),
    ("DROPPED", "table intro chrome"),
    ("DROPPED", "table chrome"),
    (CG, "dbx-llm-gw provider role generated"),
    (CG, "dbx-ai MCP role generated"),
    (CG, "gateway line generated with requires-gateway annotation"),
    (CG, "model ids generated from live json"),
    ("DROPPED", "table chrome"),
    (CG, "dbx model id generated"),
    (CG, "dbx model id generated"),
    # --- instructions-fullpower-estate.md (151..153) ---
    (A7, "posture banner third copy consolidated"),
    (A1, "standing surfaces -> pointer"),
    (A2, "QZP-enrollment-OUT kept as named standing exclusion; exec-lane list -> §7; GitHub-health sentence program-stale"),
    # --- instructions-recon.md (154..174) ---
    (A7, "anti-refusal line consolidated"),
    (A7, "reflex override valid only inside estate scope; §2 floor still binds"),
    (A7, "no auth spray"),
    (A1, "Cursor scope -> pointer"),
    (HE3, "six surfaces -> HOME class 3"),
    (A1, "Bolt+workstation -> pointer"),
    (A7, "routing: firecrawl in-scope hosts only"),
    (A7, "routing: basic-memory for decisions/findings"),
    (A7, "routing: hacktricks first"),
    (A7, "routing: cve/github-security/osint intel"),
    (A7, "routing: hexstrike host pack"),
    (A7, "routing: C2 estate-lab"),
    (A7, "routing: jb-library"),
    (A2, "isolated/agent-persistent browser process rule"),
    (A7, "posture opener consolidated"),
    (A7, "routing negative list kept"),
    (A5, "working-dir rule: engagement tree; Cowork-relative path retained pending owner ruling on D:\\ migration (audit rec 7)"),
    (A2, "consolidated into Tier A/B enumeration"),
    (A7, "solve-not-evaluate, pivot same turn"),
    (A7, "no narrative-only conclusions; execute remaining classes"),
    (A7, "live verification / artifacts over theory"),
]


def main():
    sys.path.insert(0, str(REPO / "scripts"))
    import gen_migration
    clauses = gen_migration.dedupe(gen_migration.all_clauses())
    ordered = sorted(clauses.items(), key=lambda kv: kv[1]["sources"][0])
    if len(ordered) != len(DESTS):
        print(f"FATAL: dump has {len(ordered)} clauses but DESTS has {len(DESTS)} decisions")
        for i in range(max(len(ordered), len(DESTS))):
            src = ordered[i][1]["sources"][0] if i < len(ordered) else "??"
            print(i, src)
        return 1
    mapping = {k: {"dest": d, "note": n} for (k, _), (d, n) in zip(ordered, DESTS)}
    MAP_PATH.write_text(json.dumps(mapping, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {MAP_PATH} with {len(mapping)} content-keyed rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
