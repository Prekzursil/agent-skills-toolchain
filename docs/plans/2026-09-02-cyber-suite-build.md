# Cyber suite build contract (2026-09-02)

**Branch:** `cursor/cyber-suite-full-program` (base `main`).
**Grill SSOT:** `docs/plans/2026-09-02-cyber-suite-gemhunt.md` (G1=D, G2=C with H1/H2 slice, G4=this branch, G6 darknet FULL search).
**Parent:** owns `.agents/agents.json`, `.agents/mcp-cursor-parked-31.json`, `.provenance/.agents/agents.json.md`, `.agents/tests/test_mcp_control_plane_live.py`, and this pair of plan files.

This is the implementer contract. Follow it. Do not re-grill.

## Hard bans (slice, then finish the rest)

- Do **not** author C2 / stealer / ransomware / mass-abuse kits, exploit PoCs, malware, or attack procedures (owner-ops H2 + Cursor cyber rule).
- Do **not** target third-party systems (H1). Estate-local / owner-authorized / lab range only.
- Do **not** add Sliver or Metasploit-*run* runtimes.
- Live authorized scanning rides the **existing** `hexstrike-ai-authorized-engagement` skill after rails are green.
- `darknet-mcp-server` is **full search** (onion, IntelX, Hudson Rock included). That is CTI lookup, not kit-building. Parent registers it.

## Shared rules for every wave

1. **Write-as-you-go receipt.** Immediately create `docs/plans/cyber-receipts/<wave-id>.md` as a skeleton with every claim marked `UNKNOWN - not yet measured` and this sentence:

   > If it still reads this way, the unit died before measuring anything and no verdict here may be cited.

   Rewrite the receipt at each milestone. Partial + truthful beats perfect + unwritten.
2. **Disjoint files.** Edit ONLY the paths listed for your wave. If you need a shared file, put the exact block in the receipt under `PARENT MERGE` and stop.
3. **Tests first.** For any Python/script, write tests (fakes, no live network) before implementation. Run them. For Markdown-only skills, add a tiny consistency test or fixture if the skill ships a script; otherwise the skill is the artifact.
4. **Skill shape.** Canonical root is `.agents/skills/<name>/`. Dual-write the same files under `skills/<name>/`. Frontmatter of `SKILL.md` contains **only** `name` and `description` (optional `license:` is already used by some skills — match an existing security skill). Add `agents/openai.yaml` with quoted string values (`display_name`, `short_description`, `default_prompt`). Folder names lower-case hyphen-case.
5. **Ruff.** `export PATH="$HOME/.local/bin:$PATH"`; pin `ruff==0.15.17`. `ruff check` + `ruff format` on files you touch. `python3` not `python`.
6. **Git.** You are on `cursor/cyber-suite-full-program`. Path-scoped commits only:

   ```
   git add -- <your paths>
   git commit -o -m "..." -- <your paths>
   git push -u origin cursor/cyber-suite-full-program
   ```

   If the commit races, retry the same path-scoped commit. Never `--no-verify`. Never edit other waves' files to "help". Never merge, force-push, or delete branches.
7. **No secrets.** Env names only (`${NAME}`), never live values.

## Wave roster (one implementer each)

| id | Paths | Deliverable |
|----|-------|-------------|
| W-rails | `hooks/target-scope/**`, `hooks/security-action/**` | R1 target-in-scope PreToolUse hook (clone `hooks/file-scope/` pattern: fail-open, sidecar globs, tests). R4 security-action evidence ledger (borrow `agent-self/config/hooks/event-ledger/` ideas, new dir). Do not modify existing file-scope/ulysses. |
| W-routing | `.agents/skills/hacktricks/references/security-mcp-routing.md`, `skills/hacktricks/references/security-mcp-routing.md`, `agent-self/skills/hacktricks/references/security-mcp-routing.md`, `.agents/skills/deep-research/references/research_harness/routing.py` + tests + dual-write `skills/deep-research/` counterpart | Add `vt_*` IOC row, unrouted `cve-mcp` tools (`osv_batch`, `cve_report`, `ghsa_*`, `m365_*`, `dns_email_security`), new `ioc`/`attack` capability mirroring `vuln`. Update `test_routing.py`. |
| W-corpus | `.agents/skills/sec-corpora-update/**`, `skills/sec-corpora-update/**` | Add fail-open one-liners: SecLists, Exploit-DB/searchsploit, attack-stix-data, misp-galaxy, misp-warninglists, signature-base, CTID adversary-emulation-library, control-validation-compass, sysmon-modular, LOLDrivers. Keep exit 0. Document licenses in the skill. |
| W-blue | `.agents/skills/detection-as-code/**`, `skills/detection-as-code/**` | Skill: Sigma authoring via rsigma/sigma-cli, Zircolite/Hayabusa oracles, EvidenceForge / EVTX-ATTACK-SAMPLES backtest with expected-hit manifests, DeTT&CT/navlayers coverage. No daemon. |
| W-dfir | `.agents/skills/dfir-triage/**`, `skills/dfir-triage/**` | Skill wraps: Chainsaw, Hayabusa, dissect, EZ Tools/KAPE, Plaso, Velociraptor **offline collector**, tshark/Zeek/Suricata notes, varc/container-explorer/cloudgrep, email/phishing triage. Memory stays `volatility-3`; disk stays `offline-linux-disk-surgery`. |
| W-purple | `.agents/skills/purple-emulation/**`, `skills/purple-emulation/**` | ART runner (Invoke-Atomic on a range VM) + existing `claim-verify-gate` as "did the detection fire?"; Navigator/DeTT&CT ledger; Stratus Red Team for **owner cloud**; CALDERA mentioned as range REST, not a fleet MCP. Lab/owned only. |
| W-0day | `.agents/skills/vuln-research-loop/**`, `skills/vuln-research-loop/**` | Naptime-style loop over existing RE MCPs (ghidra/ida/binja/angr/qiling/frida) + ClusterFuzzLite + Atheris + CASR + OSS-Fuzz-Gen + Jackalope/TinyInst notes + patch-diff via ghidriff/bindiff. Own code/binaries only. **No exploit writing.** |
| W-cti | `.agents/skills/cti-lookup/**`, `skills/cti-lookup/**` | Borrow cti-expert defang/refang + STIX 2.1 export + report skeleton. Route to osint `vt_*`, cve-mcp, and (once registered) darknet-mcp-server **full** tool surface. Do not install a 67-command orchestrator. |
| W-cloud | `.agents/skills/cloud-container-security/**`, `skills/cloud-container-security/**` | Prowler, Trivy, kubescape, Steampipe/Powerpipe, cloudfox (non-destructive), trufflehog, Syft. Host-gated; no always-on daemon. Receipt lists the exact `agents.json` blocks for parent (trivy/prowler/kubescape disabled until binary present). |
| W-upgrades | `.agents/skills/security-review/**` + `skills/security-review/**`; `.agents/skills/malware-analysis-triage/**` + dual-write; `.agents/skills/security-threat-model/**` + dual-write; **new** `.agents/skills/native-fuzz/**` + `skills/native-fuzz/**` | Additive Trail of Bits scanner-driven loop (CC-BY-SA, attribute) into security-review; YARA rules-as-code (yara-forge/yaraQA) into malware-analysis-triage; Anthropic defending-code-reference-harness into security-threat-model; promote `go test -fuzz` + ASan/UBSan/MSan from `.agents/library/skills/golang-testing` + `cpp-testing` into live `native-fuzz`. Do not gut existing skill text. |

## Parent-owned MCP registrations (do not touch)

`github-security` (enabled), `darknet-mcp-server` (enabled, full 66-tool search), `mitre-attack-mcp` (enabled), `proxy-mcp` (default-off), `jadx-mcp`/`apktool-mcp`/`cloud-audit`/`rsigma`/`trivy` (host-gated, enabled false). Children may propose exact JSON in the receipt `PARENT MERGE` section.
