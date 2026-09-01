import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer({
  name: "qlty",
  version: "0.1.0",
});

const DEFAULT_QLTY_BIN = String.raw`C:\Users\Prekzursil\.cargo\bin\qlty.exe`;

function resolveQltyBin() {
  return process.env.QLTY_BIN?.trim() || DEFAULT_QLTY_BIN;
}

function safeRepoInfo(repoDir) {
  if (!repoDir) return { repoDir: null, qltyConfig: false };
  return {
    repoDir,
    qltyConfig: existsSync(join(repoDir, ".qlty", "qlty.toml")),
  };
}

function runQlty(args, repoDir) {
  const bin = resolveQltyBin();
  if (!existsSync(bin)) {
    return {
      ok: false,
      blocked: true,
      reason: "qlty binary not found",
      binary: bin,
      command: [bin, ...args],
      exitCode: null,
      stdout: "",
      stderr: "",
      ...safeRepoInfo(repoDir),
    };
  }

  const result = spawnSync(bin, ["--no-upgrade-check", ...args], {
    cwd: repoDir || process.cwd(),
    encoding: "utf8",
    timeout: 120_000,
  });

  return {
    ok: (result.status ?? 1) === 0,
    blocked: false,
    binary: bin,
    command: [bin, "--no-upgrade-check", ...args],
    exitCode: result.status ?? 1,
    stdout: result.stdout ?? "",
    stderr: result.stderr ?? (result.error ? String(result.error.message ?? result.error) : ""),
    timedOut: result.error?.code === "ETIMEDOUT",
    ...safeRepoInfo(repoDir),
  };
}

function textResult(payload) {
  return {
    content: [
      {
        type: "text",
        text: JSON.stringify(payload, null, 2),
      },
    ],
  };
}

server.tool(
  "qlty_status",
  "Check the local QLTY CLI runtime and repo-level QLTY config presence.",
  {
    repo_dir: z.string().optional().describe("Optional repository directory to inspect for .qlty/qlty.toml"),
  },
  async ({ repo_dir }) => {
    const version = runQlty(["version"], repo_dir);
    return textResult(version);
  },
);

server.tool(
  "qlty_check",
  "Run `qlty check` in read-only mode. This wrapper never enables --fix or AI fixes.",
  {
    repo_dir: z.string().optional(),
    paths: z.array(z.string()).optional(),
    all: z.boolean().optional(),
    level: z.enum(["note", "fmt", "low", "medium", "high"]).optional(),
    fail_level: z.enum(["note", "fmt", "low", "medium", "high"]).optional(),
    filter: z.string().optional(),
    upstream: z.string().optional(),
    summary: z.boolean().optional(),
    no_cache: z.boolean().optional(),
    jobs: z.number().int().positive().optional(),
    verbose: z.boolean().optional(),
    print_errors: z.boolean().optional(),
  },
  async (args) => {
    const cmd = ["check", "--no-progress"];
    if (args.all) cmd.push("--all");
    if (args.level) cmd.push("--level", args.level);
    if (args.fail_level) cmd.push("--fail-level", args.fail_level);
    if (args.filter) cmd.push("--filter", args.filter);
    if (args.upstream) cmd.push("--upstream", args.upstream);
    if (args.summary) cmd.push("--summary");
    if (args.no_cache) cmd.push("--no-cache");
    if (args.jobs) cmd.push("--jobs", String(args.jobs));
    if (args.verbose) cmd.push("--verbose");
    if (args.print_errors) cmd.push("--print-errors");
    if (args.paths?.length) cmd.push(...args.paths);
    return textResult(runQlty(cmd, args.repo_dir));
  },
);

server.tool(
  "qlty_smells",
  "Run `qlty smells` in read-only mode.",
  {
    repo_dir: z.string().optional(),
    paths: z.array(z.string()).optional(),
    all: z.boolean().optional(),
    no_duplication: z.boolean().optional(),
    include_tests: z.boolean().optional(),
    no_snippets: z.boolean().optional(),
    upstream: z.string().optional(),
    quiet: z.boolean().optional(),
  },
  async (args) => {
    const cmd = ["smells"];
    if (args.all) cmd.push("--all");
    if (args.no_duplication) cmd.push("--no-duplication");
    if (args.include_tests) cmd.push("--include-tests");
    if (args.no_snippets) cmd.push("--no-snippets");
    if (args.upstream) cmd.push("--upstream", args.upstream);
    if (args.quiet) cmd.push("--quiet");
    if (args.paths?.length) cmd.push(...args.paths);
    return textResult(runQlty(cmd, args.repo_dir));
  },
);

server.tool(
  "qlty_metrics",
  "Run `qlty metrics` in read-only mode.",
  {
    repo_dir: z.string().optional(),
    paths: z.array(z.string()).optional(),
    all: z.boolean().optional(),
    dirs: z.boolean().optional(),
    functions: z.boolean().optional(),
    max_depth: z.number().int().positive().optional(),
    sort: z.enum(["name", "classes", "functions", "fields", "lines", "loc", "complexity", "lcom"]).optional(),
    limit: z.number().int().positive().optional(),
    exclude_tests: z.boolean().optional(),
    upstream: z.string().optional(),
    quiet: z.boolean().optional(),
  },
  async (args) => {
    const cmd = ["metrics"];
    if (args.all) cmd.push("--all");
    if (args.dirs) cmd.push("--dirs");
    if (args.functions) cmd.push("--functions");
    if (args.max_depth) cmd.push("--max-depth", String(args.max_depth));
    if (args.sort) cmd.push("--sort", args.sort);
    if (args.limit) cmd.push("--limit", String(args.limit));
    if (args.exclude_tests) cmd.push("--exclude-tests");
    if (args.upstream) cmd.push("--upstream", args.upstream);
    if (args.quiet) cmd.push("--quiet");
    if (args.paths?.length) cmd.push(...args.paths);
    return textResult(runQlty(cmd, args.repo_dir));
  },
);

server.tool(
  "qlty_coverage_transform",
  "Run `qlty coverage transform` in read-only mode and print the transformed coverage output.",
  {
    repo_dir: z.string().optional(),
    path: z.string().describe("Coverage report path, optionally prefixed with the format, e.g. lcov:coverage/lcov.info"),
    report_format: z.enum(["simplecov", "clover", "cobertura", "coverprofile", "lcov", "jacoco", "qlty"]).optional(),
    add_prefix: z.string().optional(),
    strip_prefix: z.string().optional(),
    quiet: z.boolean().optional(),
    dry_run: z.boolean().optional(),
  },
  async (args) => {
    const cmd = ["coverage", "transform", args.path, "--print"];
    if (args.report_format) cmd.push("--report-format", args.report_format);
    if (args.add_prefix) cmd.push("--add-prefix", args.add_prefix);
    if (args.strip_prefix) cmd.push("--strip-prefix", args.strip_prefix);
    if (args.quiet) cmd.push("--quiet");
    if (args.dry_run) cmd.push("--dry-run");
    return textResult(runQlty(cmd, args.repo_dir));
  },
);

const transport = new StdioServerTransport();
await server.connect(transport);
