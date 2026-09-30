export interface OtxGeneralResponse {
    indicator: string;
    pulse_info: {
        count: number;
        pulses: OtxPulse[];
    };
    base_indicator: Record<string, unknown>;
    sections: string[];
    type: string;
    type_title: string;
    whois?: string;
    reputation?: number;
    country_code?: string;
    country_name?: string;
    asn?: string;
    city?: string;
    [key: string]: unknown;
}
export interface OtxPulse {
    id: string;
    name: string;
    description: string;
    author_name: string;
    created: string;
    modified: string;
    tags: string[];
    targeted_countries: string[];
    malware_families: string[];
    attack_ids: {
        id: string;
        name: string;
        display_name: string;
    }[];
    industries: string[];
    TLP: string;
    adversary: string;
    indicator_count: number;
    [key: string]: unknown;
}
export interface OtxPulseSearchResponse {
    count: number;
    next: string | null;
    previous: string | null;
    results: OtxPulse[];
}
export declare function otxIp(ip: string, apiKey?: string): Promise<OtxGeneralResponse>;
export declare function otxDomain(domain: string, apiKey?: string): Promise<OtxGeneralResponse>;
export declare function otxHash(hash: string, apiKey?: string): Promise<OtxGeneralResponse>;
export declare function otxCve(cve: string, apiKey?: string): Promise<OtxGeneralResponse>;
export declare function otxSearchPulses(query: string, limit?: number, apiKey?: string): Promise<OtxPulseSearchResponse>;
//# sourceMappingURL=index.d.ts.map