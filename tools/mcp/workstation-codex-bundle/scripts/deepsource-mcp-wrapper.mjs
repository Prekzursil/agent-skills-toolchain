import { handleCliArgs, initializeServer, mcpServer } from 'deepsource-mcp-server';

const args = process.argv.slice(2);

if (handleCliArgs(args)) {
  process.exit(0);
}

await initializeServer();
await mcpServer.current.start();
