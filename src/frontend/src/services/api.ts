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

  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: { ...defaultHeaders, ...headers },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    credentials: "include",
  });

  // Retry once on CSRF failure
  if (response.status === 403 && isStateChanging) {
    const retryResponse = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: { ...defaultHeaders, ...headers },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      credentials: "include",
    });
    if (!retryResponse.ok) {
      const error = await retryResponse.json().catch(() => ({}));
      throw new ApiError(retryResponse.status, error);
    }
    return retryResponse.json();
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

  constructor(status: number, data: unknown) {
    super(`API Error ${status}`);
    this.status = status;
    this.data = data;
  }
}
