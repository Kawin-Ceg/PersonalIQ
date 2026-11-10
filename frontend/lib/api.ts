export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const USER_KEY = "personaliq.user";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/** Demo user picked in the sidebar. No auth in the hackathon build. */
export function getCurrentUserId(): string | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage.getItem(USER_KEY);
  } catch {
    return null;
  }
}

export function setCurrentUserId(id: string) {
  try {
    window.localStorage.setItem(USER_KEY, id);
  } catch {
    /* private mode: falls back to the default demo user */
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  const uid = getCurrentUserId();
  if (uid) headers["X-PersonalIQ-User"] = uid;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) {
    let message = res.statusText;
    try {
      const data = await res.json();
      message = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail ?? data);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, message);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export const apiGet = <T>(path: string) => request<T>("GET", path);
export const apiPost = <T>(path: string, body: unknown) => request<T>("POST", path, body);
export const apiPatch = <T>(path: string, body: unknown) => request<T>("PATCH", path, body);
export const apiDelete = (path: string) => request<void>("DELETE", path);
