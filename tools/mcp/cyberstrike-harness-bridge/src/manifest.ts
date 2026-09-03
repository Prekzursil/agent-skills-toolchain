import { sha256Canonical } from "./canonical-json.ts";
import { SECURITY_CAPABILITIES, type RiskClass } from "./inventory.ts";
import { arrayOf, boolean, enumeration, objectSchema, text, type JsonSchema } from "./schema.ts";

export const PROTOCOL = "ast.cyberstrike.bridge/v1";
export const GATEWAY_NAME = "cyberstrike-gateway";
export const GATEWAY_VERSION = "0.1.0";
export { SECURITY_CAPABILITIES };

export type BridgeCapability = Readonly<{
  id: string;
  backendId: "codex" | "fanout";
  upstreamToolName: string;
  inputSchema: JsonSchema;
  riskClass: "read" | "write" | "external_billable";
  available: false;
  unavailableReason: string;
  permanentlyDenied: false;
}>;

const promptSchema = objectSchema(
  { prompt: text(32_768), threadId: text(128, { pattern: "^[A-Za-z0-9_-]+$" }) },
  ["prompt"],
);
const fanoutUnitSchema = objectSchema(
  {
    unitId: text(128, { pattern: "^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$" }),
    prompt: text(32_768),
    expectedArtifact: text(256, { pattern: "^[A-Za-z0-9][A-Za-z0-9._-]{0,255}$" }),
  },
  ["unitId", "prompt", "expectedArtifact"],
);
const uuidSchema = text(36, {
  pattern: "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$",
});

function bridgeCapability(
  id: string,
  upstreamToolName: string,
  inputSchema: JsonSchema,
  riskClass: BridgeCapability["riskClass"],
): BridgeCapability {
  const backendId = id.startsWith("codex.") ? "codex" : "fanout";
  return Object.freeze({
    id,
    backendId,
    upstreamToolName,
    inputSchema,
    riskClass,
    available: false as const,
    unavailableReason:
      backendId === "codex"
        ? "official_codex_mcp_adapter_unimplemented"
        : "databricks_fanout_adapter_unimplemented",
    permanentlyDenied: false as const,
  });
}

export const BRIDGE_CAPABILITIES: readonly BridgeCapability[] = Object.freeze([
  bridgeCapability("codex.consult", "codex_consult", promptSchema, "read"),
  bridgeCapability("codex.brainstorm", "codex_brainstorm", promptSchema, "read"),
  bridgeCapability("codex.review", "codex_review", promptSchema, "read"),
  bridgeCapability("codex.discuss", "codex_discuss", promptSchema, "read"),
  bridgeCapability("codex.coordinate", "codex_coordinate", promptSchema, "write"),
  bridgeCapability("codex.curate", "codex_curate", promptSchema, "write"),
  bridgeCapability(
    "fanout.prepare",
    "fanout_prepare",
    objectSchema({ batchId: uuidSchema, units: arrayOf(fanoutUnitSchema, 2_000, 1) }, ["batchId", "units"]),
    "write",
  ),
  bridgeCapability(
    "fanout.submit",
    "fanout_submit",
    objectSchema(
      {
        preparedBatchId: uuidSchema,
        profile: enumeration(["DEFAULT", "bolt-datascience", "bolt-common", "bolt-geo"]),
      },
      ["preparedBatchId", "profile"],
    ),
    "external_billable",
  ),
  bridgeCapability(
    "fanout.status",
    "fanout_status",
    objectSchema({ runId: text(256, { pattern: "^[A-Za-z0-9._:-]+$" }), profile: enumeration(["DEFAULT", "bolt-datascience", "bolt-common", "bolt-geo"]) }, ["runId", "profile"]),
    "read",
  ),
  bridgeCapability(
    "fanout.harvest",
    "fanout_harvest",
    objectSchema({ runId: text(256, { pattern: "^[A-Za-z0-9._:-]+$" }), profile: enumeration(["DEFAULT", "bolt-datascience", "bolt-common", "bolt-geo"]) }, ["runId", "profile"]),
    "write",
  ),
]);

type BackendDefinition = Readonly<{
  id: string;
  source: string;
  sourcePin: string;
  expectedToolCount: number;
  upstreamWireSchemaSha256: string;
  policyOverlaySha256: string;
  credentialBindings: readonly string[];
  containment: "windows-job-object";
  active: true;
  available: false;
  unavailableReason: "windows_job_object_containment_unverified";
}>;

// These are independent contracts. The wire pins were calculated from the reviewed upstream
// `tools/list` payload ({name,inputSchema} only). The policy pins cover this gateway's hardened
// schemas plus risk and permanent-deny metadata. Never substitute one digest for the other.
const UPSTREAM_WIRE_SCHEMA_PINS: Readonly<Record<string, string>> = Object.freeze({
  "cloud-audit": "3a2defc428b1d5e84a12ae7d50104f601de756502a5e99ffcdf9da5a96fa658b",
  "github-security": "a4786efbe9f01de8d37a1c09b879de8d22110317fc4e7f2431177c2eacf77b75",
  "cve-mcp": "a7fdff3aeb8033901a948fe897676672023b75a01b6dffed3b01f67187cc3087",
  osint: "99ed25c56d2800ae0cf5ce6cc0f6f3aed6a8c3a096147915ae7820c4f701259a",
  metasploit: "0b69f9cfc6b795ae07fbb665ccd244e7f548bbcfa6c55fd280c483f4aa04e58c",
});

const POLICY_OVERLAY_PINS: Readonly<Record<string, string>> = Object.freeze({
  "cloud-audit": "cefce0fa05279a1b1e2c574fb37ac9a914cc4b57c884848e06b6549891f06655",
  "github-security": "81951f6a6a141f7359506b5e4a23d4a6f6bc58edf6db5752097608c9882330c6",
  "cve-mcp": "8175bd39f064b0b94dfeda6ebba2ce11bdd78071868422097d3f50214057b76a",
  osint: "5b945a51ec38af29a7253f89cee1bd9d2b2686e9d9b4e1d6d7f7894ffc944ba9",
  metasploit: "a7149be8ea2541ef9056fcae4f863783efb677bc90ec279d5d5cfef9879ea431",
});

function backend(
  id: string,
  source: string,
  sourcePin: string,
  expectedToolCount: number,
  credentialBindings: readonly string[],
): BackendDefinition {
  return Object.freeze({
    id,
    source,
    sourcePin,
    expectedToolCount,
    upstreamWireSchemaSha256: UPSTREAM_WIRE_SCHEMA_PINS[id],
    policyOverlaySha256: POLICY_OVERLAY_PINS[id],
    credentialBindings: Object.freeze([...credentialBindings]),
    containment: "windows-job-object" as const,
    active: true as const,
    available: false as const,
    unavailableReason: "windows_job_object_containment_unverified" as const,
  });
}

export const BACKEND_DEFINITIONS: readonly BackendDefinition[] = Object.freeze([
  backend("cloud-audit", "badchars/cloud-audit-mcp", "e32c53a1b02df50e4a1ba072da17b00dc971bb15", 38, []),
  backend("github-security", "npm:github-security-mcp", "0.1.0", 39, ["GITHUB_MCP_PAT"]),
  backend("cve-mcp", "npm:cve-mcp", "0.2.0", 41, ["NVD_API_KEY", "GITHUB_MCP_PAT", "VULNCHECK_API_KEY", "VULNERS_API_KEY", "ATTACKERKB_API_KEY"]),
  backend("osint", "npm:osint-mcp-server", "0.2.0", 37, ["SHODAN_API_KEY", "VT_API_KEY", "ST_API_KEY", "CENSYS_API_ID", "CENSYS_API_SECRET"]),
  backend("metasploit", "rapid7:metasploit-framework", "6.5.3-20260826060514", 16, ["METASPLOIT_RPC_CREDENTIAL_FILE"]),
]);

export const ALL_CAPABILITIES = Object.freeze([...BRIDGE_CAPABILITIES, ...SECURITY_CAPABILITIES]);

function normalizedPolicyOverlay(backendId: string) {
  return SECURITY_CAPABILITIES.filter((capability) => capability.backendId === backendId)
    .map((capability) => ({
      upstreamToolName: capability.upstreamToolName,
      inputSchema: capability.inputSchema,
      riskClass: capability.riskClass,
      permanentlyDenied: capability.permanentlyDenied,
      ...(capability.denyReason ? { denyReason: capability.denyReason } : {}),
    }))
    .sort((left, right) => left.upstreamToolName.localeCompare(right.upstreamToolName));
}

export function calculatedPolicyOverlayHashes(): Record<string, string> {
  return Object.fromEntries(
    BACKEND_DEFINITIONS.map((definition) => [
      definition.id,
      sha256Canonical(normalizedPolicyOverlay(definition.id)),
    ]),
  );
}

// Backward-compatible diagnostic alias. This is a policy-overlay hash, never an upstream wire hash.
export const calculatedInventoryHashes = calculatedPolicyOverlayHashes;

export function verifyInventoryPins(): string[] {
  const calculated = calculatedPolicyOverlayHashes();
  return BACKEND_DEFINITIONS.flatMap((definition) => {
    const actualCount = SECURITY_CAPABILITIES.filter(
      (capability) => capability.backendId === definition.id,
    ).length;
    const mismatches: string[] = [];
    if (actualCount !== definition.expectedToolCount) {
      mismatches.push(`${definition.id}:count:${actualCount}:${definition.expectedToolCount}`);
    }
    if (!/^[a-f0-9]{64}$/.test(definition.upstreamWireSchemaSha256)) {
      mismatches.push(`${definition.id}:wire_sha256:invalid`);
    }
    if (calculated[definition.id] !== definition.policyOverlaySha256) {
      mismatches.push(
        `${definition.id}:policy_sha256:${calculated[definition.id]}:${definition.policyOverlaySha256}`,
      );
    }
    return mismatches;
  });
}

function manifestPayload() {
  return {
    protocol: PROTOCOL,
    gateway: GATEWAY_NAME,
    version: GATEWAY_VERSION,
    backends: BACKEND_DEFINITIONS.map((definition) => ({
      id: definition.id,
      source: definition.source,
      sourcePin: definition.sourcePin,
      expectedToolCount: definition.expectedToolCount,
      upstreamWireSchemaSha256: definition.upstreamWireSchemaSha256,
      policyOverlaySha256: definition.policyOverlaySha256,
      credentialBindings: definition.credentialBindings,
      active: definition.active,
      available: definition.available,
      unavailableReason: definition.unavailableReason,
    })),
    capabilities: ALL_CAPABILITIES.map((capability) => ({
      id: capability.id,
      backendId: capability.backendId,
      upstreamToolName: capability.upstreamToolName,
      inputSchema: capability.inputSchema,
      riskClass: capability.riskClass,
      available: capability.available,
      unavailableReason: capability.unavailableReason,
      permanentlyDenied: capability.permanentlyDenied,
      ...(capability.denyReason ? { denyReason: capability.denyReason } : {}),
    })),
  };
}

export const MANIFEST_REVISION = sha256Canonical(manifestPayload());

export function buildCapabilityManifest() {
  return Object.freeze({ ...manifestPayload(), revision: MANIFEST_REVISION });
}

const invokeToolSchema = objectSchema(
  {
    capability: enumeration(ALL_CAPABILITIES.map((capability) => capability.id)),
    manifestRevision: text(64, { pattern: "^[a-f0-9]{64}$" }),
    arguments: Object.freeze({ type: "object", additionalProperties: true }),
    idempotencyKey: uuidSchema,
    confirm: boolean(),
  },
  ["capability", "manifestRevision", "arguments", "idempotencyKey", "confirm"],
);

export const RUNTIME_TOOLS = Object.freeze([
  Object.freeze({
    name: "harness_bridge_status",
    description: "Read-only gateway protocol and version status.",
    inputSchema: objectSchema(),
  }),
  Object.freeze({
    name: "harness_capabilities",
    description: "Read-only closed capability manifest and canonical revision.",
    inputSchema: objectSchema(),
  }),
  Object.freeze({
    name: "harness_invoke",
    description: "Invoke exactly one manifest-pinned capability through the fail-closed guard.",
    inputSchema: invokeToolSchema,
  }),
]);

export function getCapability(id: string) {
  return ALL_CAPABILITIES.find((capability) => capability.id === id);
}

export type AnyCapability = (typeof ALL_CAPABILITIES)[number] & { riskClass: RiskClass | "external_billable" };
