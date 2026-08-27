
import { Client } from "./node_modules/@modelcontextprotocol/sdk/dist/esm/client/index.js";
import { StdioClientTransport } from "./node_modules/@modelcontextprotocol/sdk/dist/esm/client/stdio.js";

const label = process.argv[2];
const command = process.argv[3];
const args = JSON.parse(process.argv[4]);

const transport = new StdioClientTransport({ command, args, env: process.env });
const client = new Client({ name: "probe", version: "0.0.1" }, { capabilities: {} });
try {
  await client.connect(transport);
  const tools = await client.listTools();
  console.log(JSON.stringify({ label, ok: true, toolCount: tools.tools.length, toolNames: tools.tools.map(t => t.name) }, null, 2));
} catch (error) {
  console.log(JSON.stringify({ label, ok: false, error: String(error?.stack || error) }, null, 2));
} finally {
  try { await transport.close(); } catch {}
}
