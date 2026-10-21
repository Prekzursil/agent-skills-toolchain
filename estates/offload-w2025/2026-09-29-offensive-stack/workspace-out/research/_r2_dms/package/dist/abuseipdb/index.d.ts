export interface AbuseipdbCheckResponse {
    data: {
        ipAddress: string;
        isPublic: boolean;
        ipVersion: number;
        isWhitelisted: boolean | null;
        abuseConfidenceScore: number;
        countryCode: string;
        countryName: string;
        usageType: string;
        isp: string;
        domain: string;
        hostnames: string[];
        isTor: boolean;
        totalReports: number;
        numDistinctUsers: number;
        lastReportedAt: string | null;
        reports?: AbuseipdbReport[];
    };
}
export interface AbuseipdbReport {
    reportedAt: string;
    comment: string;
    categories: number[];
    reporterId: number;
    reporterCountryCode: string;
    reporterCountryName: string;
}
export interface AbuseipdbReportsResponse {
    data: {
        total: number;
        page: number;
        count: number;
        perPage: number;
        lastPage: number;
        nextPageUrl: string | null;
        previousPageUrl: string | null;
        results: AbuseipdbReport[];
    };
}
export interface AbuseipdbBlacklistEntry {
    ipAddress: string;
    abuseConfidenceScore: number;
    lastReportedAt: string;
}
export interface AbuseipdbBlacklistResponse {
    meta: {
        generatedAt: string;
    };
    data: AbuseipdbBlacklistEntry[];
}
export interface AbuseipdbCheckBlockResponse {
    data: {
        networkAddress: string;
        netmask: string;
        minAddress: string;
        maxAddress: string;
        numPossibleHosts: number;
        addressSpaceDesc: string;
        reportedAddress: {
            ipAddress: string;
            numReports: number;
            mostRecentReport: string;
            abuseConfidenceScore: number;
            countryCode: string;
        }[];
    };
}
export declare function abuseipdbCheck(ip: string, maxAge: number | undefined, verbose: boolean | undefined, apiKey: string): Promise<AbuseipdbCheckResponse>;
export declare function abuseipdbReports(ip: string, maxAge: number | undefined, limit: number | undefined, apiKey: string): Promise<AbuseipdbReportsResponse>;
export declare function abuseipdbBlacklist(confidence: number | undefined, limit: number | undefined, apiKey: string): Promise<AbuseipdbBlacklistResponse>;
export declare function abuseipdbCheckBlock(network: string, maxAge: number | undefined, apiKey: string): Promise<AbuseipdbCheckBlockResponse>;
//# sourceMappingURL=index.d.ts.map