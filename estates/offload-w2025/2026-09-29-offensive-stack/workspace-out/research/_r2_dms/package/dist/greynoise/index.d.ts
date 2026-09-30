export interface GreynoiseIpResponse {
    ip: string;
    noise: boolean;
    riot: boolean;
    classification: string;
    name: string;
    link: string;
    last_seen: string;
    message: string;
}
export interface GreynoiseCheckResult {
    ip: string;
    classification: string;
    isScanner: boolean;
    isKnownBenign: boolean;
}
export declare function greynoiseIp(ip: string): Promise<GreynoiseIpResponse>;
export declare function greynoiseCheck(ip: string): Promise<GreynoiseCheckResult>;
//# sourceMappingURL=index.d.ts.map