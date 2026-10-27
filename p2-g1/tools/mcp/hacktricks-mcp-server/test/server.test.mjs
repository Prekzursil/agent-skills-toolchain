import assert from "node:assert/strict";
import { test } from "node:test";

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { SERVER_NAME, SERVER_VERSION, createServer } from "../dist/server.js";

function healthyDeps() {
  return {
    corpus: { ok: true, root: "/c", revision: "a".repeat(40), committedAt: "2026-01-01T00:00:00Z" },
    exec: async () => ({
      stdout: "",
      exitCode: 1,
      timedOut: false,
      bufferExceeded: false,
      spawnError: null,
    }),
    git: async () => ({ ok: true, stdout: "" }),
    fs: {
      async pathExists() {
        return true;
      },
      async realpath(p) {
        return p;
      },
      async statFile() {
        return null;
      },
      async readTextFile() {
        return "";
      },
      async listDir(p) {
        return p === "/c/src" ? [{ name: "pentesting-web", isDirectory: true }] : [];
      },
    },
    now: () => new Date("2026-01-02T00:00:00Z"),
    newId: () => "req-1",
  };
}

async function connectedClient() {
  const server = createServer(healthyDeps());
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  const client = new Client({ name: "test-client", version: "0.0.0" });
  await Promise.all([server.connect(serverTransport), client.connect(clientTransport)]);
  return client;
}

test("server exposes its identity constants", () => {
  assert.equal(SERVER_NAME, "hacktricks-mcp-hardened");
  assert.equal(SERVER_VERSION, "1.3.4-hardened.1");
});

test("listTools returns the seven tools over a real MCP round-trip", async () => {
  const client = await connectedClient();
  const list = await client.listTools();
  assert.equal(list.tools.length, 7);
  assert.ok(list.tools.some((t) => t.name === "search_hacktricks"));
  await client.close();
});

test("callTool dispatches a known tool and returns a structured envelope", async () => {
  const client = await connectedClient();
  await client.listTools();
  const result = await client.callTool({ name: "list_hacktricks_categories", arguments: {} });
  assert.equal(result.structuredContent.ok, true);
  assert.deepEqual(result.structuredContent.data.categories, ["pentesting-web"]);
  await client.close();
});

test("callTool tolerates missing arguments and rejects an unknown tool", async () => {
  const client = await connectedClient();
  const noArgs = await client.callTool({ name: "list_hacktricks_categories" });
  assert.equal(noArgs.structuredContent.ok, true);
  const unknown = await client.callTool({ name: "does_not_exist", arguments: {} });
  assert.equal(unknown.isError, true);
  assert.equal(unknown.structuredContent.error.code, "query_invalid");
  assert.equal(unknown.structuredContent.error.subcode, "unknown_tool");
  await client.close();
});
