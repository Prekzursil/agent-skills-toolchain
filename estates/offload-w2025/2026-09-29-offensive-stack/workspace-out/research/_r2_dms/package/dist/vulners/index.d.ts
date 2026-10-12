export interface VulnersDocument {
    id: string;
    title: string;
    description: string;
    type: string;
    bulletinFamily: string;
    cvss: {
        score: number;
        vector: string;
    } | null;
    published: string;
    modified: string;
    href: string;
    sourceHref: string;
    reporter: string;
    cvelist: string[];
    [key: string]: unknown;
}
export interface VulnersSearchResponse {
    result: string;
    data: {
        search: VulnersDocument[];
        total: number;
        exactMatch: boolean;
        references: Record<string, unknown>;
    };
}
export interface VulnersIdResponse {
    result: string;
    data: {
        documents: Record<string, VulnersDocument>;
        references: Record<string, unknown>;
    };
}
export declare function vulnersSearch(query: string, limit?: number, apiKey?: string): Promise<VulnersSearchResponse>;
export declare function vulnersId(id: string): Promise<VulnersIdResponse>;
export declare function vulnersExploit(query: string, limit?: number, apiKey?: string): Promise<VulnersSearchResponse>;
//# sourceMappingURL=index.d.ts.map