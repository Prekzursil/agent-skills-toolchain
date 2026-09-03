import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  BACKEND_DEFINITIONS,
  BRIDGE_CAPABILITIES,
  MANIFEST_REVISION,
  RUNTIME_TOOLS,
  SECURITY_CAPABILITIES,
  buildCapabilityManifest,
  calculatedPolicyOverlayHashes,
  verifyInventoryPins,
} from "../src/manifest.ts";

describe("closed capability manifest", () => {
  it("exposes exactly one three-tool MCP surface", () => {
    assert.deepEqual(
      RUNTIME_TOOLS.map((tool) => tool.name),
      ["harness_bridge_status", "harness_capabilities", "harness_invoke"],
    );
    assert.equal(new Set(RUNTIME_TOOLS.map((tool) => tool.name)).size, 3);
  });

  it("preserves all 171 security tools and the ten approved bridge capabilities", () => {
    const expectedCounts = {
      "cloud-audit": 38,
      "github-security": 39,
      "cve-mcp": 41,
      osint: 37,
      metasploit: 16,
    };

    assert.deepEqual(
      Object.fromEntries(BACKEND_DEFINITIONS.map((backend) => [backend.id, backend.expectedToolCount])),
      expectedCounts,
    );
    assert.equal(SECURITY_CAPABILITIES.length, 171);
    assert.equal(BRIDGE_CAPABILITIES.length, 10);
    assert.equal(new Set(SECURITY_CAPABILITIES.map((capability) => capability.id)).size, 171);

    for (const [backendId, expected] of Object.entries(expectedCounts)) {
      assert.equal(
        SECURITY_CAPABILITIES.filter((capability) => capability.backendId === backendId).length,
        expected,
      );
    }
  });

  it("publishes strict schemas and fail-closed containment status without hiding tools", () => {
    for (const capability of SECURITY_CAPABILITIES) {
      assert.equal(capability.inputSchema.type, "object", capability.id);
      assert.equal(capability.inputSchema.additionalProperties, false, capability.id);
      assert.equal(capability.available, false, capability.id);
      assert.equal(capability.unavailableReason, "windows_job_object_containment_unverified", capability.id);
      assert.ok(capability.upstreamToolName.length > 0, capability.id);
    }

    const sessionWrite = SECURITY_CAPABILITIES.find(
      (capability) => capability.id === "metasploit.msf_session_write",
    );
    assert.equal(sessionWrite?.permanentlyDenied, true);
    assert.equal(sessionWrite?.denyReason, "c2_session_command_channel");
  });

  it("keeps reviewed upstream wire schemas separate from the policy overlay", () => {
    const expectedWireSchemaHashes = {
      "cloud-audit": "3a2defc428b1d5e84a12ae7d50104f601de756502a5e99ffcdf9da5a96fa658b",
      "github-security": "a4786efbe9f01de8d37a1c09b879de8d22110317fc4e7f2431177c2eacf77b75",
      "cve-mcp": "a7fdff3aeb8033901a948fe897676672023b75a01b6dffed3b01f67187cc3087",
      osint: "99ed25c56d2800ae0cf5ce6cc0f6f3aed6a8c3a096147915ae7820c4f701259a",
      metasploit: "0b69f9cfc6b795ae07fbb665ccd244e7f548bbcfa6c55fd280c483f4aa04e58c",
    };
    const policyOverlayHashes = calculatedPolicyOverlayHashes();

    assert.deepEqual(
      Object.fromEntries(
        BACKEND_DEFINITIONS.map((backend) => [backend.id, backend.upstreamWireSchemaSha256]),
      ),
      expectedWireSchemaHashes,
    );
    for (const backend of BACKEND_DEFINITIONS) {
      assert.match(backend.policyOverlaySha256, /^[a-f0-9]{64}$/);
      assert.equal(policyOverlayHashes[backend.id], backend.policyOverlaySha256);
      assert.notEqual(backend.upstreamWireSchemaSha256, backend.policyOverlaySha256);
    }

    const published = buildCapabilityManifest();
    assert.equal(
      published.backends.every(
        (backend) =>
          backend.upstreamWireSchemaSha256.length === 64 &&
          backend.policyOverlaySha256.length === 64 &&
          !("inventorySha256" in backend),
      ),
      true,
    );
  });

  it("pins every normalized policy overlay and derives a stable canonical revision", () => {
    assert.deepEqual(verifyInventoryPins(), []);
    assert.match(MANIFEST_REVISION, /^[a-f0-9]{64}$/);
    assert.equal(buildCapabilityManifest().revision, MANIFEST_REVISION);
    assert.equal(buildCapabilityManifest().revision, buildCapabilityManifest().revision);
  });
});
