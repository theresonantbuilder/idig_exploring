// The only place the iDIG API origin is read (SPEC §4.1). Always just the
// origin; every path already carries the /exploring prefix (SPEC §4.7).
export const IDIG_API_URL: string = import.meta.env.VITE_IDIG_API_URL;
