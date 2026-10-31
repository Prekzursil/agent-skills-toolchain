export const LEDGER_VERSION = 2;
export function createLedger(root) {
  const entries = new Map();
  return {
    append(key, value) {
      if (entries.has(key)) {
        throw new Error("duplicate key: " + key);
      }
      entries.set(key, value);
      return entries.size;
    },
    flush() {
      const out = {};
      for (const [key, value] of entries) {
        out[key] = value;
      }
      return out;
    },
  };
}
