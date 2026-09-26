/**
 * NEXUS API Client
 *
 * Centralized HTTP client for all backend communication.
 * Auth: X-Dev-User-ID header (sprint dev mode).
 * Base: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"
 */

const BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1").replace(/\/$/, "");

const USER_ID_KEY = "nexus_dev_user_id";
const WORKSPACE_ID_KEY = "nexus_active_workspace_id";

export function getDevUserId(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(USER_ID_KEY);
}

export function setDevUserId(id: string): void {
  sessionStorage.setItem(USER_ID_KEY, id);
}

export function getActiveWorkspaceId(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(WORKSPACE_ID_KEY);
}

export function setActiveWorkspaceId(id: string): void {
  sessionStorage.setItem(WORKSPACE_ID_KEY, id);
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: Record<string, unknown> | FormData | null;
  multipart?: boolean;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const userId = getDevUserId();
  const { body, multipart, ...init } = options;

  const headers: Record<string, string> = {
    ...(userId ? { "X-Dev-User-ID": userId } : {}),
    ...(init.headers as Record<string, string> | undefined),
  };

  if (body && !multipart) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers,
    body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    let code = "UNKNOWN";
    let message = `HTTP ${response.status}`;
    try {
      const err = await response.json();
      code = err?.detail?.code ?? err?.code ?? code;
      message = err?.detail?.message ?? err?.message ?? message;
    } catch {
      // non-JSON error body
    }
    throw new ApiError(response.status, code, message);
  }

  if (response.status === 204) return undefined as unknown as T;
  return response.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string, options?: Omit<RequestOptions, "body" | "method">) =>
    request<T>(path, { ...options, method: "GET" }),

  post: <T>(path: string, body?: Record<string, unknown>, options?: Omit<RequestOptions, "body" | "method">) =>
    request<T>(path, { ...options, method: "POST", body }),

  postForm: <T>(path: string, form: FormData, options?: Omit<RequestOptions, "body" | "method" | "multipart">) =>
    request<T>(path, { ...options, method: "POST", body: form, multipart: true }),

  delete: <T>(path: string, options?: Omit<RequestOptions, "body" | "method">) =>
    request<T>(path, { ...options, method: "DELETE" }),
};

export async function* streamRequest(
  path: string,
  body: Record<string, unknown>,
): AsyncGenerator<Record<string, unknown>> {
  const userId = getDevUserId();

  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(userId ? { "X-Dev-User-ID": userId } : {}),
    },
    body: JSON.stringify(body),
  });

  if (!response.ok || !response.body) {
    throw new ApiError(response.status, "STREAM_ERROR", `Streaming failed: HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const raw = line.slice(6).trim();
        if (raw) {
          try {
            yield JSON.parse(raw) as Record<string, unknown>;
          } catch {
            // skip malformed event
          }
        }
      }
    }
  }
}
