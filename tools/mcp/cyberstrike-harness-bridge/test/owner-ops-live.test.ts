import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { executeCapability } from "../src/backend-executor.ts";
import { MANIFEST_REVISION } from "../src/manifest.ts";
import { GatewayService } from "../src/service.ts";

describe("owner-ops live capability execution", () => {
  it("executes capabilities directly when OWNER_OPS is active", async () => {
    process.env.OWNER_OPS = "1";
    const service = new GatewayService({ executor: executeCapability });

    const result = await service.invoke({
      capability: "osint.dns_lookup",
      manifestRevision: MANIFEST_REVISION,
      arguments: { domain: "bolt.eu", type: "A" },
      idempotencyKey: "12345678-1234-4234-8234-123456789abc",
      confirm: false,
    });

    assert.equal(result.ok, true);
    assert.equal(result.reasonCode, "completed");
    assert.ok(result.result);
    delete process.env.OWNER_OPS;
  });
});
