import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  AuthenticationError,
  NonceReplayCache,
  authenticateRequest,
  decodeHmacKey,
  signRequest,
} from "../src/auth.ts";

const key = Buffer.alloc(32, 0x5a);
const nowSeconds = 1_800_000_000;

function validRequest(overrides: Record<string, unknown> = {}) {
  const base = {
    method: "POST",
    pathname: "/v1/invoke",
    body: Buffer.from('{"ok":true}', "utf8"),
    timestamp: nowSeconds,
    nonceBytes: Buffer.alloc(32, 0x11),
  };
  return signRequest(key, { ...base, ...overrides });
}

describe("HMAC request authentication", () => {
  it("accepts one canonical request and rejects the accepted nonce on replay", () => {
    const cache = new NonceReplayCache({ ttlSeconds: 60, maxEntries: 128 });
    const request = validRequest();
    assert.doesNotThrow(() =>
      authenticateRequest({ ...request, key, nowSeconds, replayCache: cache }),
    );
    assert.throws(
      () => authenticateRequest({ ...request, key, nowSeconds, replayCache: cache }),
      (error: unknown) => error instanceof AuthenticationError && error.code === "replayed_nonce",
    );
  });

  it("rejects stale timestamps, body tampering, malformed nonces, and bad signatures", () => {
    const cases = [
      { request: validRequest({ timestamp: nowSeconds - 31 }), code: "timestamp_out_of_range" },
      { request: { ...validRequest(), body: Buffer.from("tampered") }, code: "body_digest_mismatch" },
      { request: { ...validRequest(), nonce: "not-base64url" }, code: "invalid_nonce" },
      { request: { ...validRequest(), signature: "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" }, code: "invalid_signature" },
    ];

    for (const testCase of cases) {
      assert.throws(
        () =>
          authenticateRequest({
            ...testCase.request,
            key,
            nowSeconds,
            replayCache: new NonceReplayCache(),
          }),
        (error: unknown) => error instanceof AuthenticationError && error.code === testCase.code,
        testCase.code,
      );
    }
  });

  it("requires a canonical base64 key decoding to exactly 32 bytes", () => {
    assert.deepEqual(decodeHmacKey(key.toString("base64")), key);
    for (const invalid of ["", Buffer.alloc(31).toString("base64"), "%%%", `${key.toString("base64")}=`]) {
      assert.throws(() => decodeHmacKey(invalid), /32-byte canonical base64/);
    }
  });

  it("fails closed at capacity without evicting an unexpired nonce under large input", () => {
    const cache = new NonceReplayCache({ ttlSeconds: 60, maxEntries: 64 });
    const first = Buffer.alloc(32, 0).toString("base64url");
    let capacityRejects = 0;
    for (let index = 0; index < 10_001; index += 1) {
      const nonce = Buffer.alloc(32, index & 0xff);
      nonce.writeUInt32BE(index, 28);
      try {
        cache.consume(nonce.toString("base64url"), nowSeconds);
      } catch (error) {
        assert.equal((error as AuthenticationError).code, "nonce_cache_capacity_exhausted");
        capacityRejects += 1;
      }
    }
    assert.equal(cache.size, 64);
    assert.equal(capacityRejects, 10_001 - 64);
    assert.throws(
      () => cache.consume(first, nowSeconds),
      (error: unknown) => error instanceof AuthenticationError && error.code === "replayed_nonce",
    );
  });
});
