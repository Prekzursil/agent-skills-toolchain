// Minimal MCP stdio client probe for cloakbrowser-mcp on Windows.
import { spawn } from 'node:child_process';

const proc = spawn('npx', ['-y', 'cloakbrowser-mcp@latest'], {
  shell: true,
  stdio: ['pipe', 'pipe', 'pipe'],
});

let buf = '';
const pending = new Map();
let nextId = 1;

proc.stdout.on('data', (d) => {
  buf += d.toString();
  let idx;
  while ((idx = buf.indexOf('\n')) >= 0) {
    const line = buf.slice(0, idx).trim();
    buf = buf.slice(idx + 1);
    if (!line) continue;
    try {
      const msg = JSON.parse(line);
      if (msg.id && pending.has(msg.id)) {
        pending.get(msg.id)(msg);
        pending.delete(msg.id);
      }
    } catch {}
  }
});
proc.stderr.on('data', (d) => process.stderr.write('[srv] ' + d));

function rpc(method, params, timeoutMs = 60000) {
  return new Promise((resolve, reject) => {
    const id = nextId++;
    const t = setTimeout(() => {
      pending.delete(id);
      reject(new Error(`timeout waiting for ${method}`));
    }, timeoutMs);
    pending.set(id, (msg) => {
      clearTimeout(t);
      resolve(msg);
    });
    const req = { jsonrpc: '2.0', id, method, params };
    proc.stdin.write(JSON.stringify(req) + '\n');
  });
}

function notify(method, params) {
  proc.stdin.write(JSON.stringify({ jsonrpc: '2.0', method, params }) + '\n');
}

const t0 = Date.now();
try {
  const init = await rpc('initialize', {
    protocolVersion: '2025-06-18',
    capabilities: {},
    clientInfo: { name: 'dive-probe', version: '0.0.1' },
  });
  console.log('== initialize:', JSON.stringify(init.result?.serverInfo));

  notify('notifications/initialized', {});

  const tools = await rpc('tools/list', {});
  const names = tools.result?.tools?.map((t) => t.name) ?? [];
  console.log('== tool count:', names.length);
  console.log('== cloak tools:', names.filter((n) => n.startsWith('cloakbrowser')));
  console.log('== sample tools:', names.filter((n) => /navigate|snapshot|click|type/.test(n)).slice(0, 8));

  // This should auto-download the CloakBrowser windows-x64 binary on first use.
  console.log('== navigating (downloads binary on first use)...');
  const nav = await rpc(
    'tools/call',
    { name: 'browser_navigate', arguments: { url: 'https://example.com/' } },
    420000,
  );
  const navText = JSON.stringify(nav.result ?? nav.error);
  console.log('== navigate elapsed_s:', ((Date.now() - t0) / 1000).toFixed(1));
  console.log('== navigate result (first 600 chars):', navText.slice(0, 600));
  process.exit(0);
} catch (e) {
  console.error('PROBE FAILED:', e.message);
  process.exit(1);
}
