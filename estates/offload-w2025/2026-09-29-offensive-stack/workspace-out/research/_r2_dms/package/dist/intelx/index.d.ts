export interface IntelxSearchInitResponse {
    id: string;
    status: number;
}
export interface IntelxSearchResultRecord {
    systemid: string;
    owner: string;
    storageid: string;
    intelxid: string;
    bucket: string;
    keyid: string;
    added: string;
    date: string;
    name: string;
    description: string;
    media: number;
    type: number;
    typeh: string;
    simhash: string;
    accesslevel: number;
    accesslevelh: string;
    [key: string]: unknown;
}
export interface IntelxSearchResultsResponse {
    id: string;
    status: number;
    selectors: unknown[];
    records: IntelxSearchResultRecord[];
    statistics: Record<string, unknown>;
    [key: string]: unknown;
}
export interface IntelxPhonebookInitResponse {
    id: string;
    status: number;
}
export interface IntelxPhonebookResultRecord {
    value: string;
    type: number;
    typeh: string;
    media: number;
    mediah: string;
    [key: string]: unknown;
}
export interface IntelxPhonebookResultsResponse {
    id: string;
    selectors: IntelxPhonebookResultRecord[];
    status: number;
    [key: string]: unknown;
}
export declare function intelxSearch(term: string, maxResults: number | undefined, apiKey: string): Promise<IntelxSearchInitResponse>;
export declare function intelxSearchResults(id: string, offset: number | undefined, limit: number | undefined, apiKey: string): Promise<IntelxSearchResultsResponse>;
export declare function intelxPhonebook(term: string, target: number | undefined, maxResults: number | undefined, apiKey: string): Promise<IntelxPhonebookInitResponse>;
export declare function intelxPhonebookResults(id: string, offset: number | undefined, limit: number | undefined, apiKey: string): Promise<IntelxPhonebookResultsResponse>;
//# sourceMappingURL=index.d.ts.map