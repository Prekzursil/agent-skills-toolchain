import { createHash, createHmac, randomBytes, timingSafeEqual } from "node:crypto";

export class AuthenticationError extends Error {
  code: string;

  constructor(code: string) {
    super(code);
    this.name = "AuthenticationError";
    this.code = code;
  }
}

export function decodeHmacKey(encoded: string): Buffer {
  if (typeof encoded !== "string" || !/^[A-Za-z0-9+/]{43}=$/.test(encoded)) {
    throw new Error("HMAC key must be a 32-byte canonical base64 value");
  }
  const decoded = Buffer.from(encoded, "base64");
  if (decoded.length !== 32 || decoded.toString("base64") !== encoded) {
    throw new Error("HMAC key must be a 32-byte canonical base64 value");
  }
  return decoded;
}

function decodeCanonicalBase64Url(value: string, length: number, code: string): Buffer {
  if (typeof value !== "string" || !/^[A-Za-z0-9_-]+$/.test(value)) {
    throw new AuthenticationError(code);
  }
  const decoded = Buffer.from(value, "base64url");
  if (decoded.length !== length || decoded.toString("base64url") !== value) {
    throw new AuthenticationError(code);
  }
  return decoded;
}

function constantEqual(left: Buffer, right: Buffer): boolean {
  return left.length === right.length && timingSafeEqual(left, right);
}

export function bodySha256(body: Buffer): string {
  return createHash("sha256").update(body).digest("hex");
}

export function signedBytes(
  method: string,
  pathname: string,
  timestamp: string,
  nonce: string,
  digest: string,
): string {
  return `${method.toUpperCase()}\n${pathname}\n${timestamp}\n${nonce}\n${digest}`;
}

export class NonceReplayCache {
  readonly ttlSeconds: number;
  readonly maxEntries: number;
  #entries = new Map<string, number>();

  constructor(options: { ttlSeconds?: number; maxEntries?: number } = {}) {
    this.ttlSeconds = Math.max(60, options.ttlSeconds ?? 60);
    this.maxEntries = Math.max(1, options.maxEntries ?? 4096);
  }

  get size(): number {
    return this.#entries.size;
  }

  consume(nonce: string, nowSeconds: number): void {
    this.#prune(nowSeconds);
    const expiresAt = this.#entries.get(nonce);
    if (expiresAt !== undefined && expiresAt > nowSeconds) {
      throw new AuthenticationError("replayed_nonce");
    }
    this.#entries.delete(nonce);
    if (this.#entries.size >= this.maxEntries) {
      throw new AuthenticationError("nonce_cache_capacity_exhausted");
    }
    this.#entries.set(nonce, nowSeconds + this.ttlSeconds);
  }

  #prune(nowSeconds: number): void {
    for (const [nonce, expiresAt] of this.#entries) {
      if (expiresAt > nowSeconds) continue;
      this.#entries.delete(nonce);
    }
  }
}

type SignRequestInput = {
  method: string;
  pathname: string;
  body: Buffer;
  timestamp?: number | string;
  nonceBytes?: Buffer;
};

export function signRequest(key: Buffer, input: SignRequestInput) {
  if (key.length !== 32) throw new Error("invalid_hmac_key_length");
  const timestamp = String(input.timestamp ?? Math.floor(Date.now() / 1000));
  const nonceBytes = input.nonceBytes ?? randomBytes(32);
  if (nonceBytes.length !== 32) throw new Error("invalid_nonce_length");
  const nonce = nonceBytes.toString("base64url");
  const digest = bodySha256(input.body);
  const signature = createHmac("sha256", key)
    .update(signedBytes(input.method, input.pathname, timestamp, nonce, digest), "utf8")
    .digest("base64url");
  return {
    method: input.method.toUpperCase(),
    pathname: input.pathname,
    body: input.body,
    timestamp,
    nonce,
    bodySha256: digest,
    signature,
  };
}

type AuthenticateInput = ReturnType<typeof signRequest> & {
  key: Buffer;
  nowSeconds?: number;
  replayCache: NonceReplayCache;
};

export function authenticateRequest(input: AuthenticateInput): void {
  if (input.key.length !== 32) throw new AuthenticationError("invalid_key");
  if (!/^(0|[1-9][0-9]{0,11})$/.test(String(input.timestamp))) {
    throw new AuthenticationError("invalid_timestamp");
  }
  const timestamp = Number(input.timestamp);
  const nowSeconds = Math.floor(input.nowSeconds ?? Date.now() / 1000);
  if (!Number.isSafeInteger(timestamp) || Math.abs(timestamp - nowSeconds) > 30) {
    throw new AuthenticationError("timestamp_out_of_range");
  }
  decodeCanonicalBase64Url(input.nonce, 32, "invalid_nonce");
  if (!/^[a-f0-9]{64}$/.test(input.bodySha256)) {
    throw new AuthenticationError("invalid_body_digest");
  }
  const actualDigest = bodySha256(input.body);
  if (!constantEqual(Buffer.from(actualDigest, "hex"), Buffer.from(input.bodySha256, "hex"))) {
    throw new AuthenticationError("body_digest_mismatch");
  }
  const suppliedSignature = decodeCanonicalBase64Url(input.signature, 32, "invalid_signature");
  const expectedSignature = createHmac("sha256", input.key)
    .update(
      signedBytes(
        input.method,
        input.pathname,
        String(input.timestamp),
        input.nonce,
        input.bodySha256,
      ),
      "utf8",
    )
    .digest();
  if (!constantEqual(expectedSignature, suppliedSignature)) {
    throw new AuthenticationError("invalid_signature");
  }
  input.replayCache.consume(input.nonce, nowSeconds);
}
