import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { allTools } from "./tools.js";
function createMcpServer(ctx) {
    const server = new McpServer({
        name: "darknet-mcp",
        version: "0.1.0",
    });
    for (const tool of allTools) {
        server.tool(tool.name, tool.description, tool.schema, async (args) => {
            try {
                const result = await tool.execute(args, ctx);
                return result;
            }
            catch (err) {
                return {
                    content: [{ type: "text", text: `Error: ${err.message}` }],
                    isError: true,
                };
            }
        });
    }
    return server;
}
export async function startMcpStdio(ctx) {
    const server = createMcpServer(ctx);
    const transport = new StdioServerTransport();
    await server.connect(transport);
    console.error("[darknet-mcp] MCP server started on stdio");
    return server;
}
//# sourceMappingURL=mcp-server.js.map