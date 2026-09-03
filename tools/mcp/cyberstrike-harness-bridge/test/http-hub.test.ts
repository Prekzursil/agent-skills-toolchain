import assert from "node:assert/strict";
import { request } from "node:http";
import { once } from "node:events";
import { describe, it } from "node:test";

import { signRequest } from "../src/auth.ts";
import { createHttpHub } from "../src/http-hub.ts";
import { buildCapabilityManifest } from "../src/manifest.ts";

const key = Buffer.alloc(32, 0x33);

async function call(
  port: number,
  options: {
    method?: string;
    path?: string;
    body?: Buffer;
    headers?: Record<string, string | number>;
    signed?: boolean;
  } = {},
) {
  const method = options.method ?? "GET";
  const path = options.path ?? "/health";
  const body = options.body ?? Buffer.alloc(0);
  const headers: Record<string, string | number> = { ...(options.headers ?? {}) };
  if (options.signed ?? true) {
    const signed = signRequest(key, {
      method,
      pathname: path.split("?", 1)[0],
      body,
      timestamp: Math.floor(Date.now() / 1000),
    });
    headers["X-AST-Timestamp"] = signed.timestamp;
    headers["X-AST-Nonce"] = signed.nonce;
    headers["X-AST-Body-SHA256"] = signed.bodySha256;
    headers["X-AST-Signature"] = signed.signature;
  }
  if (
    !("Content-Length" in headers) &&
    !("Transfer-Encoding" in headers) &&
    method === "POST"
  ) {
    headers["Content-Length"] = body.length;
  }

  return await new Promise<{ status: number; headers: Record<string, unknown>; body: string }>(
    (resolve, reject) => {
      const req = request(
        { host: "127.0.0.1", port, method, path, headers },
        (response) => {
          const chunks: Buffer[] = [];
          response.on("data", (chunk) => chunks.push(Buffer.from(chunk)));
          response.on("end", () =>
            resolve({
              status: response.statusCode ?? 0,
              headers: response.headers,
              body: Buffer.concat(chunks).toString("utf8"),
            }),
          );
        },
      );
      req.on("error", reject);
      req.end(body);
    },
  );
}

describe("authenticated loopback HTTP hub", () => {
  it("serves only authenticated bounded routes and emits no CORS", async () => {
    const server = createHttpHub({
      key,
      service: {
        status: () => ({ protocol: "ast.cyberstrike.bridge/v1", status: "ok", version: "0.1.0" }),
        capabilities: () => buildCapabilityManifest(),
        invoke: async () => ({ ok: false, reasonCode: "test_denied" }),
      },
    });
    server.listen(0, "127.0.0.1");
    await once(server, "listening");
    const address = server.address();
    assert.ok(address && typeof address === "object");
    const port = address.port;

    try {
      const health = await call(port);
      assert.equal(health.status, 200);
      assert.deepEqual(JSON.parse(health.body), {
        protocol: "ast.cyberstrike.bridge/v1",
        status: "ok",
        version: "0.1.0",
      });
      assert.equal(health.headers["access-control-allow-origin"], undefined);

      const capabilities = await call(port, { path: "/v1/capabilities" });
      assert.equal(capabilities.status, 200);
      assert.equal(JSON.parse(capabilities.body).capabilities.length, 181);

      assert.equal((await call(port, { signed: false })).status, 401);
      const replaySignature = signRequest(key, {
        method: "GET",
        pathname: "/health",
        body: Buffer.alloc(0),
      });
      const replayHeaders = {
        "X-AST-Timestamp": replaySignature.timestamp,
        "X-AST-Nonce": replaySignature.nonce,
        "X-AST-Body-SHA256": replaySignature.bodySha256,
        "X-AST-Signature": replaySignature.signature,
      };
      assert.equal(
        (await call(port, { signed: false, headers: replayHeaders })).status,
        200,
      );
      assert.equal(
        (await call(port, { signed: false, headers: replayHeaders })).status,
        401,
      );
      assert.equal((await call(port, { path: "/health?leak=1" })).status, 400);
      assert.equal((await call(port, { headers: { Origin: "http://127.0.0.1" } })).status, 403);
      assert.equal((await call(port, { headers: { Forwarded: "for=127.0.0.1" } })).status, 403);
      assert.equal((await call(port, { headers: { "X-Forwarded-Host": "evil.test" } })).status, 403);
      assert.equal((await call(port, { headers: { Host: "evil.test" } })).status, 403);
      assert.equal((await call(port, { method: "DELETE" })).status, 405);

      const nonJson = await call(port, {
        method: "POST",
        path: "/v1/invoke",
        body: Buffer.from("{}"),
        headers: { "Content-Type": "text/plain" },
      });
      assert.equal(nonJson.status, 415);

      const oversized = await call(port, {
        method: "POST",
        path: "/v1/invoke",
        body: Buffer.alloc(65_537, 0x61),
        headers: { "Content-Type": "application/json" },
      });
      assert.equal(oversized.status, 413);

      const chunked = await call(port, {
        method: "POST",
        path: "/v1/invoke",
        body: Buffer.from("{}"),
        headers: {
          "Content-Type": "application/json",
          "Transfer-Encoding": "chunked",
        },
      });
      assert.equal(chunked.status, 411);

      const malformed = await call(port, {
        method: "POST",
        path: "/v1/invoke",
        body: Buffer.from("{not-json}"),
        headers: { "Content-Type": "application/json" },
      });
      assert.equal(malformed.status, 400);

      const staleEnvelope = await call(port, {
        method: "POST",
        path: "/v1/invoke",
        body: Buffer.from(
          JSON.stringify({
            protocol: "ast.cyberstrike.bridge/v1",
            requestId: "f6ca33c0-f416-4198-9717-44ad023fab4a",
            timestamp: "2000-01-01T00:00:00.000Z",
            correlationId: "7cb5ea16-2c6c-4295-bf78-6e91eb0ba798",
            origin: "cyberstrike-plugin",
            hopCount: 0,
            input: {},
          }),
        ),
        headers: { "Content-Type": "application/json" },
      });
      assert.equal(staleEnvelope.status, 400);

      const validInvoke = await call(port, {
        method: "POST",
        path: "/v1/invoke",
        body: Buffer.from(
          JSON.stringify({
            protocol: "ast.cyberstrike.bridge/v1",
            requestId: "f6ca33c0-f416-4198-9717-44ad023fab4a",
            timestamp: new Date().toISOString(),
            correlationId: "7cb5ea16-2c6c-4295-bf78-6e91eb0ba798",
            origin: "cyberstrike-plugin",
            hopCount: 0,
            input: {},
          }),
        ),
        headers: { "Content-Type": "application/json; charset=utf-8" },
      });
      assert.equal(validInvoke.status, 200);
      assert.deepEqual(JSON.parse(validInvoke.body).result, { ok: false, reasonCode: "test_denied" });

      assert.equal((await call(port, { path: "/v1/scope" })).status, 503);
      assert.equal(
        (
          await call(port, {
            method: "POST",
            path: "/v1/hooks/tool.execute.before",
            body: Buffer.from("{}"),
            headers: { "Content-Type": "application/json" },
          })
        ).status,
        503,
      );
      assert.equal(
        (
          await call(port, {
            method: "POST",
            path: "/v1/hooks/arbitrary.shell",
            body: Buffer.from("{}"),
            headers: { "Content-Type": "application/json" },
          })
        ).status,
        404,
      );
      assert.equal((await call(port, { path: "/v1/raw-backend" })).status, 404);
    } finally {
      server.close();
      await once(server, "close");
    }
  });
});
