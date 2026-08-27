import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer({
  name: "deepscan",
  version: "0.1.0",
});

function resolveJavaBin() {
  return process.env.DEEPSCAN_JAVA_BIN?.trim() || "java";
}

function resolveJarPath(override) {
  return (override || process.env.DEEPSCAN_CLI_JAR || "").trim();
}

function resolveLicensePath(override) {
  return (override || process.env.DEEPSCAN_LICENSE_PATH || "").trim();
}

function checkJava(javaBin) {
  const res = spawnSync(javaBin, ["-version"], { encoding: "utf8", timeout: 20_000 });
  return {
    ok: (res.status ?? 1) === 0,
    stdout: res.stdout ?? "",
    stderr: res.stderr ?? (res.error ? String(res.error.message ?? res.error) : ""),
  };
}

function deepscanStatus(jarPath) {
  const javaBin = resolveJavaBin();
  const java = checkJava(javaBin);
  return {
    javaBin,
    javaOk: java.ok,
    javaStdout: java.stdout,
    javaStderr: java.stderr,
    jarPath,
    jarPresent: Boolean(jarPath) && existsSync(jarPath),
    licensePath: resolveLicensePath(),
    licensePresent: Boolean(resolveLicensePath()) && existsSync(resolveLicensePath()),
    blocked:
      !java.ok || !jarPath || !existsSync(jarPath),
    reason:
      !java.ok
        ? "java runtime not available"
        : !jarPath
          ? "DEEPSCAN_CLI_JAR is not configured"
          : !existsSync(jarPath)
            ? "configured DeepScan CLI JAR path does not exist"
            : null,
  };
}

function runDeepScan({ targetPath, format = "json", quiet = true, ignoreRules = [], ignorePatterns = [], top, licensePath, jarPathOverride }) {
  const jarPath = resolveJarPath(jarPathOverride);
  const status = deepscanStatus(jarPath);
  if (status.blocked) {
    return {
      ...status,
      ok: false,
      exitCode: null,
      stdout: "",
      stderr: "",
      command: null,
    };
  }

  const javaBin = resolveJavaBin();
  const cmd = ["-jar", jarPath, targetPath, "-f", format];
  if (quiet) cmd.push("-q");
  if (top) cmd.push("-t", String(top));
  if (ignoreRules.length) cmd.push("--ignore-rules", ignoreRules.join(","));
  if (ignorePatterns.length) cmd.push("--ignore-patterns", ignorePatterns.join(","));
  const resolvedLicense = resolveLicensePath(licensePath);
  if (resolvedLicense) cmd.push("--license", resolvedLicense);

  const res = spawnSync(javaBin, cmd, {
    encoding: "utf8",
    timeout: 120_000,
  });

  return {
    ...status,
    ok: (res.status ?? 1) === 0,
    exitCode: res.status ?? 1,
    stdout: res.stdout ?? "",
    stderr: res.stderr ?? (res.error ? String(res.error.message ?? res.error) : ""),
    timedOut: res.error?.code === "ETIMEDOUT",
    command: [javaBin, ...cmd],
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
  "deepscan_status",
  "Check whether the local DeepScan CLI runtime is available. Requires Java and a configured DEEPSCAN_CLI_JAR path.",
  {
    jar_path: z.string().optional().describe("Optional explicit path to the DeepScan CLI JAR"),
  },
  async ({ jar_path }) => textResult(deepscanStatus(resolveJarPath(jar_path))),
);

server.tool(
  "deepscan_analyze",
  "Run the DeepScan Enterprise CLI JAR against a path in read-only mode. Returns JSON/CSV/HTML output from the local JAR.",
  {
    target_path: z.string().describe("Folder or file path to analyze"),
    format: z.enum(["csv", "html", "json"]).optional(),
    quiet: z.boolean().optional(),
    top: z.number().int().positive().optional(),
    ignore_rules: z.array(z.string()).optional(),
    ignore_patterns: z.array(z.string()).optional(),
    jar_path: z.string().optional().describe("Optional explicit path to the DeepScan CLI JAR"),
    license_path: z.string().optional().describe("Optional explicit DeepScan license file path"),
  },
  async ({ target_path, format, quiet, top, ignore_rules, ignore_patterns, jar_path, license_path }) =>
    textResult(
      runDeepScan({
        targetPath: target_path,
        format,
        quiet: quiet ?? true,
        top,
        ignoreRules: ignore_rules ?? [],
        ignorePatterns: ignore_patterns ?? [],
        licensePath: license_path,
        jarPathOverride: jar_path,
      }),
    ),
);

const transport = new StdioServerTransport();
await server.connect(transport);
