import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { MemoryAuditSink } from "../src/audit.ts";
import { IdempotencyLedger } from "../src/idempotency.ts";
import { MANIFEST_REVISION } from "../src/manifest.ts";
import { classifyPermanentDeny, validateInvokeInput } from "../src/policy.ts";
import { GatewayService } from "../src/service.ts";

const idempotencyKey = "3f69c2c5-b576-4ea9-bac5-2403f27a7ed8";

describe("deny-first invocation policy", () => {
  it("recognizes C2/session channels in nested and Unicode-bearing input", () => {
    for (const args of [
      { module: "exploit/multi/handler" },
      { payload: "windows/x64/meterpreter/reverse_tcp" },
      { nested: ["start a persistent listener", { command: "sessions -i 2" }] },
      { note: "SLIVER callback" },
      { command: "reverse\u00a0shell" },
    ]) {
      assert.equal(classifyPermanentDeny(args)?.reasonCode, "c2_always_denied");
    }
    assert.equal(classifyPermanentDeny({ query: "CVE-2026-1234" }), undefined);
  });

  it("validates the closed invoke envelope and rejects extra, empty, or invalid values", () => {
    const valid = {
      capability: "cve-mcp.nvd_get",
      manifestRevision: MANIFEST_REVISION,
      arguments: { cveId: "CVE-2026-1234" },
      idempotencyKey,
      confirm: false,
    };
    assert.equal(validateInvokeInput(valid).capability, valid.capability);

    for (const invalid of [
      null,
      {},
      { ...valid, extra: true },
      { ...valid, manifestRevision: "0".repeat(64) },
      { ...valid, idempotencyKey: "not-a-uuid" },
      { ...valid, arguments: [] },
      { ...valid, capability: "metasploit.raw_rpc" },
    ]) {
      assert.throws(() => validateInvokeInput(invalid), /invalid_|manifest|capability|object|property/);
    }
  });

  it("enforces Metasploit option names and cardinality while accepting scalar integers", () => {
    const base = {
      capability: "metasploit.msf_module_check",
      manifestRevision: MANIFEST_REVISION,
      arguments: {
        type: "auxiliary",
        name: "scanner/http/title",
        options: { RPORT: 443, SSL: true },
      },
      idempotencyKey: "00000000-0000-4000-8000-000000000030",
      confirm: true,
    };
    assert.doesNotThrow(() => validateInvokeInput(base));
    assert.throws(
      () =>
        validateInvokeInput({
          ...base,
          arguments: { ...base.arguments, options: { "1INVALID": "value" } },
        }),
      /property_name/,
    );
    assert.throws(
      () =>
        validateInvokeInput({
          ...base,
          arguments: {
            ...base.arguments,
            options: Object.fromEntries(
              Array.from({ length: 257 }, (_, index) => [`OPTION_${index}`, index]),
            ),
          },
        }),
      /object_bounds/,
    );
  });

  it("gives the permanent C2 deny precedence over grants and containment state", async () => {
    let executions = 0;
    const service = new GatewayService({
      engagementProvider: async () => ({
        id: "2fbe919a-c026-46ae-b9bb-8e773c2b4ac2",
        expiresAt: "2099-01-01T00:00:00.000Z",
        allowedCapabilities: ["metasploit.msf_module_execute"],
        signatureVerified: true,
      }),
      executor: async () => {
        executions += 1;
        return { ok: true };
      },
    });

    const result = await service.invoke({
      capability: "metasploit.msf_module_execute",
      manifestRevision: MANIFEST_REVISION,
      arguments: {
        type: "exploit",
        name: "multi/handler",
        options: { PAYLOAD: "windows/meterpreter/reverse_tcp" },
      },
      idempotencyKey,
      confirm: true,
    });

    assert.deepEqual(result, {
      ok: false,
      reasonCode: "c2_always_denied",
      idempotencyKey,
      replayed: false,
    });
    assert.equal(executions, 0);
  });

  it("fails closed on containment and replays only byte-equivalent requests", async () => {
    const service = new GatewayService();
    const input = {
      capability: "cve-mcp.nvd_get",
      manifestRevision: MANIFEST_REVISION,
      arguments: { cveId: "CVE-2026-1234" },
      idempotencyKey,
      confirm: false,
    };
    const first = await service.invoke(input);
    const replay = await service.invoke(input);
    const conflict = await service.invoke({ ...input, arguments: { cveId: "CVE-2026-9999" } });

    assert.equal(first.reasonCode, "windows_job_object_containment_unverified");
    assert.equal(first.replayed, false);
    assert.equal(replay.reasonCode, first.reasonCode);
    assert.equal(replay.replayed, true);
    assert.equal(conflict.reasonCode, "idempotency_conflict");
  });

  it("requires a manifest-bound verified engagement without requiring confirmation for reads", async () => {
    const now = Date.parse("2026-09-02T18:00:00.000Z");
    const auditSink = new MemoryAuditSink();
    let executions = 0;
    const service = new GatewayService({
      now: () => now,
      auditSink,
      capabilityStateProvider: () => ({ available: true, containmentVerified: true }),
      engagementProvider: async () => ({
        id: "2fbe919a-c026-46ae-b9bb-8e773c2b4ac2",
        expiresAt: "2026-09-02T18:05:00.000Z",
        manifestRevision: MANIFEST_REVISION,
        allowedCapabilities: ["cve-mcp.nvd_get"],
        signatureVerified: true,
      }),
      executor: async () => {
        executions += 1;
        return { findings: ["CVE-2026-1234"], accessToken: "must-not-leak" };
      },
    });

    const result = await service.invoke({
      capability: "cve-mcp.nvd_get",
      manifestRevision: MANIFEST_REVISION,
      arguments: { cveId: "CVE-2026-1234" },
      idempotencyKey: "00000000-0000-4000-8000-000000000001",
      confirm: false,
    });

    assert.deepEqual(result, {
      ok: true,
      reasonCode: "completed",
      idempotencyKey: "00000000-0000-4000-8000-000000000001",
      replayed: false,
      result: { findings: ["CVE-2026-1234"], accessToken: "[REDACTED]" },
    });
    assert.equal(executions, 1);
    assert.equal(auditSink.records.at(-1)?.decision, "allow");
  });

  it("rejects missing, expired, unverified, or wrong-revision engagements", async () => {
    const now = Date.parse("2026-09-02T18:00:00.000Z");
    const baseGrant = {
      id: "2fbe919a-c026-46ae-b9bb-8e773c2b4ac2",
      expiresAt: "2026-09-02T18:05:00.000Z",
      manifestRevision: MANIFEST_REVISION,
      allowedCapabilities: ["cve-mcp.nvd_get"],
      signatureVerified: true,
    };
    const grants = [
      undefined,
      { ...baseGrant, expiresAt: "2026-09-02T17:59:59.999Z" },
      { ...baseGrant, signatureVerified: false },
      { ...baseGrant, manifestRevision: "0".repeat(64) },
      { ...baseGrant, id: "not-a-uuid" },
      { ...baseGrant, allowedCapabilities: ["osint.dns_lookup"] },
    ];

    for (const [index, grant] of grants.entries()) {
      const service = new GatewayService({
        now: () => now,
        capabilityStateProvider: () => ({ available: true, containmentVerified: true }),
        engagementProvider: async () => grant,
      });
      const result = await service.invoke({
        capability: "cve-mcp.nvd_get",
        manifestRevision: MANIFEST_REVISION,
        arguments: { cveId: "CVE-2026-1234" },
        idempotencyKey: `00000000-0000-4000-8000-${String(index + 10).padStart(12, "0")}`,
        confirm: false,
      });
      assert.equal(result.reasonCode, "engagement_required", String(index));
    }
  });

  it("requires fresh confirmation for external submissions and bounds backend responses", async () => {
    const now = Date.parse("2026-09-02T18:00:00.000Z");
    const grant = {
      id: "2fbe919a-c026-46ae-b9bb-8e773c2b4ac2",
      expiresAt: "2026-09-02T18:05:00.000Z",
      manifestRevision: MANIFEST_REVISION,
      allowedCapabilities: ["osint.vt_url"],
      signatureVerified: true,
    };
    const makeService = (executor: () => Promise<unknown>) =>
      new GatewayService({
        now: () => now,
        capabilityStateProvider: () => ({ available: true, containmentVerified: true }),
        engagementProvider: async () => grant,
        executor,
      });

    const missingConfirmation = await makeService(async () => ({ ok: true })).invoke({
      capability: "osint.vt_url",
      manifestRevision: MANIFEST_REVISION,
      arguments: { url: "https://example.test" },
      idempotencyKey: "00000000-0000-4000-8000-000000000020",
      confirm: false,
    });
    assert.equal(missingConfirmation.reasonCode, "fresh_confirmation_required");

    const oversized = await makeService(async () => ({ findings: ["x".repeat(65_536)] })).invoke({
      capability: "osint.vt_url",
      manifestRevision: MANIFEST_REVISION,
      arguments: { url: "https://example.test" },
      idempotencyKey: "00000000-0000-4000-8000-000000000021",
      confirm: true,
    });
    assert.equal(oversized.reasonCode, "backend_response_too_large");
    assert.equal(oversized.result, undefined);
  });
});

describe("bounded idempotency ledger", () => {
  it("reserves, commits, replays, conflicts, and evicts without races", () => {
    const ledger = new IdempotencyLedger({ maxEntries: 2, ttlMs: 60_000, now: () => 1000 });
    assert.deepEqual(ledger.begin("a", "hash-a"), { state: "new" });
    assert.deepEqual(ledger.begin("a", "hash-a"), { state: "in_progress" });
    ledger.commit("a", "hash-a", { result: 1 });
    assert.deepEqual(ledger.begin("a", "hash-a"), { state: "replay", value: { result: 1 } });
    assert.deepEqual(ledger.begin("a", "hash-b"), { state: "conflict" });
    ledger.begin("b", "hash-b");
    ledger.begin("c", "hash-c");
    assert.ok(ledger.size <= 2);
  });

  it("never evicts an in-flight reservation when capacity is exhausted", () => {
    const ledger = new IdempotencyLedger({ maxEntries: 2, ttlMs: 60_000, now: () => 1000 });
    assert.deepEqual(ledger.begin("a", "hash-a"), { state: "new" });
    assert.deepEqual(ledger.begin("b", "hash-b"), { state: "new" });
    assert.deepEqual(ledger.begin("c", "hash-c"), { state: "full" });
    assert.deepEqual(ledger.begin("a", "hash-a"), { state: "in_progress" });
    assert.doesNotThrow(() => ledger.commit("a", "hash-a", { result: 1 }));
  });
});
