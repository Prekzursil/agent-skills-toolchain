# Promote the reviewer receipt into the AUD-0060 artifact (merge-only; preserve all other fields).
import json

ART = r"C:\Users\Prekzursil\source\agent-skills-toolchain\command-center\audit\AUD-0060-mcp-tool-surface-inventory.json"
NOTES = (
    "Fresh-context falsification attempt paid 2026-09-19 (reviewer had not seen this unit's transcript). "
    "(1) Re-derived the configured-server count from the registry SSOT ~/.agents/agents.json: 90 total / 82 enabled / "
    "70 targeting claude — numerically disjoint from headline enabled_declared=16, but the registry is NOT this "
    "headline's claimed primary source: observation aud0015_enabled_declared_count (artifact line 270) anchors "
    "AUD-0015, whose own probe (command-center/audit/AUD-0015-mcp-scope-resolution.json:35, censused ~/.mcp.json + "
    "~/.claude.json root/per-project + ~/.claude/settings.json on the owner host) reports STATE_COUNTS "
    "ENABLED-DECLARED=16 of SERVER_COUNT=143. I re-parsed AUD-0015 /report/servers myself: exactly 16 "
    "ENABLED-DECLARED, and their names are set-identical to probe1's 16 SERVER rows ('codex' and 'fiddler' live only "
    "in the live-config planes, absent from the registry — a plane mismatch the artifact already discloses as open "
    "defect AUD-0060-D-SCOPE). (2) Counter-example hunt on internal sums via a mechanically independent re-parse of "
    "command-center/p2-wave/probes/AUD-0060/probe1-tool-surface.raw.txt: SUMMARY line 34 claims enabled=16 "
    "unreachable=16 session_tools=19 session_schema_bytes=30725; my re-derivation: 16 SERVER rows all UNREACHABLE, "
    "session tools 1+11+7=19, schema bytes 2254+19617+8854=30725 — all close. Planted control at raw line 6 "
    "(fake-mcp tool_count=1 schema_bytes=108) and the zero-state mutation control (planted-zero tool_count=0) both "
    "behave as claimed. Probe2 matrix: 23 CAP rows, 16 verified=True (matches hist_call_verified=16), verified "
    "tool_count sum=707. Headline (artifact line 267) SURVIVED falsification as scoped; no invented numbers "
    "(unreachable kept null, not zero). Caveats: artifact drifted from its self-declared hash before review "
    "(on-disk 21603 bytes / sha a1f67c2a vs declared 21231 / fa99cd59) yet counts are triple-confirmed across "
    "artifact-embedded raw_output, on-disk raw.txt, and on-disk probe JSON; and this PASS certifies the numbers as "
    "claimed, NOT that the estate's configured population is 16 (registry says 82 enabled, 70 claude-targeted) — "
    "that scope gap remains open defect AUD-0060-D-SCOPE. Raw evidence: "
    "command-center/p2-wave/reviews/AUD-0060/falsification-rederivation.raw.txt."
)

with open(ART, encoding="utf-8") as f:
    art = json.load(f)

art["reviewer"].update(
    {
        "verdict": "PASS",
        "independent": True,
        "fresh_context": True,
        "reviewer_id": "c5-fresh-context-claude-2026-09-19",
        "vendor": "claude",
        "reviewed_at": "2026-09-19T12:56:07Z",
        "notes": NOTES,
    }
)

with open(ART, "w", encoding="utf-8", newline="\n") as f:
    json.dump(art, f, indent=2, ensure_ascii=False)
    f.write("\n")

# fail-closed re-validation: re-read + assert
with open(ART, encoding="utf-8") as f:
    chk = json.load(f)
r = chk["reviewer"]
assert r["verdict"] == "PASS" and r["independent"] is True and len(r["notes"]) >= 200
assert chk["unit_id"] == "AUD-0060" and chk["report"]["headline"].startswith(
    "enabled_declared=16"
)
assert len(chk["report"]["observations"]) == 8 and len(chk["defects"]) == 3
print(
    f"SUCCESS:promote-review notes_len={len(r['notes'])} fields_preserved observations=8 defects=3 tests=3"
)
