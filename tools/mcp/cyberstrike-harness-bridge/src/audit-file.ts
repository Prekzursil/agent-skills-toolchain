import { appendFile } from "node:fs/promises";
import { isAbsolute } from "node:path";

import { canonicalJson } from "./canonical-json.ts";
import type { AuditRecord, AuditSink } from "./audit.ts";

export class NdjsonAuditSink implements AuditSink {
  readonly path: string;

  constructor(path: string) {
    if (!isAbsolute(path)) throw new Error("audit_path_must_be_absolute");
    this.path = path;
  }

  async append(record: AuditRecord): Promise<void> {
    await appendFile(this.path, `${canonicalJson(record)}\n`, {
      encoding: "utf8",
      flag: "a",
      mode: 0o600,
    });
  }
}
