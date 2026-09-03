import {
  arrayOf,
  boolean,
  enumeration,
  integer,
  number,
  objectSchema,
  text,
  type JsonSchema,
} from "./schema.ts";

export type RiskClass = "read" | "authorized_read" | "write" | "external_submission" | "high_risk";

export type SecurityCapability = Readonly<{
  id: string;
  backendId: string;
  upstreamToolName: string;
  inputSchema: JsonSchema;
  riskClass: RiskClass;
  available: false;
  unavailableReason: "windows_job_object_containment_unverified";
  permanentlyDenied: boolean;
  denyReason?: string;
}>;

type Spec = readonly [
  name: string,
  schema: JsonSchema,
  risk?: RiskClass,
  denyReason?: string,
];

const S = text();
const SHORT = text(500);
const LONG = text(10_000);
const CVE = text(64, { pattern: "^CVE-[0-9]{4}-[0-9]{4,}$" });
const CVE_LIST = text(4096, { pattern: "^CVE-[0-9]{4}-[0-9]{4,}(\\s*,\\s*CVE-[0-9]{4}-[0-9]{4,})*$" });
const LIMIT = integer(1, 100);
const MSF_LIMIT = integer(1, 1000);
const OFFSET = integer(0, 1000);

function makeCapabilities(backendId: string, specs: readonly Spec[]): SecurityCapability[] {
  return specs.map(([upstreamToolName, inputSchema, riskClass = "authorized_read", denyReason]) =>
    Object.freeze({
      id: `${backendId}.${upstreamToolName}`,
      backendId,
      upstreamToolName,
      inputSchema,
      riskClass,
      available: false as const,
      unavailableReason: "windows_job_object_containment_unverified" as const,
      permanentlyDenied: Boolean(denyReason),
      ...(denyReason ? { denyReason } : {}),
    }),
  );
}

const region = objectSchema({ region: S });
const resourceGroup = objectSchema({ resourceGroup: S });
const empty = objectSchema();

const cloudAuditSpecs: Spec[] = [
  ["aws_check_s3_public", objectSchema({ region: S, bucketName: S })],
  ["aws_check_s3_objects", objectSchema({ region: S, bucketName: S, maxObjects: integer(1, 10_000) })],
  ["aws_check_iam_policies", region],
  ["aws_check_ec2_imds", region],
  ["aws_check_ec2_snapshots", region],
  ["aws_check_ec2_security_groups", region],
  ["aws_check_lambda_env", region],
  ["aws_check_lambda_permissions", region],
  ["aws_check_ecr_images", region],
  ["aws_check_secrets_manager", region],
  ["aws_check_dynamodb", region],
  ["aws_check_api_gateway", region],
  ["aws_check_sagemaker", region],
  ["azure_check_storage_public", resourceGroup],
  ["azure_check_storage_sas", resourceGroup],
  ["azure_check_automation", resourceGroup],
  ["azure_check_vm_network", resourceGroup],
  ["azure_check_vm_encryption", resourceGroup],
  ["azure_check_vm_identity", resourceGroup],
  ["azure_check_ad_consent", empty],
  ["azure_check_logic_apps", resourceGroup],
  ["azure_check_functions", resourceGroup],
  ["azure_check_keyvault", resourceGroup],
  ["azure_check_acr", resourceGroup],
  ["azure_check_sql", resourceGroup],
  ["azure_check_webapp", resourceGroup],
  ["gcp_check_gcs_public", empty],
  ["gcp_check_gcs_objects", objectSchema({ bucketName: S, maxObjects: integer(1, 10_000) })],
  ["gcp_check_metadata", objectSchema({ zone: S })],
  ["gcp_check_iam_keys", empty],
  ["gcp_check_iam_delegation", empty],
  ["gcp_check_iam_compute", empty],
  ["gcp_check_kubernetes", objectSchema({ location: S })],
  ["gcp_check_gcr", empty],
  ["cloud_list_checks", objectSchema({ provider: enumeration(["aws", "azure", "gcp"]), severity: enumeration(["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]), priority: enumeration(["P0", "P1", "P2"]) })],
  ["cloud_audit_summary", empty],
  ["cloud_audit_report", objectSchema({ title: text(512), format: enumeration(["markdown", "json"]), severityFilter: arrayOf(text(16), 5) })],
  ["cloud_run_all", objectSchema({ provider: enumeration(["aws", "azure", "gcp"]), region: S }, ["provider"])],
];

const orgRequired = objectSchema({ org: S }, ["org"]);
const repoRequired = objectSchema({ owner: S, repo: S }, ["owner", "repo"]);
const githubSpecs: Spec[] = [
  ["github_check_org_security", orgRequired],
  ["github_check_org_sso", orgRequired],
  ["github_check_org_members", orgRequired],
  ["github_check_org_apps", orgRequired],
  ["github_check_org_webhooks", orgRequired],
  ["github_check_org_audit_log", orgRequired],
  ["github_list_org_repos", objectSchema({ org: S, type: enumeration(["all", "public", "private", "forks", "sources"]) }, ["org"])],
  ["github_check_repo_branch_protection", repoRequired],
  ["github_check_repo_secrets", repoRequired],
  ["github_check_repo_code_scanning", repoRequired],
  ["github_check_repo_dependabot", repoRequired],
  ["github_check_repo_settings", repoRequired],
  ["github_check_repo_webhooks", repoRequired],
  ["github_check_repo_deploy_keys", repoRequired],
  ["github_check_repo_codeowners", repoRequired],
  ["github_check_workflow_injection", repoRequired],
  ["github_check_workflow_pr_target", repoRequired],
  ["github_check_workflow_permissions", repoRequired],
  ["github_check_workflow_pinning", repoRequired],
  ["github_check_workflow_runners", objectSchema({ org: S, owner: S, repo: S })],
  ["github_check_workflow_environments", repoRequired],
  ["github_check_workflow_secrets", repoRequired],
  ["github_check_workflow_oidc", repoRequired],
  ["github_check_secret_scanning", repoRequired],
  ["github_check_push_protection", repoRequired],
  ["github_check_secret_patterns", orgRequired],
  ["github_check_secret_scoping", repoRequired],
  ["github_check_dependency_graph", repoRequired],
  ["github_check_dependabot_updates", repoRequired],
  ["github_check_sbom", repoRequired],
  ["github_check_vulnerabilities", repoRequired],
  ["github_check_team_permissions", objectSchema({ org: S, repo: S }, ["org"])],
  ["github_check_collaborators", repoRequired],
  ["github_check_app_permissions", repoRequired],
  ["github_check_pat_usage", orgRequired],
  ["github_list_checks", objectSchema({ category: S, severity: S })],
  ["github_audit_summary", empty],
  ["github_audit_report", objectSchema({ title: text(512), format: enumeration(["markdown", "json"]), severityFilter: arrayOf(text(16), 5) })],
  ["github_run_all", objectSchema({ org: S, owner: S, repo: S })],
];

const cveIdRequired = objectSchema({ cveId: CVE }, ["cveId"]);
const idRequired = objectSchema({ id: SHORT }, ["id"]);
const cveSpecs: Spec[] = [
  ["nvd_search", objectSchema({ keyword: S, severity: enumeration(["CRITICAL", "HIGH", "MEDIUM", "LOW"]), cweId: text(32), startDate: text(64), endDate: text(64), limit: LIMIT })],
  ["nvd_get", cveIdRequired],
  ["nvd_recent", objectSchema({ days: integer(1, 120), severity: enumeration(["CRITICAL", "HIGH", "MEDIUM", "LOW"]), limit: LIMIT })],
  ["epss_score", objectSchema({ cve: CVE_LIST }, ["cve"])],
  ["epss_top", objectSchema({ limit: LIMIT, minScore: number(0, 1) })],
  ["kev_check", objectSchema({ cve: CVE_LIST }, ["cve"])],
  ["kev_search", objectSchema({ query: S, vendor: S, product: S, limit: LIMIT })],
  ["kev_recent", objectSchema({ days: integer(1, 3650), limit: LIMIT })],
  ["ghsa_search", objectSchema({ keyword: SHORT, ecosystem: enumeration(["npm", "pip", "maven", "nuget", "rubygems", "go", "composer", "rust", "pub", "erlang", "actions", "swift"]), severity: enumeration(["critical", "high", "medium", "low"]), limit: LIMIT })],
  ["ghsa_get", idRequired],
  ["osv_query", objectSchema({ package: S, version: SHORT, ecosystem: enumeration(["npm", "PyPI", "Go", "Maven", "NuGet", "Packagist", "RubyGems", "crates.io", "Hex", "Pub"]) }, ["package", "version", "ecosystem"])],
  ["osv_get", idRequired],
  ["osv_batch", objectSchema({ queries: arrayOf(objectSchema({ package: S, version: SHORT, ecosystem: S }, ["package", "version", "ecosystem"]), 100, 1) }, ["queries"])],
  ["exploit_search", objectSchema({ cve: CVE }, ["cve"])],
  ["cve_enrich", cveIdRequired],
  ["cve_prioritize", objectSchema({ cves: arrayOf(CVE, 100, 1) }, ["cves"])],
  ["cve_list_sources", empty],
  ["cve_report", objectSchema({ cves: arrayOf(CVE, 100, 1), title: text(512) }, ["cves"])],
  ["cve_by_product", objectSchema({ keyword: S, limit: LIMIT }, ["keyword"])],
  ["cwe_lookup", objectSchema({ id: text(32), query: S })],
  ["cvss_parse", objectSchema({ vector: text(512) }, ["vector"])],
  ["cve_trending", objectSchema({ limit: LIMIT, minEpss: number(0, 1) })],
  ["cve_compare", objectSchema({ cve1: CVE, cve2: CVE }, ["cve1", "cve2"])],
  ["shodan_cve", cveIdRequired],
  ["shodan_product", objectSchema({ product: S, count: LIMIT, is_kev: boolean() }, ["product"])],
  ["shodan_ip_vulns", objectSchema({ ip: text(45) }, ["ip"]), "authorized_read"],
  ["vulncheck_kev", objectSchema({ cve: CVE }, ["cve"])],
  ["vulncheck_cpe", objectSchema({ cpe: text(4096) }, ["cpe"])],
  ["vulncheck_purl", objectSchema({ purl: text(4096) }, ["purl"])],
  ["vulners_lookup", cveIdRequired],
  ["vulners_search", objectSchema({ query: S, limit: LIMIT, type: SHORT }, ["query"])],
  ["nuclei_check", cveIdRequired],
  ["msf_check", cveIdRequired],
  ["cpe_search", objectSchema({ keyword: S, limit: LIMIT }, ["keyword"])],
  ["cpe_match", objectSchema({ cveId: CVE, limit: LIMIT }, ["cveId"])],
  ["circl_cve", cveIdRequired],
  ["attackerkb_assess", cveIdRequired],
  ["cve_to_attack", objectSchema({ cweIds: arrayOf(text(32), 100, 1) }, ["cweIds"])],
  ["cwe_get", objectSchema({ id: text(32) }, ["id"])],
  ["cwe_hierarchy", objectSchema({ id: text(32) }, ["id"])],
  ["cwe_top25", objectSchema({ year: integer(1999, 2100) })],
];

const domainRequired = objectSchema({ domain: S }, ["domain"]);
const ipRequired = objectSchema({ ip: text(45) }, ["ip"]);
const osintSpecs: Spec[] = [
  ["dns_lookup", objectSchema({ domain: S, type: enumeration(["A", "AAAA", "MX", "TXT", "NS", "SOA", "CNAME", "SRV"]) }, ["domain", "type"])],
  ["dns_reverse", ipRequired],
  ["dns_email_security", objectSchema({ domain: S, dkim_selectors: arrayOf(S, 100) }, ["domain"])],
  ["dns_spf_chain", objectSchema({ domain: S, max_depth: integer(1, 10) }, ["domain"])],
  ["dns_srv_discover", domainRequired],
  ["dns_wildcard_check", domainRequired],
  ["whois_domain", domainRequired],
  ["whois_ip", ipRequired],
  ["crtsh_search", objectSchema({ domain: S, exclude_expired: boolean() }, ["domain"])],
  ["shodan_host", ipRequired],
  ["shodan_search", objectSchema({ query: S, page: integer(1, 1000), facets: S }, ["query"])],
  ["shodan_dns_resolve", objectSchema({ hostnames: arrayOf(S, 100, 1) }, ["hostnames"])],
  ["shodan_exploits", objectSchema({ query: S, type: S }, ["query"])],
  ["vt_domain", domainRequired],
  ["vt_ip", ipRequired],
  ["vt_subdomains", objectSchema({ domain: S, limit: LIMIT }, ["domain"])],
  ["vt_url", objectSchema({ url: text(8192) }, ["url"]), "external_submission"],
  ["st_subdomains", domainRequired],
  ["st_dns_history", objectSchema({ domain: S, type: enumeration(["a", "aaaa", "mx", "ns", "soa", "txt"]) }, ["domain", "type"])],
  ["st_whois", domainRequired],
  ["censys_hosts", objectSchema({ query: S, per_page: LIMIT }, ["query"])],
  ["censys_host_details", ipRequired],
  ["censys_certificates", objectSchema({ query: S, per_page: LIMIT }, ["query"])],
  ["geoip_lookup", ipRequired],
  ["geoip_batch", objectSchema({ ips: arrayOf(text(45), 100, 1) }, ["ips"])],
  ["bgp_asn", objectSchema({ asn: integer(0, 4_294_967_295) }, ["asn"])],
  ["bgp_ip", ipRequired],
  ["bgp_prefix", objectSchema({ prefix: text(45), cidr: integer(0, 128) }, ["prefix", "cidr"])],
  ["wayback_urls", objectSchema({ domain: S, match_type: enumeration(["exact", "prefix", "host", "domain"]), filter: S, limit: integer(1, 1000) }, ["domain"])],
  ["wayback_snapshots", objectSchema({ url: text(8192), limit: integer(1, 1000) }, ["url"])],
  ["hackertarget_hostsearch", domainRequired],
  ["hackertarget_reverseip", ipRequired],
  ["hackertarget_aslookup", objectSchema({ query: S }, ["query"])],
  ["m365_tenant", domainRequired],
  ["m365_userrealm", domainRequired],
  ["osint_list_sources", empty],
  ["osint_domain_recon", domainRequired],
];

const scalar = Object.freeze({
  anyOf: [text(10_000), integer(-2_147_483_648, 2_147_483_647), number(-1e12, 1e12), boolean(), Object.freeze({ type: "null" })],
});
const msfOptions = Object.freeze({
  type: "object",
  propertyNames: { pattern: "^[A-Za-z][A-Za-z0-9_:-]{0,127}$" },
  additionalProperties: scalar,
  maxProperties: 256,
});
const workspacePage = objectSchema({ workspace: S, limit: MSF_LIMIT, offset: OFFSET });
const metasploitSpecs: Spec[] = [
  ["msf_credential_info", workspacePage, "high_risk"],
  ["msf_host_info", objectSchema({ workspace: S, addresses: text(256), only_up: boolean(), limit: MSF_LIMIT, offset: OFFSET }), "authorized_read"],
  ["msf_loot_info", workspacePage, "high_risk"],
  ["msf_module_check", objectSchema({ type: enumeration(["exploit", "auxiliary"]), name: SHORT, options: msfOptions }, ["type", "name", "options"]), "high_risk"],
  ["msf_module_execute", objectSchema({ type: enumeration(["exploit", "auxiliary", "post", "payload", "evasion"]), name: SHORT, options: msfOptions }, ["type", "name", "options"]), "high_risk"],
  ["msf_module_info", objectSchema({ type: enumeration(["exploit", "auxiliary", "post", "payload", "encoder", "evasion", "nop"]), name: SHORT }, ["type", "name"]), "authorized_read"],
  ["msf_module_results", objectSchema({ uuid: text(24, { minLength: 24, maxLength: 24 }) }, ["uuid"]), "authorized_read"],
  ["msf_note_info", objectSchema({ workspace: S, type: S, host: text(45), ports: text(64), protocol: enumeration(["tcp", "udp"]), limit: MSF_LIMIT, offset: OFFSET }), "authorized_read"],
  ["msf_running_stats", empty, "authorized_read"],
  ["msf_search_modules", objectSchema({ query: SHORT, limit: MSF_LIMIT, offset: OFFSET }, ["query"]), "authorized_read"],
  ["msf_service_info", objectSchema({ workspace: S, names: S, host: text(45), ports: text(64), protocol: enumeration(["tcp", "udp"]), only_up: boolean(), limit: MSF_LIMIT, offset: OFFSET }), "authorized_read"],
  ["msf_session_list", empty, "high_risk"],
  ["msf_session_read", objectSchema({ session_id: integer(1, 1_000_000) }, ["session_id"]), "high_risk", "c2_session_command_channel"],
  ["msf_session_stop", objectSchema({ session_id: integer(1, 1_000_000) }, ["session_id"]), "high_risk"],
  ["msf_session_write", objectSchema({ session_id: integer(1, 1_000_000), data: LONG }, ["session_id", "data"]), "high_risk", "c2_session_command_channel"],
  ["msf_vulnerability_info", objectSchema({ workspace: S, names: arrayOf(S, 100), host: text(45), ports: text(64), protocol: enumeration(["tcp", "udp"]), limit: MSF_LIMIT, offset: OFFSET }), "authorized_read"],
];

export const SECURITY_CAPABILITIES: readonly SecurityCapability[] = Object.freeze([
  ...makeCapabilities("cloud-audit", cloudAuditSpecs),
  ...makeCapabilities("github-security", githubSpecs),
  ...makeCapabilities("cve-mcp", cveSpecs),
  ...makeCapabilities("osint", osintSpecs),
  ...makeCapabilities("metasploit", metasploitSpecs),
]);
