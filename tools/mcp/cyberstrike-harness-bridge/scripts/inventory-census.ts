import { canonicalJson } from "../src/canonical-json.ts";
import {
  BACKEND_DEFINITIONS,
  calculatedPolicyOverlayHashes,
  verifyInventoryPins,
} from "../src/manifest.ts";

const calculated = calculatedPolicyOverlayHashes();
const census = {
  backends: BACKEND_DEFINITIONS.map((backend) => ({
    id: backend.id,
    expectedToolCount: backend.expectedToolCount,
    upstreamWireSchemaSha256: backend.upstreamWireSchemaSha256,
    pinnedPolicyOverlaySha256: backend.policyOverlaySha256,
    calculatedPolicyOverlaySha256: calculated[backend.id],
  })),
  mismatches: verifyInventoryPins(),
};

process.stdout.write(`${canonicalJson(census)}\n`);
if (census.mismatches.length > 0) process.exitCode = 1;
