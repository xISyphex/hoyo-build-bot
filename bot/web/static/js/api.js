// The optimizer's JSON API. The session token comes in the URL fragment (never sent to the server or logged), is kept
// for this tab only, and goes out in the Authorization header.

const KEY = "hsr-optimize-token";

export class ApiError extends Error {
  constructor(status, body) {
    super((body && body.error) || `HTTP ${status}`);
    this.status = status;
    this.body = body || {};
  }
}

export function takeToken() {
  const fromUrl = location.hash.replace(/^#/, "").trim();
  if (fromUrl) {
    try { sessionStorage.setItem(KEY, fromUrl); } catch { /* private mode: keep it in memory only */ }
    history.replaceState(null, "", location.pathname + location.search);  // out of the address bar
    return fromUrl;
  }
  try { return sessionStorage.getItem(KEY) || ""; } catch { return ""; }
}

export function forgetToken() {
  try { sessionStorage.removeItem(KEY); } catch { /* nothing kept */ }
}

export async function api(path, { token, method = "GET", body } = {}) {
  const headers = { Accept: "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  let response;
  try {
    response = await fetch(`/api/hsr/${path}`, {
      method, headers, body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "omit", cache: path === "meta" ? "default" : "no-store",
    });
  } catch {
    throw new ApiError(0, { error: "Can't reach the optimizer. Check your connection and try again." });
  }
  let data = null;
  try { data = await response.json(); } catch { data = null; }
  if (!response.ok) throw new ApiError(response.status, data);
  return data;
}
