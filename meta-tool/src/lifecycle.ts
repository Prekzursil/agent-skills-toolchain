/**
 * Server lifecycle manager — manages on-demand MCP server child processes.
 *
 * State machine per server: IDLE -> STARTING -> READY -> (keepalive 5min) -> STOPPING -> IDLE
 *
 * Features:
 * - On-demand startup via getClient()
 * - 5-minute idle keepalive timer
 * - Max 3 concurrent servers with LRU eviction
 * - Retry-once on startup failure
 */

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import {
  StdioClientTransport,
  getDefaultEnvironment,
} from "@modelcontextprotocol/sdk/client/stdio.js";

// --- Types ---

export interface ServerConfig {
  command: string;
  args?: string[];
  env?: Record<string, string>;
}

type ServerState = "IDLE" | "STARTING" | "READY" | "STOPPING";

interface ServerInstance {
  state: ServerState;
  client: Client | null;
  transport: StdioClientTransport | null;
  lastUsed: number;
  idleTimer: ReturnType<typeof setTimeout> | null;
  config: ServerConfig;
}

// --- Constants ---

const KEEPALIVE_MS = 5 * 60 * 1000; // 5 minutes
const MAX_CONCURRENT = 3;
const CONNECT_TIMEOUT_MS = 30_000; // 30 seconds

// --- Helpers ---

/**
 * Resolve `${VAR}` placeholders in environment values from process.env.
 */
function resolveEnvVars(env: Record<string, string>): Record<string, string> {
  const resolved: Record<string, string> = {};
  for (const [key, value] of Object.entries(env)) {
    resolved[key] = value.replace(/\$\{(\w+)\}/g, (_match, varName: string) => {
      return process.env[varName] ?? "";
    });
  }
  return resolved;
}

// --- LifecycleManager ---

export class LifecycleManager {
  private servers: Map<string, ServerInstance> = new Map();
  private maxConcurrent: number = MAX_CONCURRENT;

  /**
   * Get or start a client for the named server.
   * If the server is already running and READY, returns the existing client.
   * If not running, starts it (with LRU eviction if at capacity).
   */
  async getClient(serverName: string, config: ServerConfig): Promise<Client> {
    const existing = this.servers.get(serverName);

    if (existing && existing.state === "READY" && existing.client) {
      // Refresh LRU timestamp and reset idle timer
      existing.lastUsed = Date.now();
      this.resetIdleTimer(serverName);
      return existing.client;
    }

    // If currently starting, wait for it
    if (existing && existing.state === "STARTING") {
      return this.waitForReady(serverName);
    }

    // Evict if at capacity
    const readyCount = this.countReady();
    if (readyCount >= this.maxConcurrent) {
      await this.evictLRU();
    }

    // Start the server (retry once on failure)
    return this.startServer(serverName, config);
  }

  /**
   * Shutdown all managed servers. Call during process cleanup.
   */
  async shutdownAll(): Promise<void> {
    const shutdowns: Promise<void>[] = [];
    for (const serverName of this.servers.keys()) {
      shutdowns.push(this.shutdownServer(serverName));
    }
    await Promise.allSettled(shutdowns);
    this.servers.clear();
  }

  // --- Private methods ---

  private countReady(): number {
    let count = 0;
    for (const instance of this.servers.values()) {
      if (instance.state === "READY" || instance.state === "STARTING") {
        count++;
      }
    }
    return count;
  }

  private async startServer(
    serverName: string,
    config: ServerConfig,
    isRetry = false,
  ): Promise<Client> {
    const instance: ServerInstance = {
      state: "STARTING",
      client: null,
      transport: null,
      lastUsed: Date.now(),
      idleTimer: null,
      config,
    };
    this.servers.set(serverName, instance);

    try {
      const client = await this.connectToServer(serverName, config);
      instance.client = client;
      instance.state = "READY";
      instance.lastUsed = Date.now();
      this.resetIdleTimer(serverName);
      return client;
    } catch (err) {
      // On first failure, retry once
      if (!isRetry) {
        instance.state = "IDLE";
        instance.client = null;
        instance.transport = null;
        return this.startServer(serverName, config, true);
      }
      // Second failure — clean up and throw
      this.servers.delete(serverName);
      const message = err instanceof Error ? err.message : String(err);
      throw new Error(
        `Failed to start server "${serverName}" after retry: ${message}`,
      );
    }
  }

  private async connectToServer(
    serverName: string,
    config: ServerConfig,
  ): Promise<Client> {
    // Build environment: start with safe defaults, layer in catalog env vars
    const env: Record<string, string> = {
      ...getDefaultEnvironment(),
      ...(config.env ? resolveEnvVars(config.env) : {}),
    };

    const transport = new StdioClientTransport({
      command: config.command,
      args: config.args,
      env,
      stderr: "pipe",
    });

    const instance = this.servers.get(serverName);
    if (instance) {
      instance.transport = transport;
    }

    const client = new Client(
      { name: `meta-tool/${serverName}`, version: "0.1.0" },
      { capabilities: {} },
    );

    // Connect with a timeout
    const connectPromise = client.connect(transport);
    const timeoutPromise = new Promise<never>((_resolve, reject) => {
      setTimeout(
        () => reject(new Error(`Timeout connecting to "${serverName}" after ${CONNECT_TIMEOUT_MS}ms`)),
        CONNECT_TIMEOUT_MS,
      );
    });

    await Promise.race([connectPromise, timeoutPromise]);
    return client;
  }

  private async waitForReady(serverName: string): Promise<Client> {
    // Poll until the server transitions out of STARTING
    const deadline = Date.now() + CONNECT_TIMEOUT_MS;
    while (Date.now() < deadline) {
      const instance = this.servers.get(serverName);
      if (!instance) {
        throw new Error(`Server "${serverName}" disappeared while starting`);
      }
      if (instance.state === "READY" && instance.client) {
        instance.lastUsed = Date.now();
        this.resetIdleTimer(serverName);
        return instance.client;
      }
      if (instance.state === "IDLE") {
        throw new Error(`Server "${serverName}" failed to start`);
      }
      // Brief wait before re-checking
      await new Promise((resolve) => setTimeout(resolve, 200));
    }
    throw new Error(`Timeout waiting for server "${serverName}" to become ready`);
  }

  private resetIdleTimer(serverName: string): void {
    const instance = this.servers.get(serverName);
    if (!instance) return;

    if (instance.idleTimer) {
      clearTimeout(instance.idleTimer);
    }

    instance.idleTimer = setTimeout(() => {
      this.shutdownServer(serverName).catch(() => {
        // Swallow shutdown errors on idle cleanup
      });
    }, KEEPALIVE_MS);
  }

  /**
   * Evict the least-recently-used READY server to make room for a new one.
   */
  private async evictLRU(): Promise<void> {
    let oldestName: string | null = null;
    let oldestTime = Infinity;

    for (const [name, instance] of this.servers.entries()) {
      if (instance.state === "READY" && instance.lastUsed < oldestTime) {
        oldestTime = instance.lastUsed;
        oldestName = name;
      }
    }

    if (oldestName) {
      await this.shutdownServer(oldestName);
    }
  }

  private async shutdownServer(serverName: string): Promise<void> {
    const instance = this.servers.get(serverName);
    if (!instance) return;

    if (instance.state === "STOPPING" || instance.state === "IDLE") return;

    instance.state = "STOPPING";

    if (instance.idleTimer) {
      clearTimeout(instance.idleTimer);
      instance.idleTimer = null;
    }

    try {
      if (instance.client) {
        await instance.client.close();
      }
    } catch {
      // Best-effort close
    }

    try {
      if (instance.transport) {
        await instance.transport.close();
      }
    } catch {
      // Best-effort close
    }

    instance.client = null;
    instance.transport = null;
    instance.state = "IDLE";
    this.servers.delete(serverName);
  }
}
