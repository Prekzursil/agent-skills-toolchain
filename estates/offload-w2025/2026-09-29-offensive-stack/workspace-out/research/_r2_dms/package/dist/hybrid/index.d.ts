export interface HybridSearchResult {
    sha256: string;
    sha1: string;
    md5: string;
    verdict: string;
    av_detect: number;
    threat_score: number | null;
    vx_family: string;
    type: string;
    type_short: string[];
    environment_description: string;
    environment_id: number;
    submit_name: string;
    analysis_start_time: string;
    size: number;
    tags: string[];
    [key: string]: unknown;
}
export interface HybridSearchResponse extends Array<HybridSearchResult> {
}
export interface HybridOverviewResponse {
    sha256: string;
    sha1: string;
    md5: string;
    size: number;
    type: string;
    type_short: string;
    verdict: string;
    av_detect: number;
    threat_score: number | null;
    vx_family: string;
    submit_name: string;
    analysis_start_time: string;
    last_multi_scan: string;
    tags: string[];
    classification_tags: string[];
    domains: string[];
    hosts: string[];
    compromised_hosts: string[];
    total_network_connections: number;
    total_processes: number;
    total_signatures: number;
    extracted_files: {
        name: string;
        sha256: string;
        type_tags: string[];
        description: string;
        runtime_process: string;
        threat_level: number;
    }[];
    processes: {
        uid: string;
        name: string;
        command_line: string;
        sha256: string;
    }[];
    mitre_attcks: {
        tactic: string;
        technique: string;
        attck_id: string;
        attck_id_wiki: string;
        malicious_identifiers_count: number;
        suspicious_identifiers_count: number;
        informative_identifiers_count: number;
    }[];
    [key: string]: unknown;
}
export interface HybridFeedEntry {
    sha256: string;
    md5: string;
    sha1: string;
    verdict: string;
    av_detect: number;
    vx_family: string;
    submit_name: string;
    analysis_start_time: string;
    environment_description: string;
    type: string;
    size: number;
    tags: string[];
    threat_score: number | null;
    [key: string]: unknown;
}
export type HybridFeedResponse = HybridFeedEntry[];
export declare function malwareSearch(hash: string, apiKey: string): Promise<HybridSearchResponse>;
export declare function malwareOverview(sha256: string, apiKey: string): Promise<HybridOverviewResponse>;
export declare function malwareFeed(apiKey: string): Promise<HybridFeedResponse>;
//# sourceMappingURL=index.d.ts.map