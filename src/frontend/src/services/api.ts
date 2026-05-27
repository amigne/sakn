const BASE_URL = "/api/v1";

interface ApiOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
}

function getCsrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)sakn_csrf=([^;]*)/);
  return match?.[1] ?? "";
}

export async function api<T = unknown>(path: string, options: ApiOptions = {}): Promise<T> {
  const { method = "GET", body, headers = {} } = options;

  const defaultHeaders: Record<string, string> = {
    Accept: "application/json",
  };

  if (body !== undefined) {
    defaultHeaders["Content-Type"] = "application/json";
  }

  const isStateChanging = ["POST", "PUT", "DELETE", "PATCH"].includes(method);
  if (isStateChanging) {
    const csrf = getCsrfToken();
    if (csrf) {
      defaultHeaders["X-CSRF-Token"] = csrf;
    }
  }

  const doFetch = () =>
    fetch(`${BASE_URL}${path}`, {
      method,
      headers: { ...defaultHeaders, ...headers },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      credentials: "include",
    });

  let response = await doFetch();

  // On CSRF mismatch (403), fetch fresh token and retry once
  if (response.status === 403 && isStateChanging) {
    const errorData = await response.json().catch(() => ({}));
    const code = errorData?.error?.code;
    if (code === "CSRF_MISMATCH") {
      // Fetch fresh CSRF token
      await fetch(`${BASE_URL}/auth/csrf`, { credentials: "include" });
      // Re-read cookie and retry
      const freshCsrf = getCsrfToken();
      if (freshCsrf) {
        defaultHeaders["X-CSRF-Token"] = freshCsrf;
      }
      response = await doFetch();
    }
  }

  // On 401, clear auth state and redirect to login (except auth endpoints themselves).
  // INVALID_CREDENTIALS means the user is authenticated but password confirmation failed —
  // don't log them out, let the caller handle the error.
  if (response.status === 401 && !path.startsWith("/auth/")) {
    const errorData = await response.json().catch(() => ({}));
    const errorCode = errorData?.error?.code;
    if (errorCode !== "INVALID_CREDENTIALS") {
      const { useAuthStore } = await import("@/stores/authStore");
      useAuthStore.setState({ user: null, preferences: null });
      window.location.href = "/login";
      throw new ApiError(401, { error: { message: "Session expired." } });
    }
    throw new ApiError(401, errorData);
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new ApiError(response.status, error);
  }

  return response.json();
}

export interface FieldError {
  message_key: string;
  message: string;
}

export interface ErrorFields {
  [field: string]: FieldError;
}

export class ApiError extends Error {
  status: number;
  data: unknown;
  code: string;
  messageKey: string | null;
  fields: ErrorFields | null;

  constructor(status: number, data: unknown) {
    const err = (
      data as { error?: { code?: string; message?: string; message_key?: string; details?: { fields?: ErrorFields } } }
    )?.error;
    const msg = err?.message ?? `API Error ${status}`;
    super(msg);
    this.status = status;
    this.data = data;
    this.code = err?.code ?? "UNKNOWN";
    const rawKey = err?.message_key ?? null;
    this.messageKey = rawKey?.startsWith("errors.") ? `errors:${rawKey.slice("errors.".length)}` : rawKey;
    const rawFields = err?.details?.fields ?? null;
    if (rawFields) {
      const rewritten: ErrorFields = {};
      for (const [field, info] of Object.entries(rawFields)) {
        rewritten[field] = {
          message_key: info.message_key?.startsWith("errors.")
            ? `errors:${info.message_key.slice("errors.".length)}`
            : info.message_key,
          message: info.message,
        };
      }
      this.fields = rewritten;
    } else {
      this.fields = null;
    }
  }
}
