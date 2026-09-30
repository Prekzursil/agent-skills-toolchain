export interface PulsediveIndicatorResponse {
    iid: number;
    type: string;
    indicator: string;
    risk: string;
    risk_recommended: string;
    manualrisk: number;
    retired: string;
    stamp_added: string;
    stamp_updated: string;
    stamp_seen: string;
    stamp_retired: string | null;
    recent: number;
    summary: {
        properties: Record<string, unknown>;
        threats: {
            tid: number;
            name: string;
            category: string;
        }[];
        feeds: {
            fid: number;
            name: string;
            organization: string;
        }[];
    };
    threats: string[];
    feeds: string[];
    comments: unknown[];
    attributes: Record<string, unknown>;
    properties: Record<string, unknown>;
    [key: string]: unknown;
}
export interface PulsediveSearchResponse {
    results: string[];
    [key: string]: unknown;
}
export interface PulsediveExploreResponse {
    results: {
        iid: number;
        indicator: string;
        type: string;
        risk: string;
        stamp_linked: string;
    }[];
    [key: string]: unknown;
}
export declare function pulsediveIndicator(indicator: string, apiKey?: string): Promise<PulsediveIndicatorResponse>;
export declare function pulsediveSearch(query: string, apiKey?: string): Promise<PulsediveSearchResponse>;
export declare function pulsediveExplore(query: string, apiKey?: string): Promise<PulsediveExploreResponse>;
//# sourceMappingURL=index.d.ts.map