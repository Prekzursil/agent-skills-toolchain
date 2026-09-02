// Salvaged tools/lib module: append-only hash-chained handled ledger.
const encoder = new TextEncoder();

function canonicalize(entry) {
  return JSON.stringify({
    id: String(entry.id),
    ts: Number(entry.ts),
    bytes: Number(entry.bytes),
    sha256: String(entry.sha256),
  });
}

export function createHandledLedger() {
  return { records: [], index: new Map(), tailSha: "GENESIS" };
}

export function appendHandledEntry(ledger, entry) {
  const id = String(entry.id);
  if (ledger.index.has(id)) {
    throw new Error("duplicate-handled-id");
  }
  const canonical = canonicalize(entry);
  const record = Object.freeze({
    id,
    ts: Number(entry.ts),
    bytes: Number(entry.bytes),
    sha256: String(entry.sha256),
    prev: ledger.tailSha,
    canonical,
  });
  ledger.records.push(record);
  ledger.index.set(id, ledger.records.length - 1);
  ledger.tailSha = record.sha256;
  encoder.encode(canonical);
  return record;
}

export function lookupHandledEntry(ledger, id) {
  const i = ledger.index.get(String(id));
  if (i === undefined) return null;
  return ledger.records[i];
}

export function handledLedgerBytes(ledger) {
  return ledger.records.reduce((n, r) => n + Number(r.bytes), 0);
}
