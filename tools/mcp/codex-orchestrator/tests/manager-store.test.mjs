import test from 'node:test';
import assert from 'node:assert/strict';
import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs/promises';

import { bindWorkspace, readHealthEvents, setThreadMetadata, writeRoute } from '../src/manager/store.mjs';

async function tempCodexHome() {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'codex-manager-store-'));
  const codexHome = path.join(root, '.codex');
  await fs.mkdir(codexHome, { recursive: true });
  return { root, codexHome };
}

test('manager store persists workspace bindings, route writes, and allows clearing tags', async () => {
  const { root, codexHome } = await tempCodexHome();
  try {
    const workspace = await bindWorkspace({
      codexHome,
      workspacePath: 'C:/repo',
      alias: 'repo'
    });
    assert.equal(workspace.path, 'C:/repo');
    assert.equal(workspace.alias, 'repo');

    const first = await setThreadMetadata({
      codexHome,
      threadId: 'thread-1',
      workspacePath: 'C:/repo',
      label: 'Discuss',
      tags: ['alpha', 'beta'],
      pinned: true
    });
    assert.equal(first.thread_id, 'thread-1');
    assert.equal(first.pinned, 1);
    assert.deepEqual(JSON.parse(first.tags_json), ['alpha', 'beta']);

    const cleared = await setThreadMetadata({
      codexHome,
      threadId: 'thread-1',
      tags: []
    });
    assert.deepEqual(JSON.parse(cleared.tags_json), []);

    const route = await writeRoute({
      codexHome,
      routeKey: 'chatgpt:C:/repo:discuss',
      value: { sessionKey: 'chatgpt:repo:discuss', protected: true }
    });
    assert.equal(route.route_key, 'chatgpt:C:/repo:discuss');
    assert.equal(route.value.protected, true);

    const events = await readHealthEvents({ codexHome, limit: 5 });
    assert.deepEqual(events, []);
  } finally {
    await fs.rm(root, { recursive: true, force: true });
  }
});
