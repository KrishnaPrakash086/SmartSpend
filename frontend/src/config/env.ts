// Single source of truth for ALL environment variables — read once at module load, exported as constants
// Usage: import { API_BASE_URL, VAPI_PUBLIC_KEY } from "@/config/env";

const env = (import.meta as any).env || {};

// Backend API base URL — falls back to localhost for dev convenience
export const API_BASE_URL: string = env.VITE_API_BASE_URL || "http://localhost:8001/api/v1";

// VAPI voice assistant credentials — leave empty to disable Voice Mode in the UI
export const VAPI_PUBLIC_KEY: string = env.VITE_VAPI_PUBLIC_KEY || "";
export const VAPI_ASSISTANT_ID: string = env.VITE_VAPI_ASSISTANT_ID || "";

// Convenience flag — true when both keys are set
export const VAPI_ENABLED: boolean = Boolean(VAPI_PUBLIC_KEY && VAPI_ASSISTANT_ID);

// Build mode — vite injects this automatically
export const IS_DEV: boolean = env.DEV === true;
export const IS_PROD: boolean = env.PROD === true;
