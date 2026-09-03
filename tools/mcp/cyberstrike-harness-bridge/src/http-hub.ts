import { randomUUID } from "node:crypto";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";

import {
  AuthenticationError,
  NonceReplayCache,
  authenticateRequest,
} from "./auth.ts";
import { GATEWAY_VERSION, PROTOCOL } from "./manifest.ts";

const MAX_REQUEST_BYTES = 65_536;
const MAX_RESPONSE_BYTES = 262_144;
const JSON_CONTENT_TYPE = /^application\/json(?:\s*;\s*charset=utf-8)?$/i;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const HOOK_NAMES = new Set([
  "event",
  "config",
  "tool",
  "auth",
  "chat.message",
  "chat.params",
  "chat.headers",
  "permission.ask",
  "command.execute.before",
  "tool.execute.before",
  "shell.env",
  "tool.execute.after",
  "experimental.chat.messages.transform",
  "experimental.chat.system.transform",
  "experimental.session.compacting",
  "experimental.text.complete",
  "tool.definition",
]);

type GatewayLike = {
  status(): unknown;
  capabilities(): unknown;
  invoke(input: unknown): Promise<unknown>;
};

type HttpEnvelope = {
  protocol: string;
  requestId: string;
  timestamp: string;
  correlationId: string;
  origin: "cyberstrike-plugin" | "harness-reverse";
  hopCount: number;
  input: unknown;
};

function header(request: IncomingMessage, name: string): string | undefined {
  const value = request.headers[name.toLowerCase()];
  return typeof value === "string" ? value : undefined;
}

function respond(response: ServerResponse, status: number, body: unknown): void {
  let serialized = JSON.stringify(body);
  if (Buffer.byteLength(serialized, "utf8") > MAX_RESPONSE_BYTES) {
    status = 507;
    serialized = JSON.stringify({ protocol: PROTOCOL, ok: false, reasonCode: "response_too_large" });
  }
  response.statusCode = status;
  response.setHeader("Content-Type", "application/json; charset=utf-8");
  response.setHeader("Content-Length", Buffer.byteLength(serialized, "utf8"));
  response.setHeader("Cache-Control", "no-store");
  response.end(serialized);
}

function rejectForwardingHeaders(request: IncomingMessage): boolean {
  return Object.keys(request.headers).some(
    (name) => name === "forwarded" || name.startsWith("x-forwarded-"),
  );
}

function expectedHost(request: IncomingMessage): string | undefined {
  const address = request.socket.localAddress;
  const port = request.socket.localPort;
  if (address !== "127.0.0.1" || !port) return undefined;
  return `127.0.0.1:${port}`;
}

async function readBody(request: IncomingMessage): Promise<Buffer> {
  const chunks: Buffer[] = [];
  let total = 0;
  for await (const chunk of request) {
    const bytes = Buffer.from(chunk);
    total += bytes.length;
    if (total > MAX_REQUEST_BYTES) throw new Error("body_too_large");
    chunks.push(bytes);
  }
  return Buffer.concat(chunks);
}

function validateEnvelope(value: unknown): HttpEnvelope {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid_envelope");
  const record = value as Record<string, unknown>;
  const keys = Object.keys(record).sort();
  const expected = ["correlationId", "hopCount", "input", "origin", "protocol", "requestId", "timestamp"];
  if (keys.length !== expected.length || keys.some((key, index) => key !== expected[index])) {
    throw new Error("invalid_envelope");
  }
  if (record.protocol !== PROTOCOL) throw new Error("invalid_protocol");
  if (typeof record.requestId !== "string" || !UUID.test(record.requestId)) throw new Error("invalid_request_id");
  if (typeof record.correlationId !== "string" || !UUID.test(record.correlationId)) throw new Error("invalid_correlation_id");
  if (record.origin !== "cyberstrike-plugin" && record.origin !== "harness-reverse") throw new Error("invalid_origin");
  if (record.hopCount !== 0 && record.hopCount !== 1) throw new Error("invalid_hop_count");
  if (record.origin === "cyberstrike-plugin" && record.hopCount !== 0) throw new Error("invalid_hop_count");
  if (record.origin === "harness-reverse" && record.hopCount !== 1) throw new Error("invalid_hop_count");
  if (typeof record.timestamp !== "string") throw new Error("invalid_envelope_timestamp");
  const timestamp = Date.parse(record.timestamp);
  if (!Number.isFinite(timestamp) || Math.abs(timestamp - Date.now()) > 30_000) throw new Error("invalid_envelope_timestamp");
  return record as HttpEnvelope;
}

function responseEnvelope(envelope: HttpEnvelope, result: unknown) {
  return {
    protocol: PROTOCOL,
    requestId: envelope.requestId,
    timestamp: new Date().toISOString(),
    correlationId: envelope.correlationId,
    origin: envelope.origin,
    hopCount: envelope.hopCount,
    result,
  };
}

function unavailableEnvelope(reasonCode = "gateway_capability_unimplemented") {
  return {
    protocol: PROTOCOL,
    requestId: randomUUID(),
    timestamp: new Date().toISOString(),
    correlationId: randomUUID(),
    origin: "cyberstrike-plugin",
    hopCount: 0,
    ok: false,
    reasonCode,
  };
}

export function createHttpHub(options: {
  key: Buffer;
  service: GatewayLike;
  replayCache?: NonceReplayCache;
}) {
  if (options.key.length !== 32) throw new Error("invalid_hmac_key_length");
  const replayCache = options.replayCache ?? new NonceReplayCache();
  const server = createServer(async (request, response) => {
    try {
      const remote = request.socket.remoteAddress;
      if (remote !== "127.0.0.1" && remote !== "::ffff:127.0.0.1") {
        respond(response, 403, { error: "loopback_required" });
        return;
      }
      const host = header(request, "host");
      if (!host || host !== expectedHost(request)) {
        respond(response, 403, { error: "invalid_host" });
        return;
      }
      if (request.headers.origin !== undefined || rejectForwardingHeaders(request)) {
        respond(response, 403, { error: "proxy_headers_forbidden" });
        return;
      }
      if (!request.url || request.url.includes("?")) {
        respond(response, 400, { error: "query_string_forbidden" });
        return;
      }

      const method = (request.method ?? "").toUpperCase();
      const pathname = request.url;
      const isGet = method === "GET";
      const isPost = method === "POST";
      if (!isGet && !isPost) {
        respond(response, 405, { error: "method_not_allowed" });
        return;
      }
      if (request.headers["transfer-encoding"] !== undefined) {
        respond(response, 411, { error: "chunked_body_forbidden" });
        request.resume();
        return;
      }

      let body = Buffer.alloc(0);
      if (isGet) {
        if (Number(header(request, "content-length") ?? "0") !== 0) {
          respond(response, 400, { error: "get_body_forbidden" });
          request.resume();
          return;
        }
      } else {
        const contentLengthValue = header(request, "content-length");
        if (!contentLengthValue || !/^(0|[1-9][0-9]{0,5})$/.test(contentLengthValue)) {
          respond(response, 411, { error: "content_length_required" });
          request.resume();
          return;
        }
        const contentLength = Number(contentLengthValue);
        if (contentLength > MAX_REQUEST_BYTES) {
          respond(response, 413, { error: "body_too_large" });
          request.resume();
          return;
        }
        if (!JSON_CONTENT_TYPE.test(header(request, "content-type") ?? "")) {
          respond(response, 415, { error: "json_required" });
          request.resume();
          return;
        }
        body = await readBody(request);
        if (body.length !== contentLength) {
          respond(response, 400, { error: "content_length_mismatch" });
          return;
        }
      }

      authenticateRequest({
        key: options.key,
        replayCache,
        method,
        pathname,
        body,
        timestamp: header(request, "x-ast-timestamp") ?? "",
        nonce: header(request, "x-ast-nonce") ?? "",
        bodySha256: header(request, "x-ast-body-sha256") ?? "",
        signature: header(request, "x-ast-signature") ?? "",
      });

      if (method === "GET" && pathname === "/health") {
        respond(response, 200, options.service.status());
        return;
      }
      if (method === "GET" && pathname === "/v1/capabilities") {
        respond(response, 200, options.service.capabilities());
        return;
      }
      if (method === "GET" && pathname === "/v1/scope") {
        respond(response, 503, unavailableEnvelope());
        return;
      }
      if (method === "POST" && pathname === "/v1/invoke") {
        let parsed: unknown;
        try {
          parsed = JSON.parse(body.toString("utf8"));
        } catch {
          respond(response, 400, { error: "invalid_json" });
          return;
        }
        const envelope = validateEnvelope(parsed);
        const result = await options.service.invoke(envelope.input);
        respond(response, 200, responseEnvelope(envelope, result));
        return;
      }
      if (method === "POST" && pathname === "/v1/skills/authorize") {
        respond(response, 503, unavailableEnvelope());
        return;
      }
      if (method === "POST" && pathname.startsWith("/v1/hooks/")) {
        const hookName = pathname.slice("/v1/hooks/".length);
        respond(response, HOOK_NAMES.has(hookName) ? 503 : 404, unavailableEnvelope());
        return;
      }
      respond(response, 404, { error: "route_not_found" });
    } catch (error) {
      if (error instanceof AuthenticationError) {
        respond(response, 401, { error: "authentication_failed" });
      } else if (error instanceof Error && error.message === "body_too_large") {
        respond(response, 413, { error: "body_too_large" });
      } else if (error instanceof Error && error.message.startsWith("invalid_")) {
        respond(response, 400, { error: error.message });
      } else {
        respond(response, 500, { error: "internal_error" });
      }
    }
  });

  server.on("listening", () => {
    const address = server.address();
    if (!address || typeof address === "string" || address.address !== "127.0.0.1") {
      server.close();
      server.emit("error", new Error("hub_must_bind_127_0_0_1"));
    }
  });
  return server;
}

export const HTTP_HOOK_NAMES = Object.freeze([...HOOK_NAMES].sort());
export const HTTP_REQUEST_MAX_BYTES = MAX_REQUEST_BYTES;
export const HTTP_RESPONSE_MAX_BYTES = MAX_RESPONSE_BYTES;
// Compatibility alias for callers that historically treated this as the request ceiling.
export const HTTP_MAX_BYTES = MAX_REQUEST_BYTES;
export const HTTP_PROTOCOL_VERSION = GATEWAY_VERSION;
