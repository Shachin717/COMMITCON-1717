import { showToast } from "@/components/ui/toast";

export class ApiError extends Error {
  status: number;
  data: any;
  fieldErrors?: Record<string, string>;

  constructor(
    message: string,
    status: number,
    data?: any,
    fieldErrors?: Record<string, string>
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
    this.fieldErrors = fieldErrors;
  }
}

let isRefreshing = false;
let refreshSubscribers: ((token: string | null) => void)[] = [];

function subscribeTokenRefresh(cb: (token: string | null) => void) {
  refreshSubscribers.push(cb);
}

function onRefreshed(token: string | null) {
  refreshSubscribers.forEach((cb) => cb(token));
  refreshSubscribers = [];
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
  skipAuthRefresh?: boolean;
}

function getCsrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export async function apiClient<T = any>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { params, skipAuthRefresh, headers: customHeaders, ...restOptions } = options;

  let url = endpoint.startsWith("http")
    ? endpoint
    : `${API_BASE_URL}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;

  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, String(value));
      }
    });
    const qs = searchParams.toString();
    if (qs) {
      url += (url.includes("?") ? "&" : "?") + qs;
    }
  }

  const defaultHeaders: Record<string, string> = {
    "X-Requested-With": "XMLHttpRequest",
  };
  const csrfToken = getCsrfToken();
  if (csrfToken) {
    defaultHeaders["X-CSRF-Token"] = csrfToken;
  }
  if (!(restOptions.body instanceof FormData)) {
    defaultHeaders["Content-Type"] = "application/json";
  }

  const config: RequestInit = {
    ...restOptions,
    credentials: "include", // Always include cookies
    headers: {
      ...defaultHeaders,
      ...customHeaders,
    },
  };

  let response: Response;
  try {
    response = await fetch(url, config);
  } catch (err: any) {
    if (err?.name === "AbortError") {
      throw err;
    }
    const netMsg = err?.message
      ? `Network error: ${err.message}`
      : "Network error: Unable to connect to server. Please check your internet connection.";
    throw new ApiError(netMsg, 0);
  }

  // Handle 401 Unauthorized
  if (response.status === 401 && !skipAuthRefresh && !endpoint.includes("/auth/")) {
    if (!isRefreshing) {
      isRefreshing = true;

      try {
        const refreshRes = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
          },
        });

        if (refreshRes.ok) {
          const data = await refreshRes.json();
          isRefreshing = false;
          onRefreshed(data.access_token || "refreshed");
          // Retry original request once
          return apiClient<T>(endpoint, { ...options, skipAuthRefresh: true });
        } else {
          throw new Error("Refresh failed");
        }
      } catch (refreshErr) {
        isRefreshing = false;
        onRefreshed(null);
        handleSessionExpired();
        throw new ApiError("Session expired", 401);
      }
    } else {
      // Wait for existing refresh promise
      return new Promise((resolve, reject) => {
        subscribeTokenRefresh(async (token) => {
          if (token) {
            try {
              const res = await apiClient<T>(endpoint, {
                ...options,
                skipAuthRefresh: true,
              });
              resolve(res);
            } catch (retryErr) {
              reject(retryErr);
            }
          } else {
            reject(new ApiError("Session expired", 401));
          }
        });
      });
    }
  }

  let data: any = null;
  const contentType = response.headers.get("content-type");
  if (contentType && contentType.includes("application/json")) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  } else {
    try {
      data = await response.text();
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    let errorMessage = "";
    const fieldErrors: Record<string, string> = {};

    if (typeof data === "string") {
      // Non-JSON or HTML response (e.g., 502/504 Bad Gateway, custom server text)
      const cleanText = data.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
      errorMessage = cleanText ? cleanText.slice(0, 300) : (response.statusText || `Request failed with status ${response.status}`);
    } else if (data && typeof data === "object") {
      const detail = data.detail ?? data.message ?? data.error;

      if (Array.isArray(detail)) {
        // FastAPI 422: detail is array of { loc: [...], msg: string, ... }
        const formattedLines: string[] = [];
        detail.forEach((item: any) => {
          if (item && typeof item === "object") {
            let field = "error";
            if (Array.isArray(item.loc) && item.loc.length > 0) {
              // Extract field name from loc array (e.g. ['body', 'slot_id'] -> 'slot_id')
              const lastLoc = item.loc[item.loc.length - 1];
              field = String(lastLoc);
            } else if (item.loc) {
              field = String(item.loc);
            }

            const msg =
              typeof item.msg === "string"
                ? item.msg
                : typeof item.message === "string"
                ? item.message
                : JSON.stringify(item);

            fieldErrors[field] = msg;
            formattedLines.push(`${field}: ${msg}`);
          } else if (typeof item === "string") {
            formattedLines.push(item);
          }
        });

        errorMessage = formattedLines.length > 0 ? formattedLines.join("\n") : "Validation error occurred.";
      } else if (typeof detail === "string") {
        errorMessage = detail;
      } else if (typeof detail === "object" && detail !== null) {
        // Object dictionary of errors
        const entries = Object.entries(detail).map(([k, v]) => {
          const valStr = typeof v === "string" ? v : JSON.stringify(v);
          fieldErrors[k] = valStr;
          return `${k}: ${valStr}`;
        });
        errorMessage = entries.length > 0 ? entries.join("\n") : JSON.stringify(detail);
      } else {
        errorMessage = response.statusText || `Request failed with status ${response.status}`;
      }
    } else {
      errorMessage = response.statusText || `Request failed with status ${response.status}`;
    }

    if (typeof errorMessage !== "string" || !errorMessage.trim()) {
      errorMessage = `Request failed with status ${response.status}`;
    }

    throw new ApiError(
      errorMessage,
      response.status,
      data,
      Object.keys(fieldErrors).length > 0 ? fieldErrors : undefined
    );
  }

  return data as T;
}

function handleSessionExpired() {
  if (typeof window !== "undefined") {
    // Notify the user via toast
    showToast({
      title: "Session Expired",
      message: "Your session has expired. Please log in again.",
      type: "warning",
      duration: 6000,
    });

    const currentPath = window.location.pathname;
    let loginTarget = "/staff/login";
    if (currentPath.startsWith("/admin")) {
      loginTarget = "/admin/login";
    } else if (currentPath.startsWith("/coordinator")) {
      loginTarget = "/coordinator/login";
    } else if (currentPath.startsWith("/faculty")) {
      loginTarget = "/faculty/login";
    } else if (currentPath.startsWith("/hod")) {
      loginTarget = "/hod/login";
    }

    setTimeout(() => {
      window.location.href = `${loginTarget}?expired=1`;
    }, 400);
  }
}

