// Salvaged tools/lib module: default-deny host allowlist (distinct mechanism).
const DEFAULT_DENY = true;

function hostKey(raw) {
  return String(raw).trim().toLowerCase();
}

export function createNetAllowlist(seeds) {
  const allowed = new Set((seeds || []).map(hostKey).filter(Boolean));
  return { allowed, defaultDeny: DEFAULT_DENY };
}

export function allowHost(list, host) {
  const key = hostKey(host);
  if (!key) throw new Error("empty-host");
  list.allowed.add(key);
  return key;
}

export function isHostAllowed(list, host) {
  const key = hostKey(host);
  if (list.allowed.has(key)) return true;
  return list.defaultDeny ? false : true;
}

export function assertAllowed(list, host) {
  if (!isHostAllowed(list, host)) {
    throw new Error("net-allowlist-denied");
  }
  return hostKey(host);
}
