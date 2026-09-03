export const AGPL_BOUNDARY_CENSUS = Object.freeze({
  version: 1,
  privateGatewayLicenseBoundary: "independently-authored-license-neutral-process",
  cyberStrikeBoundary: "external-process",
  gatewayImportsCyberStrike: false,
  forbiddenPackageScopes: ["@cyberstrike-io/"],
  externalAgplArtifacts: [
    Object.freeze({ name: "@cyberstrike-io/cyberstrike", version: "1.1.16", location: "outside-repository" }),
    Object.freeze({ name: "@cyberstrike-io/plugin", version: "1.1.16", location: "external-plugin-only" }),
    Object.freeze({ name: "@cyberstrike-io/sdk", version: "1.1.16", location: "external-plugin-only" }),
  ],
});

type CensusInput = { packageJson: string; sources: readonly string[] };

export function censusAgplBoundary(input: CensusInput): Array<{ code: string; subject: string }> {
  const violations: Array<{ code: string; subject: string }> = [];
  let manifest: Record<string, any>;
  try {
    manifest = JSON.parse(input.packageJson);
  } catch {
    return [{ code: "invalid_package_manifest", subject: "package.json" }];
  }
  for (const section of ["dependencies", "devDependencies", "optionalDependencies", "peerDependencies"]) {
    for (const name of Object.keys(manifest[section] ?? {})) {
      if (name.startsWith("@cyberstrike-io/")) {
        violations.push({ code: "forbidden_cyberstrike_dependency", subject: name });
      }
    }
  }
  const importPattern = /(?:from\s*|import\s*\(|require\s*\()\s*["'](@cyberstrike-io\/[^"']+)["']/gu;
  for (const source of input.sources) {
    for (const match of source.matchAll(importPattern)) {
      violations.push({ code: "forbidden_cyberstrike_import", subject: match[1] });
    }
  }
  return violations.sort((left, right) =>
    `${left.code}:${left.subject}`.localeCompare(`${right.code}:${right.subject}`),
  );
}
