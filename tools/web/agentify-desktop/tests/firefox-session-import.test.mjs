import test from 'node:test';
import assert from 'node:assert/strict';
import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs/promises';
import { DatabaseSync } from 'node:sqlite';

import { compress as snappyCompress } from 'snappyjs';

import {
  decodeFirefoxLocalStorageValue,
  listFirefoxProfiles,
  readFirefoxBootstrapFromProfile,
  toElectronCookieDetails
} from '../firefox-session-import.mjs';

async function tempDir() {
  return await fs.mkdtemp(path.join(os.tmpdir(), 'agentify-firefox-import-test-'));
}

function createCookiesDb(file) {
  const db = new DatabaseSync(file);
  db.exec(`
    CREATE TABLE moz_cookies (
      id INTEGER PRIMARY KEY,
      originAttributes TEXT,
      name TEXT,
      value TEXT,
      host TEXT,
      path TEXT,
      expiry INTEGER,
      lastAccessed INTEGER,
      creationTime INTEGER,
      isSecure INTEGER,
      isHttpOnly INTEGER,
      inBrowserElement INTEGER,
      sameSite INTEGER,
      schemeMap INTEGER,
      isPartitionedAttributeSet INTEGER,
      updateTime INTEGER
    );
  `);
  return db;
}

function createLocalStorageDb(file) {
  const db = new DatabaseSync(file);
  db.exec(`
    CREATE TABLE data (
      key TEXT,
      utf16_length INTEGER,
      conversion_type INTEGER,
      compression_type INTEGER,
      last_access_time INTEGER,
      value BLOB
    );
    CREATE TABLE database (
      origin TEXT,
      usage INTEGER,
      last_vacuum_time INTEGER,
      last_analyze_time INTEGER,
      last_vacuum_size INTEGER
    );
  `);
  return db;
}

function encodeLocalStorageValue(value, { compressed = false } = {}) {
  const bytes = Buffer.from(String(value), 'utf8');
  return compressed ? Buffer.from(snappyCompress(bytes)) : bytes;
}

async function buildFirefoxProfileFixture() {
  const dir = await tempDir();
  const profilePath = path.join(dir, 'k4cy1nuq.default-release');
  await fs.mkdir(path.join(profilePath, 'storage', 'default', 'https+++chatgpt.com', 'ls'), { recursive: true });
  await fs.mkdir(path.join(profilePath, 'storage', 'default', 'https+++auth.openai.com', 'ls'), { recursive: true });

  const cookiesDb = createCookiesDb(path.join(profilePath, 'cookies.sqlite'));
  const insertCookie = cookiesDb.prepare(`
    INSERT INTO moz_cookies (
      originAttributes, name, value, host, path, expiry, lastAccessed, creationTime,
      isSecure, isHttpOnly, inBrowserElement, sameSite, schemeMap,
      isPartitionedAttributeSet, updateTime
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);
  insertCookie.run('', '__Secure-next-auth.session-token', 'chatgpt-cookie', '.chatgpt.com', '/', 4102444800, 0, 0, 1, 1, 0, 0, 0, 0, 0);
  insertCookie.run('', 'auth-token', 'auth-cookie', 'auth.openai.com', '/', 4102444800, 0, 0, 1, 1, 0, 1, 0, 0, 0);
  insertCookie.run('^partitionKey=%28https%2Cchatgpt.com%29', 'skip-origin-attr', 'x', '.chatgpt.com', '/', 4102444800, 0, 0, 1, 0, 0, 0, 0, 0, 0);
  insertCookie.run('', 'skip-partitioned', 'y', '.openai.com', '/', 4102444800, 0, 0, 1, 0, 0, 2, 0, 1, 0);
  insertCookie.run('', 'skip-other-domain', 'z', '.example.com', '/', 4102444800, 0, 0, 1, 0, 0, 0, 0, 0, 0);
  cookiesDb.close();

  const chatDb = createLocalStorageDb(path.join(profilePath, 'storage', 'default', 'https+++chatgpt.com', 'ls', 'data.sqlite'));
  const insertChat = chatDb.prepare(`
    INSERT INTO data (key, utf16_length, conversion_type, compression_type, last_access_time, value)
    VALUES (?, ?, ?, ?, ?, ?)
  `);
  insertChat.run('RESUME_TOKEN_STORE_KEY', 2, 1, 0, 0, encodeLocalStorageValue('{}'));
  insertChat.run('statsig.last_modified_time.evaluations', 32, 1, 1, 0, encodeLocalStorageValue('{"ok":true}', { compressed: true }));
  chatDb.close();

  const authDb = createLocalStorageDb(path.join(profilePath, 'storage', 'default', 'https+++auth.openai.com', 'ls', 'data.sqlite'));
  const insertAuth = authDb.prepare(`
    INSERT INTO data (key, utf16_length, conversion_type, compression_type, last_access_time, value)
    VALUES (?, ?, ?, ?, ?, ?)
  `);
  insertAuth.run('statsig.stable_id.444584300', 36, 1, 0, 0, encodeLocalStorageValue('"demo-stable-id"'));
  authDb.close();

  return { dir, profilePath };
}

test('listFirefoxProfiles prefers default-release profile', async () => {
  const dir = await tempDir();
  await fs.mkdir(path.join(dir, 'rjbMjwtv.Profile 1'));
  await fs.mkdir(path.join(dir, 'k4cy1nuq.default-release'));
  await fs.mkdir(path.join(dir, 'wwfd9hcr.default'));

  const profiles = await listFirefoxProfiles({ profilesRoot: dir });
  assert.deepEqual(
    profiles.map((p) => ({ id: p.id, isDefault: p.isDefault })),
    [
      { id: 'k4cy1nuq.default-release', isDefault: true },
      { id: 'wwfd9hcr.default', isDefault: false },
      { id: 'rjbMjwtv.Profile 1', isDefault: false }
    ]
  );
});

test('decodeFirefoxLocalStorageValue handles plain and snappy-compressed UTF-8 payloads', async () => {
  assert.equal(
    decodeFirefoxLocalStorageValue({ value: Buffer.from('{"ok":true}', 'utf8'), conversionType: 1, compressionType: 0 }),
    '{"ok":true}'
  );

  const compressed = encodeLocalStorageValue('{"compressed":true}', { compressed: true });
  assert.equal(
    decodeFirefoxLocalStorageValue({ value: compressed, conversionType: 1, compressionType: 1 }),
    '{"compressed":true}'
  );

  assert.throws(
    () => decodeFirefoxLocalStorageValue({ value: Buffer.from('x'), conversionType: 1, compressionType: 9 }),
    /unsupported_compression_type/
  );
});

test('toElectronCookieDetails maps sameSite and host-only semantics', () => {
  const domainCookie = toElectronCookieDetails({
    name: 'session',
    value: 'abc',
    host: '.chatgpt.com',
    path: '/',
    expiry: 4102444800,
    isSecure: 1,
    isHttpOnly: 1,
    sameSite: 0
  });
  assert.equal(domainCookie.domain, '.chatgpt.com');
  assert.equal(domainCookie.sameSite, 'no_restriction');
  assert.equal(domainCookie.url, 'https://chatgpt.com/');

  const hostOnlyCookie = toElectronCookieDetails({
    name: 'host-only',
    value: 'abc',
    host: 'auth.openai.com',
    path: '/login',
    expiry: 0,
    isSecure: 1,
    isHttpOnly: 0,
    sameSite: 256
  });
  assert.equal(hostOnlyCookie.domain, undefined);
  assert.equal(hostOnlyCookie.sameSite, 'unspecified');
  assert.equal(hostOnlyCookie.url, 'https://auth.openai.com/login');
  assert.equal(hostOnlyCookie.expirationDate, undefined);
});

test('readFirefoxBootstrapFromProfile snapshots Firefox state, filters cookies, and decodes localStorage', async () => {
  const { profilePath } = await buildFirefoxProfileFixture();
  const out = await readFirefoxBootstrapFromProfile({ profilePath });

  assert.equal(out.summary.cookies.imported, 2);
  assert.equal(out.summary.cookies.skippedOriginAttributes, 1);
  assert.equal(out.summary.cookies.skippedPartitioned, 1);
  assert.equal(out.summary.cookies.skippedHost, 1);
  assert.deepEqual(
    out.cookies.map((c) => c.name).sort(),
    ['__Secure-next-auth.session-token', 'auth-token']
  );

  assert.equal(out.localStorageByOrigin['https://chatgpt.com'].RESUME_TOKEN_STORE_KEY, '{}');
  assert.equal(out.localStorageByOrigin['https://chatgpt.com']['statsig.last_modified_time.evaluations'], '{"ok":true}');
  assert.equal(out.localStorageByOrigin['https://auth.openai.com']['statsig.stable_id.444584300'], '"demo-stable-id"');
  assert.deepEqual(out.summary.localStorage, {
    'https://chatgpt.com': 2,
    'https://auth.openai.com': 1
  });
});
