import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { AGPL_BOUNDARY_CENSUS, censusAgplBoundary } from "../src/agpl-boundary.ts";
import { createAuditRecord, deepRedact } from "../src/audit.ts";
import { canonicalJson } from "../src/canonical-json.ts";

describe("redacted audit", () => {
  it("never persists prompts, commands, secrets, auth, cookies, stderr, or raw output", () => {
    const raw = {
      requestId: "request",
      provider: "safe-provider-binding",
      prompt: "private prompt",
      command: "do not log",
      nested: {
        password: "hunter2",
        authorization: "Bearer secret",
        cookie: "sid=secret",
        stderr: "secret trace",
        output: "raw output",
      },
      idempotencyKey: "safe-id",
    };
    const redacted = deepRedact(raw);
    const serialized = JSON.stringify(redacted);
    for (const forbidden of ["private prompt", "do not log", "hunter2", "Bearer secret", "sid=secret", "secret trace", "raw output"]) {
      assert.equal(serialized.includes(forbidden), false, forbidden);
    }
    assert.equal(redacted.idempotencyKey, "safe-id");
  });

  it("writes an allowlisted receipt with only hashes and lengths for arguments/results", () => {
    const record = createAuditRecord({
      utc: "2026-09-02T18:00:00.000Z",
      requestId: "f6ca33c0-f416-4198-9717-44ad023fab4a",
      correlationId: "7cb5ea16-2c6c-4295-bf78-6e91eb0ba798",
      engagementId: "4d1ebd0a-36c8-46dd-ab5f-35117020563e",
      capability: "cve-mcp.nvd_get",
      decision: "deny",
      reasonCode: "engagement_required",
      durationMs: 12,
      arguments: { cveId: "CVE-2026-1234", token: "secret" },
      result: { text: "raw result" },
    });
    const serialized = JSON.stringify(record);
    assert.match(record.argumentsSha256, /^[a-f0-9]{64}$/);
    assert.match(record.resultSha256, /^[a-f0-9]{64}$/);
    assert.equal(serialized.includes("secret"), false);
    assert.equal(serialized.includes("raw result"), false);
    assert.deepEqual(Object.keys(record).sort(), [
      "argumentsLength",
      "argumentsSha256",
      "capability",
      "correlationId",
      "decision",
      "durationMs",
      "engagementId",
      "reasonCode",
      "requestId",
      "resultLength",
      "resultSha256",
      "utc",
    ]);
  });

  it("serializes pre-engagement denials without an undefined engagement field", () => {
    const record = createAuditRecord({
      utc: "2026-09-02T18:00:00.000Z",
      requestId: "f6ca33c0-f416-4198-9717-44ad023fab4a",
      correlationId: "7cb5ea16-2c6c-4295-bf78-6e91eb0ba798",
      capability: "cve-mcp.nvd_get",
      decision: "deny",
      reasonCode: "windows_job_object_containment_unverified",
      durationMs: 1,
      arguments: { cveId: "CVE-2026-1234" },
    });

    assert.equal(Object.hasOwn(record, "engagementId"), false);
    assert.doesNotThrow(() => canonicalJson(record));
  });
});

describe("AGPL process boundary census", () => {
  it("records CyberStrike as external and keeps the private gateway dependency-free", () => {
    assert.equal(AGPL_BOUNDARY_CENSUS.gatewayImportsCyberStrike, false);
    assert.equal(AGPL_BOUNDARY_CENSUS.cyberStrikeBoundary, "external-process");
    assert.deepEqual(censusAgplBoundary({ packageJson: '{"dependencies":{}}', sources: ["import fs from 'node:fs';"] }), []);
  });

  it("detects forbidden CyberStrike SDK/plugin imports and dependencies", () => {
    const violations = censusAgplBoundary({
      packageJson: '{"dependencies":{"@cyberstrike-io/sdk":"1.1.16"}}',
      sources: ["import { tool } from '@cyberstrike-io/plugin';"],
    });
    assert.deepEqual(violations.map((item) => item.code), [
      "forbidden_cyberstrike_dependency",
      "forbidden_cyberstrike_import",
    ]);
  });
});
