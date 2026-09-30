export interface PhishTankCheckResponse {
    results: {
        url: string;
        in_database: boolean;
        phish_id?: string;
        phish_detail_page?: string;
        verified: boolean;
        verified_at?: string;
        valid: boolean;
    };
    meta: {
        timestamp: string;
        serverid: string;
        status: string;
        requestid: string;
    };
}
export declare function phishingCheck(url: string, apiKey?: string): Promise<PhishTankCheckResponse>;
//# sourceMappingURL=index.d.ts.map