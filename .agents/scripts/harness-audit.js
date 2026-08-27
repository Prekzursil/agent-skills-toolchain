#!/usr/bin/env node
/**
 * harness-audit.js — deterministic harness scorer for Miky's shared agent estate.
 * Wave B item 5 (2026-08-27), per the /harness-audit command contract
 * (~/.claude/commands/harness-audit.md, rubric 2026-05-19): 12 fixed categories,
 * each normalized 0-10, derived ONLY from explicit file/rule checks — reproducible
 * for the same on-disk state. No LLM judgment, no ad-hoc points.
 *
 * Usage: node harness-audit.js [repo|hooks|skills|commands|agents] [--format text|json]
 * (scopes other than `repo` filter which categories are reported; scoring is identical)
 *
 * Checks are deliberately simple: file exists, JSON parses, counts, sizes, freshness,
 * no-dupe. Every check names its exact path so a failure is directly actionable.
 */
'use strict';
const fs = require('fs');
const path = require('path');

const HOME = 'C:/Users/Prekzursil';
const P = (...seg) => path.join(HOME, ...seg);

const exists = f => { try { return fs.existsSync(f); } catch { return false; } };
const readText = f => { try { return fs.readFileSync(f, 'utf8'); } catch { return null; } };
const readJson = f => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch { return null; } };
const ageDays = f => { try { return (Date.now() - fs.statSync(f).mtimeMs) / 86400000; } catch { return Infinity; } };
const sizeKB = f => { try { return fs.statSync(f).size / 1024; } catch { return Infinity; } };

// A check: { name, path, points, pass } — category score = 10 * earned/possible.
function category(name, checks) {
  const possible = checks.reduce((s, c) => s + c.points, 0);
  const earned = checks.reduce((s, c) => s + (c.pass ? c.points : 0), 0);
  const score = possible ? Math.round((earned / possible) * 100) / 10 : 0;
  return { name, score, earned, possible, checks };
}

function build() {
  const cats = [];

  // 1. Tool Coverage — the control plane's config surfaces exist and parse.
  const agentsJson = readJson(P('.agents/agents.json'));
  let denyContradiction = false;
  if (agentsJson) {
    const servers = (agentsJson.mcp && agentsJson.mcp.servers) || agentsJson.servers || {};
    for (const k of ['markitdown', 'meta-tool']) {
      if (servers[k] && servers[k].enabled === true) denyContradiction = true;
    }
  }
  cats.push(category('Tool Coverage', [
    { name: 'agents.json exists and parses', path: P('.agents/agents.json'), points: 3, pass: !!agentsJson },
    { name: 'Cursor mcp.json exists and parses', path: P('.cursor/mcp.json'), points: 2, pass: !!readJson(P('.cursor/mcp.json')) },
    { name: 'Codex config.toml exists', path: P('.codex/config.toml'), points: 2, pass: exists(P('.codex/config.toml')) },
    { name: 'no enabled-but-Claude-denied registry entries (markitdown/meta-tool)', path: P('.agents/agents.json'), points: 3, pass: !!agentsJson && !denyContradiction },
  ]));

  // 2. Context Efficiency — the always-injected rules files stay lean and undupe'd.
  const claudeMd = readText(P('CLAUDE.md')) || '';
  const agentsMd = readText(P('AGENTS.md')) || '';
  cats.push(category('Context Efficiency', [
    { name: 'CLAUDE.md <= 12 KB (paid every turn)', path: P('CLAUDE.md'), points: 3, pass: sizeKB(P('CLAUDE.md')) <= 12 },
    { name: 'AGENTS.md <= 16 KB (paid every turn)', path: P('AGENTS.md'), points: 3, pass: sizeKB(P('AGENTS.md')) <= 16 },
    { name: 'AgentBridge tombstone not duplicated full-length in CLAUDE.md', path: P('CLAUDE.md'), points: 2, pass: !claudeMd.includes('The two rails that replaced it') },
    { name: 'no stale "not computable" budget-pacing claim in either rules file', path: P('AGENTS.md'), points: 2, pass: !/not (currently )?computable/i.test(claudeMd) && !/not (currently )?computable/i.test(agentsMd) },
  ]));

  // 3. Quality Gates — the dispatch manifest is valid and not oversubscribed.
  const manifest = readJson(P('.claude/hooks/_dispatch/manifest.json'));
  let stopOk = false, ceilingOk = false, stopCount = 0;
  if (manifest && manifest.events) {
    for (const [ev, spec] of Object.entries(manifest.events)) {
      const ceiling = spec.settings_timeout || 0;
      const checks = spec.checks || [];
      if (ev === 'Stop') {
        stopCount = checks.length;
        const sum = checks.reduce((s, c) => s + (c.timeout || 0), 0);
        stopOk = sum <= 100; // was 144s under a 35s ceiling pre-rebalance
      }
      ceilingOk = true;
      for (const c of checks) if ((c.timeout || 0) > ceiling) ceilingOk = false;
      if (!ceilingOk) break;
    }
  }
  cats.push(category('Quality Gates', [
    { name: 'dispatch manifest.json parses', path: P('.claude/hooks/_dispatch/manifest.json'), points: 3, pass: !!manifest },
    { name: 'Stop event timeout sum <= 100s (rebalanced)', path: P('.claude/hooks/_dispatch/manifest.json'), points: 3, pass: stopOk },
    { name: 'no per-check timeout above its event ceiling (inert-budget defect)', path: P('.claude/hooks/_dispatch/manifest.json'), points: 2, pass: ceilingOk },
    { name: 'dispatch wiring tests present (test_wiring.py)', path: P('.claude/hooks/_dispatch/test_wiring.py'), points: 2, pass: exists(P('.claude/hooks/_dispatch/test_wiring.py')) },
  ]));

  // 4. Memory Persistence — the supervised basic-memory stack + state stores.
  cats.push(category('Memory Persistence', [
    { name: 'basic-memory vault present (D:/basic-memory)', path: 'D:/basic-memory', points: 4, pass: exists('D:/basic-memory') },
    { name: 'basic-memory supervisor log present', path: P('.agents/logs/basic-memory-supervisor.log'), points: 3, pass: exists(P('.agents/logs/basic-memory-supervisor.log')) },
    { name: 'harness state dir present', path: P('.agents/state'), points: 3, pass: exists(P('.agents/state')) },
  ]));

  // 5. Eval Coverage — the harness's own test/verification artifacts.
  cats.push(category('Eval Coverage', [
    { name: 'dispatch manifest-presence test', path: P('.claude/hooks/_dispatch/test_manifest_presence.py'), points: 4, pass: exists(P('.claude/hooks/_dispatch/test_manifest_presence.py')) },
    { name: 'this scorer exists (numeric audits instead of NOT-CHECKED)', path: P('.agents/scripts/harness-audit.js'), points: 3, pass: exists(P('.agents/scripts/harness-audit.js')) },
    { name: 'execution log discipline in use (wave log on disk)', path: P('.agents/WAVE-ABCD-EXECUTION_2026-08-27.md'), points: 3, pass: exists(P('.agents/WAVE-ABCD-EXECUTION_2026-08-27.md')) },
  ]));

  // 6. Security Guardrails — veto surfaces + tamper tracer on the guards themselves.
  const cursorHooks = readJson(P('.cursor/hooks.json'));
  const hookCount = cursorHooks && cursorHooks.hooks ? Object.keys(cursorHooks.hooks).length : 0;
  const rules = readText(P('.codex/rules/default.rules')) || '';
  cats.push(category('Security Guardrails', [
    { name: 'Cursor hooks.json exists, parses, has >= 5 hook events', path: P('.cursor/hooks.json'), points: 3, pass: !!cursorHooks && hookCount >= 5 },
    { name: 'Codex execpolicy bans routine git writes', path: P('.codex/rules/default.rules'), points: 3, pass: /"git",\s*"commit"/.test(rules) && /"git",\s*"push"/.test(rules) },
    { name: 'guard-tamper tracer script present', path: P('.agents/scripts/guard-tamper-check.ps1'), points: 2, pass: exists(P('.agents/scripts/guard-tamper-check.ps1')) },
    { name: 'guard-tamper log fresh (< 3 days)', path: P('.agents/logs/guard-tamper.log'), points: 2, pass: ageDays(P('.agents/logs/guard-tamper.log')) < 3 },
  ]));

  // 7. Cost Efficiency — quota is measured, not guessed.
  const statusline = readText(P('.claude/statusline-command.sh')) || '';
  cats.push(category('Cost Efficiency', [
    { name: 'statusline parses rate_limits.five_hour/seven_day', path: P('.claude/statusline-command.sh'), points: 5, pass: statusline.includes('rate_limits.five_hour.used_percentage') && statusline.includes('rate_limits.seven_day.used_percentage') },
    { name: 'rules files point at the statusline fields for pacing', path: P('AGENTS.md'), points: 5, pass: agentsMd.includes('rate_limits.five_hour.used_percentage') },
  ]));

  // 8-12. Integration lanes — capability documented as a vault skill (SSOT), or honestly 0.
  const skillCat = (label, skillDirs) => category(label, skillDirs.map(d => ({
    name: `vault skill ${d} present`, path: P('.agents/skills', d, 'SKILL.md'),
    points: Math.round(10 / skillDirs.length), pass: exists(P('.agents/skills', d, 'SKILL.md')),
  })));
  cats.push(skillCat('GitHub Integration', ['gh-fix-ci', 'gh-address-comments']));
  cats.push(skillCat('Vercel Integration', ['vercel-deploy']));
  cats.push(skillCat('Netlify Integration', ['netlify-deploy']));
  cats.push(skillCat('Cloudflare Integration', ['cloudflare-deploy']));
  cats.push(skillCat('Fly Integration', ['fly-deploy']));

  return cats;
}

function main() {
  const args = process.argv.slice(2);
  const fmtIdx = args.indexOf('--format');
  const format = fmtIdx >= 0 ? (args[fmtIdx + 1] || 'text') : 'text';
  const scope = args.find(a => ['repo', 'hooks', 'skills', 'commands', 'agents'].includes(a)) || 'repo';

  const scopeFilter = {
    repo: () => true,
    hooks: c => ['Quality Gates', 'Security Guardrails'].includes(c.name),
    skills: c => c.name.includes('Integration') || c.name === 'Eval Coverage',
    commands: c => ['Tool Coverage', 'Cost Efficiency'].includes(c.name),
    agents: c => ['Tool Coverage', 'Memory Persistence', 'Context Efficiency'].includes(c.name),
  }[scope];

  const cats = build().filter(scopeFilter);
  const overall = Math.round(cats.reduce((s, c) => s + c.score, 0) * 10) / 10;
  const max = cats.length * 10;
  const failed = [];
  for (const c of cats) for (const chk of c.checks) if (!chk.pass) failed.push({ category: c.name, ...chk });
  failed.sort((a, b) => b.points - a.points);
  const top_actions = failed.slice(0, 3).map(f => `[${f.category}] ${f.name} (${f.path})`);

  const result = {
    rubric_version: '2026-05-19', scope, generated: new Date().toISOString(),
    overall_score: overall, max_score: max,
    categories: cats.map(c => ({ name: c.name, score: c.score, earned: c.earned, possible: c.possible })),
    failed_checks: failed.map(f => ({ category: f.category, name: f.name, path: f.path, points: f.points })),
    top_actions,
  };

  if (format === 'json') { console.log(JSON.stringify(result, null, 2)); return; }
  console.log(`Harness Audit (${scope}): ${overall}/${max}`);
  for (const c of cats) console.log(`- ${c.name}: ${c.score}/10 (${c.earned}/${c.possible} pts)`);
  if (failed.length) {
    console.log('\nFailed checks:');
    for (const f of failed) console.log(`- [${f.category}] ${f.name} -> ${f.path}`);
  }
  if (top_actions.length) {
    console.log('\nTop 3 Actions:');
    top_actions.forEach((a, i) => console.log(`${i + 1}) ${a}`));
  }
}

main();
