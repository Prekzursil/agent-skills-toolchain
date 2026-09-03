import { canonicalJson, sha256Canonical } from "./canonical-json.ts";
import { ALL_CAPABILITIES, MANIFEST_REVISION, getCapability } from "./manifest.ts";
import { SchemaValidationError, validateSchema } from "./schema.ts";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const REVISION = /^[a-f0-9]{64}$/;
const INVOKE_KEYS = ["arguments", "capability", "confirm", "idempotencyKey", "manifestRevision"];

const C2_PATTERNS = [
  /(?:^|[^a-z0-9])sliver(?:$|[^a-z0-9])/u,
  /(?:^|[^a-z0-9])multi[\\/]+handler(?:$|[^a-z0-9])/u,
  /(?:^|[^a-z0-9])meterpreter(?:$|[^a-z0-9])/u,
  /(?:^|[^a-z0-9])reverse[\s_-]*shell(?:$|[^a-z0-9])/u,
  /(?:^|[^a-z0-9])reverse_(?:tcp|http|https)(?:$|[^a-z0-9])/u,
  /(?:^|[^a-z0-9])persistent\s+listeners?(?:$|[^a-z0-9])/u,
  /(?:^|[^a-z0-9])sessions?\s+-i(?:$|[^a-z0-9])/u,
  /(?:^|[^a-z0-9])command[\s_-]*and[\s_-]*control(?:$|[^a-z0-9])/u,
  /(?:^|[^a-z0-9])c2\s+(?:callback|channel|listener|server)(?:$|[^a-z0-9])/u,
  /(?:^|[^a-z0-9])msfvenom(?:$|[^a-z0-9])/u,
];

function normalized(value: string): string {
  return value.normalize("NFKC").replace(/\s/gu, " ").toLowerCase();
}

export function classifyPermanentDeny(
  input: unknown,
  capabilityId?: string,
): { reasonCode: "c2_always_denied" | "policy_input_uninspectable" } | undefined {
  if (
    capabilityId === "metasploit.msf_session_read" ||
    capabilityId === "metasploit.msf_session_write"
  ) {
    return { reasonCode: "c2_always_denied" };
  }

  const pending: Array<{ value: unknown; key?: string; depth: number }> = [
    { value: input, depth: 0 },
  ];
  let visited = 0;
  while (pending.length > 0) {
    const current = pending.pop()!;
    visited += 1;
    if (visited > 10_000 || current.depth > 32) {
      return { reasonCode: "policy_input_uninspectable" };
    }
    if (typeof current.value === "string") {
      const candidate = normalized(current.value);
      if (C2_PATTERNS.some((pattern) => pattern.test(candidate))) {
        return { reasonCode: "c2_always_denied" };
      }
      if (
        capabilityId === "metasploit.msf_module_execute" &&
        ((current.key === "type" && candidate === "payload") ||
          (current.key?.toUpperCase() === "PAYLOAD" && candidate.length > 0))
      ) {
        return { reasonCode: "c2_always_denied" };
      }
    } else if (Array.isArray(current.value)) {
      for (const item of current.value) pending.push({ value: item, depth: current.depth + 1 });
    } else if (current.value && typeof current.value === "object") {
      for (const [key, value] of Object.entries(current.value as Record<string, unknown>)) {
        pending.push({ value, key, depth: current.depth + 1 });
      }
    }
  }
  return undefined;
}

export type InvokeInput = {
  capability: string;
  manifestRevision: string;
  arguments: Record<string, unknown>;
  idempotencyKey: string;
  confirm: boolean;
};

export class InvokeValidationError extends Error {
  code: string;

  constructor(code: string) {
    super(code);
    this.name = "InvokeValidationError";
    this.code = code;
  }
}

export function validateInvokeInput(input: unknown): InvokeInput {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new InvokeValidationError("invalid_invoke_object");
  }
  const record = input as Record<string, unknown>;
  const keys = Object.keys(record).sort();
  if (keys.length !== INVOKE_KEYS.length || keys.some((key, index) => key !== INVOKE_KEYS[index])) {
    throw new InvokeValidationError("invalid_invoke_property");
  }
  if (typeof record.capability !== "string" || !getCapability(record.capability)) {
    throw new InvokeValidationError("invalid_capability");
  }
  if (typeof record.manifestRevision !== "string" || !REVISION.test(record.manifestRevision)) {
    throw new InvokeValidationError("invalid_manifest_revision");
  }
  if (record.manifestRevision !== MANIFEST_REVISION) {
    throw new InvokeValidationError("capability_manifest_changed");
  }
  if (typeof record.idempotencyKey !== "string" || !UUID.test(record.idempotencyKey)) {
    throw new InvokeValidationError("invalid_idempotency_key");
  }
  if (typeof record.confirm !== "boolean") throw new InvokeValidationError("invalid_confirm");
  if (!record.arguments || typeof record.arguments !== "object" || Array.isArray(record.arguments)) {
    throw new InvokeValidationError("invalid_arguments_object");
  }
  const capability = getCapability(record.capability)!;
  try {
    validateSchema(capability.inputSchema, record.arguments);
  } catch (error) {
    if (error instanceof SchemaValidationError) throw new InvokeValidationError(error.code);
    throw error;
  }
  const normalizedInput: InvokeInput = {
    capability: record.capability,
    manifestRevision: record.manifestRevision,
    arguments: record.arguments as Record<string, unknown>,
    idempotencyKey: record.idempotencyKey,
    confirm: record.confirm,
  };
  if (Buffer.byteLength(canonicalJson(normalizedInput), "utf8") > 65_536) {
    throw new InvokeValidationError("invalid_invoke_size");
  }
  return normalizedInput;
}

export function invocationHash(input: InvokeInput): string {
  return sha256Canonical({
    capability: input.capability,
    manifestRevision: input.manifestRevision,
    arguments: input.arguments,
    confirm: input.confirm,
  });
}

export function capabilityIds(): readonly string[] {
  return ALL_CAPABILITIES.map((capability) => capability.id);
}
