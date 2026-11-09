// The session is an HttpOnly cookie set by the server at sign-in. The browser sends it on its own; no script can read it,
// and the app keeps no copy of it. All that is remembered here is who signed in (see auth.tsx), so a phone with no signal can still open.
const USER_KEY = "lt.user";

// Older versions kept the session token in localStorage. Take it out so no copy of it is left behind.
try {
  localStorage.removeItem("lt.token");
} catch {
  /* private mode */
}

/** True when this browser has signed in here before (the cached person exists). It does not prove the session is still good. */
export function looksSignedIn(): boolean {
  try {
    return !!localStorage.getItem(USER_KEY);
  } catch {
    return false;
  }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, opts: { method?: string; body?: unknown; form?: FormData } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  const res = await fetch(path, { method: opts.method ?? (body ? "POST" : "GET"), headers, body, credentials: "same-origin" });
  if (res.status === 401 && looksSignedIn() && !path.startsWith("/api/auth/login")) {
    window.dispatchEvent(new Event("lt:signed-out"));
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data.error ?? `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export async function download(path: string, filename: string) {
  const res = await fetch(path, { credentials: "same-origin" });
  if (!res.ok) throw new ApiError(res.status, "Download failed");
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
