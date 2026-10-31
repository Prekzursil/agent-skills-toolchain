export const JOURNAL_VERSION = 2;
export function createJournal(root) {
  const records = new Map();
  return {
    append(key, item) {
      if (records.has(key)) {
        throw new Error("duplicate key: " + key);
      }
      records.set(key, item);
      return records.size;
    },
    flush() {
      const out = {};
      for (const [key, item] of records) {
        out[key] = item;
      }
      return out;
    },
  };
}
