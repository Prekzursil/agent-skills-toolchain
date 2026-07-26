// Concrete Node primitives injected into the pure policy modules. This file is
// the process/filesystem/network boundary; it is exercised only through the
// index/verify-citation entrypoints and is deliberately excluded from the unit
// coverage denominator (see README.md "Coverage scope").

import { execFile } from "node:child_process";
import { promises as fsp } from "node:fs";
import { lookup } from "node:dns/promises";
import { randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import type { CorpusFs, ExecFn, GitFn } from "./corpus.js";
import type { HttpResponse, VerifyDeps } from "./verify.js";
import { SEARCH_TIMEOUT_MS, VERIFY_MAX_RESPONSE_BYTES } from "./limits.js";

export const realExec: ExecFn = (file, args, opts) =>
  new Promise((res) => {
    execFile(
      file,
      args,
      {
        timeout: opts.timeout,
        maxBuffer: opts.maxBuffer,
        cwd: opts.cwd,
        windowsHide: true,
      },
      (err, stdout) => {
        const out = typeof stdout === "string" ? stdout : "";
        if (err) {
          const e = err as NodeJS.ErrnoException & {
            killed?: boolean;
            signal?: string;
          };
          res({
            stdout: out,
            exitCode: typeof e.code === "number" ? e.code : null,
            timedOut: e.killed === true || e.signal === "SIGTERM",
            bufferExceeded: e.code === "ERR_CHILD_PROCESS_STDIO_MAXBUFFER",
            spawnError: e.code === "ENOENT" ? "ripgrep not found" : null,
          });
          return;
        }
        res({
          stdout: out,
          exitCode: 0,
          timedOut: false,
          bufferExceeded: false,
          spawnError: null,
        });
      },
    );
  });

export const realGit: GitFn = (root, args) =>
  new Promise((res) => {
    execFile(
      "git",
      ["-C", root, ...args],
      { maxBuffer: 4 * 1024 * 1024, windowsHide: true },
      (err, stdout) => {
        if (err) {
          res({ ok: false, message: String(err.message) });
          return;
        }
        res({ ok: true, stdout: typeof stdout === "string" ? stdout : "" });
      },
    );
  });

export const realFs: CorpusFs = {
  async pathExists(path) {
    try {
      await fsp.access(path);
      return true;
    } catch {
      return false;
    }
  },
  async realpath(path) {
    return fsp.realpath(path);
  },
  async statFile(path) {
    try {
      const stat = await fsp.stat(path);
      return { isDirectory: stat.isDirectory(), size: stat.size };
    } catch {
      return null;
    }
  },
  async readTextFile(path) {
    return fsp.readFile(path, "utf8");
  },
  async listDir(path) {
    try {
      const entries = await fsp.readdir(path, { withFileTypes: true });
      return entries.map((entry) => ({
        name: entry.name,
        isDirectory: entry.isDirectory(),
      }));
    } catch {
      return [];
    }
  },
};

export function resolveCorpusRoot(
  env: NodeJS.ProcessEnv,
  moduleUrl: string,
): string {
  const override = env["HACKTRICKS_CORPUS"];
  if (override !== undefined && override !== "") {
    return override;
  }
  const here = dirname(fileURLToPath(moduleUrl));
  return resolve(here, "..", "hacktricks");
}

export function defaultToolDeps(): {
  exec: ExecFn;
  git: GitFn;
  fs: CorpusFs;
  now: () => Date;
  newId: () => string;
} {
  return {
    exec: realExec,
    git: realGit,
    fs: realFs,
    now: () => new Date(),
    newId: () => randomUUID(),
  };
}

export function realVerifyDeps(): VerifyDeps {
  return {
    now: () => new Date(),
    resolveIps: async (hostname) => {
      const records = await lookup(hostname, { all: true });
      return records.map((record) => record.address);
    },
    fetchNoRedirect: async (url): Promise<HttpResponse> => {
      const controller = new AbortController();
      const timer = setTimeout(() => {
        controller.abort();
      }, SEARCH_TIMEOUT_MS);
      try {
        const response = await fetch(url, {
          redirect: "manual",
          signal: controller.signal,
        });
        const buffer = await response.arrayBuffer();
        const body = Buffer.from(buffer)
          .subarray(0, VERIFY_MAX_RESPONSE_BYTES)
          .toString("utf8");
        return {
          status: response.status,
          location: response.headers.get("location"),
          body,
        };
      } finally {
        clearTimeout(timer);
      }
    },
  };
}
