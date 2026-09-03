import { createInterface } from "node:readline";
import type { Readable, Writable } from "node:stream";

import { GATEWAY_NAME, GATEWAY_VERSION, RUNTIME_TOOLS } from "./manifest.ts";

const MCP_PROTOCOL_VERSION = "2025-06-18";
const MAX_MESSAGE_BYTES = 65_536;

type GatewayLike = {
  status(): unknown;
  capabilities(): unknown;
  invoke(input: unknown): Promise<unknown>;
};

type RpcRequest = {
  jsonrpc: "2.0";
  id?: string | number | null;
  method: string;
  params?: unknown;
};

function error(id: RpcRequest["id"], code: number, message: string) {
  return { jsonrpc: "2.0", id: id ?? null, error: { code, message } };
}

function result(id: RpcRequest["id"], value: unknown) {
  return { jsonrpc: "2.0", id: id ?? null, result: value };
}

function objectParams(params: unknown): Record<string, unknown> | undefined {
  if (params === undefined) return {};
  if (!params || typeof params !== "object" || Array.isArray(params)) return undefined;
  return params as Record<string, unknown>;
}

function emptyArguments(value: unknown): boolean {
  const args = objectParams(value);
  return Boolean(args && Object.keys(args).length === 0);
}

function toolResult(value: unknown, isError = false) {
  return {
    content: [{ type: "text", text: JSON.stringify(value) }],
    ...(isError ? { isError: true } : {}),
  };
}

export function createMcpDispatcher(service: GatewayLike) {
  return async function dispatch(request: RpcRequest): Promise<any> {
    if (!request || request.jsonrpc !== "2.0" || typeof request.method !== "string") {
      return error(request?.id, -32600, "Invalid Request");
    }
    if (request.id === undefined && request.method.startsWith("notifications/")) return undefined;
    if (request.method === "ping") return result(request.id, {});
    if (request.method === "initialize") {
      return result(request.id, {
        protocolVersion: MCP_PROTOCOL_VERSION,
        capabilities: { tools: { listChanged: false } },
        serverInfo: { name: GATEWAY_NAME, version: GATEWAY_VERSION },
      });
    }
    if (request.method === "tools/list") {
      if (!emptyArguments(request.params)) return error(request.id, -32602, "Invalid params");
      return result(request.id, { tools: RUNTIME_TOOLS });
    }
    if (request.method !== "tools/call") return error(request.id, -32601, "Method not found");

    const params = objectParams(request.params);
    if (
      !params ||
      typeof params.name !== "string" ||
      !("arguments" in params) ||
      Object.keys(params).length !== 2
    ) {
      return error(request.id, -32602, "Invalid params");
    }
    if (params.name === "harness_bridge_status") {
      if (!emptyArguments(params.arguments)) return error(request.id, -32602, "Invalid params");
      return result(request.id, toolResult(service.status()));
    }
    if (params.name === "harness_capabilities") {
      if (!emptyArguments(params.arguments)) return error(request.id, -32602, "Invalid params");
      return result(request.id, toolResult(service.capabilities()));
    }
    if (params.name === "harness_invoke") {
      try {
        return result(request.id, toolResult(await service.invoke(params.arguments)));
      } catch (caught) {
        const reasonCode =
          caught && typeof caught === "object" && "code" in caught
            ? String((caught as { code: unknown }).code)
            : "invalid_invoke";
        return result(request.id, toolResult({ ok: false, reasonCode }, true));
      }
    }
    return error(request.id, -32602, "Unknown tool");
  };
}

export async function runStdioMcpServer(
  service: GatewayLike,
  input: Readable = process.stdin,
  output: Writable = process.stdout,
): Promise<void> {
  const dispatch = createMcpDispatcher(service);
  const lines = createInterface({ input, crlfDelay: Infinity });
  for await (const line of lines) {
    let response: unknown;
    if (Buffer.byteLength(line, "utf8") > MAX_MESSAGE_BYTES) {
      response = error(null, -32600, "Message too large");
    } else {
      try {
        const request = JSON.parse(line) as RpcRequest;
        response = await dispatch(request);
      } catch {
        response = error(null, -32700, "Parse error");
      }
    }
    if (response !== undefined) output.write(`${JSON.stringify(response)}\n`);
  }
}

export const MCP_MAX_MESSAGE_BYTES = MAX_MESSAGE_BYTES;
export const MCP_VERSION = MCP_PROTOCOL_VERSION;
