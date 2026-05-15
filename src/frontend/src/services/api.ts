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

  // On 401, clear auth state and redirect to login (except auth endpoints themselves)
  if (response.status === 401 && !path.startsWith("/auth/")) {
    const { useAuthStore } = await import("@/stores/authStore");
    // Clear user directly — don't call logout() which would trigger another API call
    useAuthStore.setState({ user: null, preferences: null });
    window.location.href = "/login";
    throw new ApiError(401, { error: { message: "Session expired." } });
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new ApiError(response.status, error);
  }

  return response.json();
}

export class ApiError extends Error {
  status: number;
  data: unknown;
  code: string;

  constructor(status: number, data: unknown) {
    const msg = (data as { error?: { message?: string } })?.error?.message ?? `API Error ${status}`;
    super(msg);
    this.status = status;
    this.data = data;
    this.code = (data as { error?: { code?: string } })?.error?.code ?? "UNKNOWN";
  }
}
