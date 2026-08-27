import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { readFileSync } from "fs";
import { parse } from "yaml";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import { LifecycleManager } from "./lifecycle.js";
import { transformResult } from "./transformer.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

// --- Types ---

interface ToolParam {
  name: string;
  type: string;
  required: boolean;
  description?: string;
}

interface ToolDef {
  id: string;
  name: string;
  keywords: string[];
  category: string;
  description: string;
  params: ToolParam[];
  result_size: string;
}

interface ServerDef {
  display_name: string;
  description: string;
  transport: string;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  plugin_id?: string;
  categories: string[];
  tools: ToolDef[];
}

interface Catalog {
  version: number;
  generated: string;
  servers: Record<string, ServerDef>;
}

// --- Load catalog ---

const catalogPath = join(__dirname, "..", "catalog.yaml");
const catalog: Catalog = parse(readFileSync(catalogPath, "utf-8"));

// --- Build search index ---

interface IndexEntry {
  server: string;
  tool: ToolDef;
  searchText: string;
}

const index: IndexEntry[] = [];
for (const [serverName, server] of Object.entries(catalog.servers)) {
  for (const tool of server.tools) {
    const searchText = [
      tool.name,
      tool.description,
      ...tool.keywords,
      tool.category,
      serverName,
      server.display_name,
    ]
      .join(" ")
      .toLowerCase();
    index.push({ server: serverName, tool, searchText });
  }
}

function searchIndex(
  query: string,
  category?: string,
  server?: string,
  limit = 10,
): IndexEntry[] {
  const terms = query.toLowerCase().split(/\s+/);
  let results = index;

  if (server) {
    results = results.filter((e) => e.server === server);
  }
  if (category) {
    results = results.filter((e) => e.tool.category === category);
  }

  // Score by term match count
  const scored = results.map((entry) => {
    let score = 0;
    for (const term of terms) {
      if (entry.searchText.includes(term)) score++;
      // Bonus for exact keyword match
      if (entry.tool.keywords.some((k) => k === term)) score += 2;
    }
    return { entry, score };
  });

  return scored
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map((s) => s.entry);
}

// --- Lifecycle manager for child MCP servers ---

const lifecycleManager = new LifecycleManager();

// --- Create MCP server ---

const server = new McpServer({
  name: "meta-tool",
  version: "0.1.0",
});

// Tool 1: search_capabilities
server.tool(
  "search_capabilities",
  "Search the tool catalog across all wrapped MCP servers. Returns matching tools with server, category, and description. Use natural language or keywords to find the right tool for a task.",
  {
    query: z.string().describe("Natural language query or keywords"),
    category: z.string().optional().describe("Optional category filter (e.g. code_quality, issues, pull_requests, security, coverage)"),
    server: z.string().optional().describe("Optional server filter (codacy, sonarqube, github, linear, sentry, notion)"),
    limit: z.number().optional().describe("Max results (default 10)"),
  },
  async (args) => {
    const results = searchIndex(
      args.query as string,
      args.category as string | undefined,
      args.server as string | undefined,
      (args.limit as number) || 10,
    );

    return {
      content: [
        {
          type: "text" as const,
          text: JSON.stringify(
            {
              results: results.map((r) => ({
                server: r.server,
                tool_id: r.tool.id,
                name: r.tool.name,
                category: r.tool.category,
                description: r.tool.description,
              })),
              total_matches: results.length,
              hint: "Use describe_tool(server, tool_id) for full parameter schema",
            },
            null,
            2,
          ),
        },
      ],
    };
  },
);

// Tool 2: describe_tool
server.tool(
  "describe_tool",
  "Get the full parameter schema and usage details for a specific tool. Use after search_capabilities to get the information needed to call a tool.",
  {
    server: z.string().describe("Server name from search results"),
    tool_id: z.string().describe("Tool ID from search results"),
  },
  async (args) => {
    const serverName = args.server as string;
    const toolId = args.tool_id as string;
    const serverDef = catalog.servers[serverName];

    if (!serverDef) {
      return {
        content: [
          {
            type: "text" as const,
            text: `Server "${serverName}" not found. Available: ${Object.keys(catalog.servers).join(", ")}`,
          },
        ],
      };
    }

    const tool = serverDef.tools.find((t) => t.id === toolId);
    if (!tool) {
      return {
        content: [
          {
            type: "text" as const,
            text: `Tool "${toolId}" not found in ${serverName}. Available: ${serverDef.tools.map((t) => t.id).join(", ")}`,
          },
        ],
      };
    }

    return {
      content: [
        {
          type: "text" as const,
          text: JSON.stringify(
            {
              server: serverName,
              server_display_name: serverDef.display_name,
              transport: serverDef.transport,
              tool_id: tool.id,
              name: tool.name,
              description: tool.description,
              parameters: tool.params,
              result_size: tool.result_size,
              example: `execute_tool(server="${serverName}", tool_id="${tool.id}", params={${tool.params
                .filter((p) => p.required)
                .map((p) => `${p.name}: "..."`)
                .join(", ")}})`,
            },
            null,
            2,
          ),
        },
      ],
    };
  },
);

// Tool 3: execute_tool
server.tool(
  "execute_tool",
  "Execute a tool on a wrapped MCP server. Stdio servers start on-demand with 5-min keepalive. Plugin servers return delegation hints. Results are filtered to stay within token budget.",
  {
    server: z.string().describe("Server name"),
    tool_id: z.string().describe("Tool ID"),
    params: z.record(z.string(), z.any()).describe("Tool parameters as key-value pairs"),
    max_tokens: z.number().optional().describe("Max tokens for result (default 2000)"),
  },
  async (args) => {
    const serverName = args.server as string;
    const toolId = args.tool_id as string;
    const maxTokens = (args.max_tokens as number | undefined) ?? 2000;
    const serverDef = catalog.servers[serverName];

    if (!serverDef) {
      return {
        content: [
          {
            type: "text" as const,
            text: `Server "${serverName}" not found. Available: ${Object.keys(catalog.servers).join(", ")}`,
          },
        ],
      };
    }

    const tool = serverDef.tools.find((t) => t.id === toolId);
    if (!tool) {
      return {
        content: [
          {
            type: "text" as const,
            text: `Tool "${toolId}" not found in ${serverName}. Available: ${serverDef.tools.map((t) => t.id).join(", ")}`,
          },
        ],
      };
    }

    // For plugin-backed servers, return delegation instruction
    if (serverDef.transport === "plugin") {
      return {
        content: [
          {
            type: "text" as const,
            text: JSON.stringify(
              {
                status: "delegate",
                message:
                  "This server is managed by a Claude plugin. Use ToolSearch to load and call the plugin tool directly.",
                plugin_id: serverDef.plugin_id,
                suggested_tool_prefix: `mcp__${serverDef.plugin_id?.replace(/:/g, "_")}__`,
                tool_hint: toolId,
                params: args.params,
              },
              null,
              2,
            ),
          },
        ],
      };
    }

    // For stdio servers, use the lifecycle manager
    if (serverDef.transport === "stdio") {
      if (!serverDef.command) {
        return {
          content: [
            {
              type: "text" as const,
              text: JSON.stringify(
                {
                  status: "error",
                  message: `Server "${serverName}" is stdio transport but has no command configured.`,
                },
                null,
                2,
              ),
            },
          ],
        };
      }

      try {
        const client = await lifecycleManager.getClient(serverName, {
          command: serverDef.command,
          args: serverDef.args,
          env: serverDef.env,
        });

        const result = await client.callTool({
          name: toolId,
          arguments: args.params as Record<string, string>,
        });

        // Extract the text content from the MCP result
        const rawContent = result.content;
        const transformed = transformResult(rawContent, maxTokens);

        return {
          content: [
            {
              type: "text" as const,
              text: transformed,
            },
          ],
        };
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        return {
          content: [
            {
              type: "text" as const,
              text: JSON.stringify(
                {
                  status: "error",
                  server: serverName,
                  tool_id: toolId,
                  message,
                },
                null,
                2,
              ),
            },
          ],
        };
      }
    }

    // For http servers, use fetch
    if (serverDef.transport === "http") {
      return {
        content: [
          {
            type: "text" as const,
            text: JSON.stringify(
              {
                status: "not_implemented",
                message:
                  "HTTP transport is not yet implemented. Configure the server as stdio or plugin instead.",
                server: serverName,
                tool_id: toolId,
                transport: serverDef.transport,
              },
              null,
              2,
            ),
          },
        ],
      };
    }

    // Unknown transport
    return {
      content: [
        {
          type: "text" as const,
          text: JSON.stringify(
            {
              status: "error",
              message: `Unknown transport "${serverDef.transport}" for server "${serverName}".`,
            },
            null,
            2,
          ),
        },
      ],
    };
  },
);

// --- Start server ---

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

// Cleanup child servers on exit
function cleanup() {
  lifecycleManager.shutdownAll().catch(() => {});
}
process.on("SIGINT", cleanup);
process.on("SIGTERM", cleanup);
process.on("exit", cleanup);

main().catch(console.error);
