// R4 third-mechanism probe: Node.js (V8 JSON.parse) — mechanically different from the
// python json parses used by the original lane and verifier V2.
// Targets: codacy (known-present CONTROL), codecov, digitalocean (claims under test).
// SAFETY: never prints credential VALUES — only env key names, lengths, literal flags.
const fs = require('fs');
const os = require('os');
const path = require('path');
const HOME = os.homedir();
const TARGETS = ['codacy', 'codecov', 'digitalocean'];

function safeStr(s, max) {
  s = String(s);
  if (/[A-Za-z0-9+/_=-]{25,}/.test(s)) return '<opaque len=' + s.length + '>';
  return s.length > max ? s.slice(0, max) + '…' : s;
}
function envShape(env) {
  if (!env || typeof env !== 'object' || Array.isArray(env)) return undefined;
  const out = {};
  for (const [k, v] of Object.entries(env)) {
    const s = String(v);
    // literal = value is NOT an env-var reference (${VAR}, %VAR%, $VAR)
    out[k] = { len: s.length, literal: !/\$\{|%[^%]+%|^\$[A-Z]/.test(s) };
  }
  return out;
}
function argShape(a) {
  return safeStr(a, 90);
}
function entryShape(name, e) {
  if (e === null || typeof e !== 'object') return { name, scalar: safeStr(e, 60) };
  const o = { name };
  for (const k of ['type', 'command', 'enabled', 'transport']) if (k in e) o[k] = e[k];
  if (e.url) {
    try {
      const u = new URL(e.url);
      o.url = u.protocol + '//' + u.host + (u.pathname || '');
      o.url_query_len = (u.search || '').length;
    } catch { o.url = '<unparsed len=' + String(e.url).length + '>'; }
  }
  if (Array.isArray(e.args)) o.args = e.args.map(argShape);
  const es = envShape(e.env); if (es) o.env = es;
  if (e.headers && typeof e.headers === 'object') o.headers = Object.keys(e.headers);
  if (Array.isArray(e.targets)) o.targets = e.targets;
  return o;
}
const report = { probe: 'node-v8-jsonparse', generated: new Date().toISOString(), surfaces: {} };
function addSurface(label, data) { report.surfaces[label] = data; }

// 1) ~/.agents/agents.json (SSOT registry)
try {
  const reg = JSON.parse(fs.readFileSync(path.join(HOME, '.agents', 'agents.json'), 'utf8'));
  const servers = (reg.mcp && reg.mcp.servers) || {};
  const hits = {};
  for (const [k, v] of Object.entries(servers)) if (TARGETS.includes(k)) hits[k] = entryShape(k, v);
  addSurface('agents.json(registry)', { total: Object.keys(servers).length, hits });
} catch (err) { addSurface('agents.json(registry)', { error: String(err) }); }

// 2) ~/.claude.json (root mcpServers + per-project defs + enable/disable marks)
try {
  const cj = JSON.parse(fs.readFileSync(path.join(HOME, '.claude.json'), 'utf8'));
  const root = cj.mcpServers || {};
  const hits = {};
  for (const [k, v] of Object.entries(root)) if (TARGETS.includes(k)) hits[k] = entryShape(k, v);
  const projDefs = {}, marks = {};
  for (const [pk, p] of Object.entries(cj.projects || {})) {
    for (const t of TARGETS) {
      if (p && p.mcpServers && p.mcpServers[t]) {
        (projDefs[t] = projDefs[t] || []).push({ project: pk, entry: entryShape(t, p.mcpServers[t]) });
      }
    }
    for (const ln of ['enabledMcpServers', 'disabledMcpServers']) {
      const l = p && p[ln];
      if (Array.isArray(l)) for (const t of TARGETS) if (l.includes(t)) {
        const key = t + '.project_' + ln; marks[key] = (marks[key] || 0) + 1;
      }
    }
  }
  for (const ln of ['enabledMcpServers', 'disabledMcpServers']) {
    const l = cj[ln];
    if (Array.isArray(l)) for (const t of TARGETS) if (l.includes(t)) marks[t + '.ROOT_' + ln] = 1;
  }
  const projSummary = {};
  for (const [t, a] of Object.entries(projDefs)) projSummary[t] = { count: a.length, sample: a.slice(0, 1) };
  addSurface('claude.json', { root_total: Object.keys(root).length, root_hits: hits, per_project_defs: projSummary, enable_disable_marks: marks });
} catch (err) { addSurface('claude.json', { error: String(err) }); }

// 3) ~/.gemini/settings.json
try {
  const g = JSON.parse(fs.readFileSync(path.join(HOME, '.gemini', 'settings.json'), 'utf8'));
  const ms = g.mcpServers || {};
  const hits = {};
  for (const [k, v] of Object.entries(ms)) if (TARGETS.includes(k)) hits[k] = entryShape(k, v);
  addSurface('gemini/settings.json', { total: Object.keys(ms).length, hits });
} catch (err) { addSurface('gemini/settings.json', { error: String(err) }); }

// 4) ~/.cursor/mcp.json
try {
  const c = JSON.parse(fs.readFileSync(path.join(HOME, '.cursor', 'mcp.json'), 'utf8'));
  const ms = c.mcpServers || {};
  const hits = {};
  for (const [k, v] of Object.entries(ms)) if (TARGETS.includes(k)) hits[k] = entryShape(k, v);
  addSurface('cursor/mcp.json', { total: Object.keys(ms).length, hits });
} catch (err) { addSurface('cursor/mcp.json', { error: String(err) }); }

// 5) ~/.mcp.json
try {
  const m = JSON.parse(fs.readFileSync(path.join(HOME, '.mcp.json'), 'utf8'));
  const ms = m.mcpServers || {};
  const hits = {};
  for (const [k, v] of Object.entries(ms)) if (TARGETS.includes(k)) hits[k] = entryShape(k, v);
  addSurface('.mcp.json', { total: Object.keys(ms).length, hits });
} catch (err) { addSurface('.mcp.json', { error: String(err) }); }

// 6) ~/.McpHub/config.json — structure unknown; recursive walk for target keys anywhere
try {
  const h = JSON.parse(fs.readFileSync(path.join(HOME, '.McpHub', 'config.json'), 'utf8'));
  const found = {};
  let totalLeafNames = 0;
  (function walk(node, p) {
    if (node && typeof node === 'object') {
      for (const [k, v] of Object.entries(node)) {
        if (TARGETS.includes(k)) found[p + '/' + k] = entryShape(k, v);
        walk(v, p + '/' + k);
      }
    }
  })(h, '');
  addSurface('.McpHub/config.json', { top_keys: Object.keys(h), found });
} catch (err) { addSurface('.McpHub/config.json', { error: String(err) }); }

const outPath = path.join(path.dirname(process.argv[1]), 'r4_probe_out.json');
fs.writeFileSync(outPath, JSON.stringify(report, null, 1));
console.log('WROTE ' + outPath);
for (const [s, r] of Object.entries(report.surfaces)) {
  let names;
  if (r.error) names = ['ERROR: ' + r.error.slice(0, 80)];
  else if (r.hits) names = Object.keys(r.hits);
  else if (r.found) names = Object.keys(r.found).map(x => x.split('/').pop() + '@' + x);
  else names = [];
  console.log(s + ' | total=' + (r.total ?? r.root_total ?? '-') + ' | targets=' + names.join(' ; '));
}
