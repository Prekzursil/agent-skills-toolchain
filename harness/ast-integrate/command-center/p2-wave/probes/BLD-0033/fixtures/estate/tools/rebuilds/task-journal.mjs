// Planted rebuild: SAME MECHANISM as tools/lib/handled-ledger.mjs, new filename
// and renamed exports. Filename/token search must miss; shingles must catch.
const encoder = new TextEncoder();

function freezeShape(rec) {
  return JSON.stringify({
    id: String(rec.id),
    ts: Number(rec.ts),
    bytes: Number(rec.bytes),
    sha256: String(rec.sha256),
  });
}

export function makeTaskJournal() {
  return { records: [], index: new Map(), tailSha: "GENESIS" };
}

export function pushClosedRecord(book, rec) {
  const id = String(rec.id);
  if (book.index.has(id)) {
    throw new Error("duplicate-handled-id");
  }
  const canonical = freezeShape(rec);
  const row = Object.freeze({
    id,
    ts: Number(rec.ts),
    bytes: Number(rec.bytes),
    sha256: String(rec.sha256),
    prev: book.tailSha,
    canonical,
  });
  book.records.push(row);
  book.index.set(id, book.records.length - 1);
  book.tailSha = row.sha256;
  encoder.encode(canonical);
  return row;
}

export function findClosedRecord(book, id) {
  const i = book.index.get(String(id));
  if (i === undefined) return null;
  return book.records[i];
}

export function closedRecordBytes(book) {
  return book.records.reduce((n, r) => n + Number(r.bytes), 0);
}
