// Wires the seven tools onto a low-level MCP Server over any transport. The
// low-level Server does NOT validate call arguments against the advertised
// inputSchema, so the hardened per-tool validation (and its structured
// query_invalid errors) run for every call.

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  type CallToolResult,
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { buildFailure, toolError } from "./errors.js";
import { createTools, type ToolDeps } from "./tools.js";

export const SERVER_NAME = "hacktricks-mcp-hardened";
export const SERVER_VERSION = "1.3.4-hardened.1";

export function createServer(deps: ToolDeps): Server {
  const { handlers, defs } = createTools(deps);
  const server = new Server(
    { name: SERVER_NAME, version: SERVER_VERSION },
    { capabilities: { tools: {} } },
  );
  server.setRequestHandler(ListToolsRequestSchema, () => ({ tools: defs }));
  server.setRequestHandler(
    CallToolRequestSchema,
    (request): Promise<CallToolResult> => {
      const name = request.params.name;
      const handler = handlers[name];
      if (handler === undefined) {
        return Promise.resolve(
          toolError(
            buildFailure(
              name,
              deps.newId(),
              0,
              "query_invalid",
              "unknown tool",
              "unknown_tool",
              false,
              1,
            ),
          ),
        );
      }
      const args = request.params.arguments;
      const safeArgs =
        typeof args === "object" && args !== null
          ? (args as Record<string, unknown>)
          : {};
      return handler(safeArgs);
    },
  );
  return server;
}
