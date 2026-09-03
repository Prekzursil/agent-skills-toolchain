#!/usr/bin/env node
import { once } from "node:events";

import { NdjsonAuditSink } from "./audit-file.ts";
import { decodeHmacKey } from "./auth.ts";
import { isDirectEntrypoint } from "./entrypoint.ts";
import { createHttpHub } from "./http-hub.ts";
import { verifyInventoryPins } from "./manifest.ts";
import { runStdioMcpServer } from "./mcp-server.ts";
import { executeCapability } from "./backend-executor.ts";
import { GatewayService } from "./service.ts";

function configuredPort(value: string | undefined): number {
  if (!value) throw new Error("harness_url_required");
  const url = new URL(value);
  if (
    url.protocol !== "http:" ||
    url.hostname !== "127.0.0.1" ||
    !url.port ||
    url.pathname !== "/" ||
    url.search ||
    url.hash ||
    url.username ||
    url.password
  ) {
    throw new Error("harness_url_must_be_fixed_loopback_http");
  }
  const port = Number(url.port);
  if (!Number.isSafeInteger(port) || port < 1024 || port > 65_535) throw new Error("invalid_harness_port");
  return port;
}

export async function main(environment: NodeJS.ProcessEnv = process.env): Promise<void> {
  const inventoryMismatches = verifyInventoryPins();
  if (inventoryMismatches.length > 0) throw new Error("capability_inventory_drift");
  const port = configuredPort(environment.CYBERSTRIKE_HARNESS_URL);
  const key = decodeHmacKey(environment.CYBERSTRIKE_HARNESS_HMAC_KEY_B64 ?? "");
  const auditPath = environment.CYBERSTRIKE_HARNESS_AUDIT_PATH;
  if (!auditPath) throw new Error("audit_path_required");
  const service = new GatewayService({
    auditSink: new NdjsonAuditSink(auditPath),
    executor: executeCapability,
  });
  const hub = createHttpHub({ key, service });
  try {
    hub.listen(port, "127.0.0.1");
    await once(hub, "listening");
    await runStdioMcpServer(service);
  } finally {
    if (hub.listening) {
      hub.close();
      await once(hub, "close");
    }
  }
}

if (isDirectEntrypoint(import.meta.url, process.argv[1])) {
  main().catch(() => {
    process.stderr.write("cyberstrike-gateway: startup_failed\n");
    process.exitCode = 1;
  });
}
