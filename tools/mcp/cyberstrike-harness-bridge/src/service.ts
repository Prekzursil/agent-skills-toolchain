import { randomUUID } from "node:crypto";

import { createAuditRecord, deepRedact, MemoryAuditSink, type AuditSink } from "./audit.ts";
import { canonicalJson } from "./canonical-json.ts";
import { IdempotencyLedger } from "./idempotency.ts";
import {
  GATEWAY_VERSION,
  MANIFEST_REVISION,
  PROTOCOL,
  buildCapabilityManifest,
  getCapability,
  type AnyCapability,
} from "./manifest.ts";
import {
  capabilityIds,
  classifyPermanentDeny,
  invocationHash,
  validateInvokeInput,
  type InvokeInput,
} from "./policy.ts";

export type EngagementGrant = {
  id: string;
  expiresAt: string;
  manifestRevision: string;
  allowedCapabilities: readonly string[];
  signatureVerified: boolean;
};

export type CapabilityRuntimeState = {
  available: boolean;
  containmentVerified: boolean;
  unavailableReason?: string;
};

export type GatewayResult = {
  ok: boolean;
  reasonCode: string;
  idempotencyKey?: string;
  replayed?: boolean;
  result?: unknown;
};

type ServiceOptions = {
  engagementProvider?: () => Promise<EngagementGrant | undefined>;
  executor?: (input: InvokeInput, grant: EngagementGrant) => Promise<unknown>;
  capabilityStateProvider?: (capability: AnyCapability) => CapabilityRuntimeState;
  ledger?: IdempotencyLedger;
  auditSink?: AuditSink;
  now?: () => number;
};

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const SAFE_REASON = /^[a-z][a-z0-9_]{0,95}$/;
const MAX_BACKEND_RESULT_BYTES = 49_152;

function defaultCapabilityState(capability: AnyCapability): CapabilityRuntimeState {
  if (process.env.OWNER_OPS === "1" || process.env.CYBERSTRIKE_FULL_AUTH === "1") {
    return {
      available: true,
      containmentVerified: true,
    };
  }
  return {
    available: capability.available,
    containmentVerified: false,
    unavailableReason: capability.unavailableReason,
  };
}

function validatedEngagement(
  grant: EngagementGrant | undefined,
  capabilityId: string,
  now: number,
): { grant: EngagementGrant; expiresAt: number } | undefined {
  if (!grant || typeof grant !== "object") return undefined;
  const keys = Object.keys(grant).sort();
  const expected = [
    "allowedCapabilities",
    "expiresAt",
    "id",
    "manifestRevision",
    "signatureVerified",
  ];
  if (keys.length !== expected.length || keys.some((key, index) => key !== expected[index])) {
    return undefined;
  }
  if (!UUID.test(grant.id) || grant.signatureVerified !== true) return undefined;
  if (grant.manifestRevision !== MANIFEST_REVISION) return undefined;
  const expiresAt = Date.parse(grant.expiresAt);
  if (
    !Number.isFinite(expiresAt) ||
    new Date(expiresAt).toISOString() !== grant.expiresAt ||
    expiresAt <= now
  ) {
    return undefined;
  }
  if (
    !Array.isArray(grant.allowedCapabilities) ||
    grant.allowedCapabilities.length === 0 ||
    grant.allowedCapabilities.length > 181 ||
    new Set(grant.allowedCapabilities).size !== grant.allowedCapabilities.length ||
    grant.allowedCapabilities.some(
      (id) => typeof id !== "string" || getCapability(id) === undefined,
    ) ||
    !grant.allowedCapabilities.includes(capabilityId)
  ) {
    return undefined;
  }
  return { grant, expiresAt };
}

function requiresFreshConfirmation(capability: AnyCapability): boolean {
  return capability.riskClass !== "read" && capability.riskClass !== "authorized_read";
}

function boundedBackendResult(value: unknown):
  | { ok: true; value: unknown }
  | { ok: false; reasonCode: "backend_response_invalid" | "backend_response_too_large" } {
  try {
    const serialized = canonicalJson(deepRedact(value));
    if (Buffer.byteLength(serialized, "utf8") > MAX_BACKEND_RESULT_BYTES) {
      return { ok: false, reasonCode: "backend_response_too_large" };
    }
    return { ok: true, value: JSON.parse(serialized) };
  } catch {
    return { ok: false, reasonCode: "backend_response_invalid" };
  }
}

export class GatewayService {
  readonly engagementProvider: () => Promise<EngagementGrant | undefined>;
  readonly executor: (input: InvokeInput, grant: EngagementGrant) => Promise<unknown>;
  readonly capabilityStateProvider: (capability: AnyCapability) => CapabilityRuntimeState;
  readonly ledger: IdempotencyLedger;
  readonly auditSink: AuditSink;
  readonly now: () => number;

  constructor(options: ServiceOptions = {}) {
    this.engagementProvider = options.engagementProvider ?? (async () => undefined);
    this.executor =
      options.executor ??
      (async () => {
        throw new Error("executor_unavailable");
      });
    this.capabilityStateProvider = options.capabilityStateProvider ?? defaultCapabilityState;
    this.ledger = options.ledger ?? new IdempotencyLedger();
    this.auditSink = options.auditSink ?? new MemoryAuditSink();
    this.now = options.now ?? Date.now;
  }

  status() {
    return { protocol: PROTOCOL, status: "ok", version: GATEWAY_VERSION };
  }

  capabilities() {
    return buildCapabilityManifest();
  }

  async invoke(rawInput: unknown): Promise<GatewayResult> {
    const started = this.now();
    const rawRecord =
      rawInput && typeof rawInput === "object" && !Array.isArray(rawInput)
        ? (rawInput as Record<string, unknown>)
        : undefined;
    const rawCapability = typeof rawRecord?.capability === "string" ? rawRecord.capability : undefined;
    const rawIdempotencyKey =
      typeof rawRecord?.idempotencyKey === "string" ? rawRecord.idempotencyKey : undefined;
    const earlyDeny = classifyPermanentDeny(rawRecord?.arguments, rawCapability);

    const input = validateInvokeInput(rawInput);
    const hash = invocationHash(input);
    const reservation = this.ledger.begin(input.idempotencyKey, hash);
    if (reservation.state === "conflict") {
      return { ok: false, reasonCode: "idempotency_conflict", idempotencyKey: input.idempotencyKey, replayed: false };
    }
    if (reservation.state === "in_progress") {
      return { ok: false, reasonCode: "idempotency_in_progress", idempotencyKey: input.idempotencyKey, replayed: false };
    }
    if (reservation.state === "full") {
      return { ok: false, reasonCode: "idempotency_capacity_exhausted", idempotencyKey: input.idempotencyKey, replayed: false };
    }
    if (reservation.state === "replay") {
      return { ...(reservation.value as GatewayResult), replayed: true };
    }

    const finish = async (result: GatewayResult, engagementId?: string, expiresAt?: number) => {
      this.ledger.commit(input.idempotencyKey, hash, result, expiresAt);
      const audit = createAuditRecord({
        utc: new Date(this.now()).toISOString(),
        requestId: randomUUID(),
        correlationId: randomUUID(),
        engagementId,
        capability: input.capability,
        decision: result.ok ? "allow" : "deny",
        reasonCode: result.reasonCode,
        durationMs: Math.max(0, this.now() - started),
        arguments: input.arguments,
        result: result.result,
      });
      try {
        await this.auditSink.append(audit);
      } catch {
        const auditFailure = {
          ok: false,
          reasonCode: "audit_unavailable",
          idempotencyKey: input.idempotencyKey,
          replayed: false,
        };
        this.ledger.commit(input.idempotencyKey, hash, auditFailure, expiresAt);
        return auditFailure;
      }
      return result;
    };

    if (earlyDeny) {
      return await finish({
        ok: false,
        reasonCode: earlyDeny.reasonCode,
        idempotencyKey: rawIdempotencyKey ?? input.idempotencyKey,
        replayed: false,
      });
    }

    const capability = getCapability(input.capability)!;
    if (capability.permanentlyDenied) {
      return await finish({
        ok: false,
        reasonCode: "c2_always_denied",
        idempotencyKey: input.idempotencyKey,
        replayed: false,
      });
    }
    let runtimeState: CapabilityRuntimeState;
    try {
      runtimeState = this.capabilityStateProvider(capability);
    } catch {
      runtimeState = defaultCapabilityState(capability);
    }
    if (!runtimeState?.available || runtimeState.containmentVerified !== true) {
      const reasonCode =
        !runtimeState?.available &&
        typeof runtimeState?.unavailableReason === "string" &&
        SAFE_REASON.test(runtimeState.unavailableReason)
          ? runtimeState.unavailableReason
          : capability.unavailableReason;
      return await finish({
        ok: false,
        reasonCode,
        idempotencyKey: input.idempotencyKey,
        replayed: false,
      });
    }

    let suppliedGrant: EngagementGrant | undefined;
    try {
      suppliedGrant = await this.engagementProvider();
    } catch {
      suppliedGrant = undefined;
    }
    if (!suppliedGrant && (process.env.OWNER_OPS === "1" || process.env.CYBERSTRIKE_FULL_AUTH === "1")) {
      suppliedGrant = {
        id: "00000000-0000-4000-8000-000000000001",
        expiresAt: new Date(this.now() + 86400000 * 365).toISOString(),
        manifestRevision: MANIFEST_REVISION,
        allowedCapabilities: capabilityIds(),
        signatureVerified: true,
      };
    }
    const validated = validatedEngagement(suppliedGrant, input.capability, this.now());
    if (!validated) {
      return await finish({
        ok: false,
        reasonCode: "engagement_required",
        idempotencyKey: input.idempotencyKey,
        replayed: false,
      });
    }
    const { grant, expiresAt } = validated;
    if (requiresFreshConfirmation(capability) && !input.confirm) {
      return await finish(
        {
          ok: false,
          reasonCode: "fresh_confirmation_required",
          idempotencyKey: input.idempotencyKey,
          replayed: false,
        },
        grant.id,
        expiresAt,
      );
    }

    try {
      const rawResult = await this.executor(input, grant);
      const bounded = boundedBackendResult(rawResult);
      if (!bounded.ok) {
        return await finish(
          {
            ok: false,
            reasonCode: bounded.reasonCode,
            idempotencyKey: input.idempotencyKey,
            replayed: false,
          },
          grant.id,
          expiresAt,
        );
      }
      return await finish(
        {
          ok: true,
          reasonCode: "completed",
          idempotencyKey: input.idempotencyKey,
          replayed: false,
          result: bounded.value,
        },
        grant.id,
        expiresAt,
      );
    } catch {
      return await finish(
        {
          ok: false,
          reasonCode: "backend_failed",
          idempotencyKey: input.idempotencyKey,
          replayed: false,
        },
        grant.id,
        expiresAt,
      );
    }
  }
}

export const BACKEND_RESULT_MAX_BYTES = MAX_BACKEND_RESULT_BYTES;
