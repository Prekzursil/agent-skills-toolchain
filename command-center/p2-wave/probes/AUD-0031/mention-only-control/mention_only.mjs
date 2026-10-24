/**
 * AUD-0031 use-vs-mention control.
 *
 * This file NAMEs tools/lib modules only inside a block comment and a line
 * comment. It must NOT count as a consumer of any salvaged module.
 *
 * Mentioned (must NOT count):
 *   tools/lib/security.mjs
 *   @prekzursil/tools-lib/security
 *   tools/lib/workspace.mjs
 *   tools/lib/git-diff.mjs
 *   tools/lib/handled-ledger.mjs
 *   tools/lib/net-allowlist.mjs
 *   tools/lib/codex-invocation.mjs
 */
// import { isPathWithin } from '@prekzursil/tools-lib/security';
// import { detectWorkspaceRoot } from '../tools/lib/workspace.mjs';

export const AUD0031_MENTION_ONLY = true;
export function ping() {
  return "mention-only-control-alive";
}
