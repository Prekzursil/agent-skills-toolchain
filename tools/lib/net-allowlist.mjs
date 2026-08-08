// ORIGIN: tools/web/agentify-desktop/http-api.mjs:6-29 (extracted; the other ~16 KB of that file
// was the Electron sidecar's local HTTP server and was retired with it).
//
// SURVIVED THE RETIREMENT because it is a self-contained remote-address allowlist with no HTTP
// coupling at all - ~25 lines usable by any loopback-bound local server (mcp-http-host,
// agent-mail on 127.0.0.1:8812). It handles the two things hand-rolled checks get wrong:
// the '::ffff:' IPv4-mapped-IPv6 prefix, and IPv6 unique-local (fc00::/7) addresses.
//
// Carried over verbatim apart from exporting the two helpers (they were module-private) so they
// can be tested directly. No behaviour change.

export function normalizeRemoteAddress(remoteAddress) {
  const raw = String(remoteAddress || '').trim();
  if (!raw) return '';
  return raw.startsWith('::ffff:') ? raw.slice('::ffff:'.length) : raw;
}

export function isPrivateIpv4(address) {
  if (!address.includes('.')) return false;
  const parts = address.split('.').map((part) => Number(part));
  if (parts.length !== 4 || parts.some((part) => !Number.isInteger(part) || part < 0 || part > 255)) return false;
  if (parts[0] === 10) return true;
  if (parts[0] === 192 && parts[1] === 168) return true;
  if (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31) return true;
  return false;
}

/**
 * Loopback is always allowed. Everything else requires the caller to opt in explicitly via
 * allowPrivateNetwork - the default is deny, which is the property that makes this safe to reuse.
 */
export function isAllowedRemoteAddress(remoteAddress, { allowPrivateNetwork = false } = {}) {
  const a = normalizeRemoteAddress(remoteAddress);
  if (!a) return false;
  if (a === '127.0.0.1' || a === '::1') return true;
  if (!allowPrivateNetwork) return false;
  if (isPrivateIpv4(a)) return true;
  return a.startsWith('fc') || a.startsWith('fd');
}
