import assert from "node:assert/strict";
import { Readable, Writable } from "node:stream";
import { describe, it } from "node:test";

import {
  MCP_MAX_MESSAGE_BYTES,
  createMcpDispatcher,
  runStdioMcpServer,
} from "../src/mcp-server.ts";

describe("cyberstrike-gateway MCP adapter", () => {
  it("initializes under the one approved server name and lists exactly three tools", async () => {
    const dispatch = createMcpDispatcher({
      status: () => ({ status: "ok" }),
      capabilities: () => ({ revision: "a".repeat(64) }),
      invoke: async () => ({ ok: false, reasonCode: "unavailable" }),
    });
    const initialized = await dispatch({ jsonrpc: "2.0", id: 1, method: "initialize", params: {} });
    assert.equal(initialized.result.serverInfo.name, "cyberstrike-gateway");

    const listed = await dispatch({ jsonrpc: "2.0", id: 2, method: "tools/list", params: {} });
    assert.deepEqual(listed.result.tools.map((tool: { name: string }) => tool.name), [
      "harness_bridge_status",
      "harness_capabilities",
      "harness_invoke",
    ]);
    assert.equal(listed.result.tools.every((tool: { inputSchema: { additionalProperties: boolean } }) => tool.inputSchema.additionalProperties === false), true);
  });

  it("dispatches only the three named tools and rejects generic RPC/resources", async () => {
    const dispatch = createMcpDispatcher({
      status: () => ({ status: "ok" }),
      capabilities: () => ({ revision: "a".repeat(64) }),
      invoke: async (input) => ({ ok: false, reasonCode: "blocked", capability: input.capability }),
    });
    const status = await dispatch({
      jsonrpc: "2.0",
      id: "status",
      method: "tools/call",
      params: { name: "harness_bridge_status", arguments: {} },
    });
    assert.equal(JSON.parse(status.result.content[0].text).status, "ok");

    const unknownTool = await dispatch({
      jsonrpc: "2.0",
      id: 3,
      method: "tools/call",
      params: { name: "shell", arguments: { command: "whoami" } },
    });
    assert.equal(unknownTool.error.code, -32602);

    const resources = await dispatch({ jsonrpc: "2.0", id: 4, method: "resources/list", params: {} });
    assert.equal(resources.error.code, -32601);

    const extraToolParam = await dispatch({
      jsonrpc: "2.0",
      id: 5,
      method: "tools/call",
      params: { name: "harness_bridge_status", arguments: {}, rawBackend: "forbidden" },
    });
    assert.equal(extraToolParam.error.code, -32602);

    const unknownNotification = await dispatch({
      jsonrpc: "2.0",
      method: "notifications/cancelled",
      params: { requestId: 3, reason: "test" },
    });
    assert.equal(unknownNotification, undefined);
  });

  it("turns invoke validation failures into bounded MCP tool errors", async () => {
    const dispatch = createMcpDispatcher({
      status: () => ({}),
      capabilities: () => ({}),
      invoke: async () => {
        throw Object.assign(new Error("private detail"), {
          code: "capability_manifest_changed",
        });
      },
    });
    const response = await dispatch({
      jsonrpc: "2.0",
      id: 6,
      method: "tools/call",
      params: { name: "harness_invoke", arguments: {} },
    });
    assert.equal(response.result.isError, true);
    assert.deepEqual(JSON.parse(response.result.content[0].text), {
      ok: false,
      reasonCode: "capability_manifest_changed",
    });
  });

  it("frames stdio JSON-RPC, ignores notifications, and bounds input lines", async () => {
    const input = Readable.from([
      `${JSON.stringify({ jsonrpc: "2.0", id: 1, method: "ping" })}\n`,
      "{not-json}\n",
      `${"x".repeat(MCP_MAX_MESSAGE_BYTES + 1)}\n`,
      `${JSON.stringify({ jsonrpc: "2.0", method: "notifications/cancelled" })}\n`,
    ]);
    let outputText = "";
    const output = new Writable({
      write(chunk, _encoding, callback) {
        outputText += chunk.toString();
        callback();
      },
    });
    await runStdioMcpServer(
      {
        status: () => ({}),
        capabilities: () => ({}),
        invoke: async () => ({}),
      },
      input,
      output,
    );

    const messages = outputText.trim().split("\n").map((line) => JSON.parse(line));
    assert.equal(messages.length, 3);
    assert.deepEqual(messages[0].result, {});
    assert.equal(messages[1].error.code, -32700);
    assert.equal(messages[2].error.message, "Message too large");
  });
});
