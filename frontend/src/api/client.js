import { readText, parseSSE, errorMessage } from "../lib/stream";

const API_BASE = "/api/v1";
const ACCESS_KEY = "finance_rag_access_token";
const REFRESH_KEY = "finance_rag_refresh_token";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

export class UnauthorizedError extends ApiError {
  constructor(message = "Session expired, please log in again") {
    super(message, 401);
  }
}

const store = {
  get: (k) => localStorage.getItem(k),
  set: (access, refresh) => {
    localStorage.setItem(ACCESS_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear: () => {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

export const hasSession = () => !!store.get(ACCESS_KEY);
export const logout = () => store.clear();

// Access tokens last 30 minutes, refresh tokens 7 days. Several requests
// can hit a 401 at once (a page loading its data), so they all wait on
// the same refresh rather than each spending the refresh token.
let refreshing = null;
function refreshSession() {
  refreshing ??= (async () => {
    const refresh_token = store.get(REFRESH_KEY);
    if (!refresh_token) throw new UnauthorizedError();
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token }),
    });
    if (!res.ok) throw new UnauthorizedError();
    const data = await res.json();
    store.set(data.access_token, data.refresh_token);
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

/** fetch with the bearer token, one transparent refresh-and-retry on 401, and errors raised as ApiError. */
async function authedFetch(path, options = {}) {
  const send = () =>
    fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        // FormData needs the browser to set its own multipart boundary.
        ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        Authorization: `Bearer ${store.get(ACCESS_KEY)}`,
        ...(options.headers || {}),
      },
    });

  let res = await send();
  if (res.status === 401) {
    try {
      await refreshSession();
    } catch (err) {
      store.clear();
      throw err;
    }
    res = await send();
    if (res.status === 401) {
      store.clear();
      throw new UnauthorizedError();
    }
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(errorMessage(body, res.status), res.status);
  }
  return res;
}

async function request(path, options) {
  const res = await authedFetch(path, options);
  return res.status === 204 ? null : res.json();
}

const json = (method, body) => ({ method, body: JSON.stringify(body) });

// ---- auth ----
export async function login(username, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(errorMessage(body, res.status), res.status);
  }
  const data = await res.json();
  store.set(data.access_token, data.refresh_token);
}

export const fetchMe = () => request("/auth/me");
export const createUser = (user) => request("/auth/admin/users", json("POST", user));
export const fetchUsers = () => request("/auth/admin/users");
export const setUserAdmin = (id, is_admin) => request(`/auth/admin/users/${id}`, json("PATCH", { is_admin }));

// ---- documents ----
export const fetchDocuments = () => request("/ingestion/documents").then((r) => r.documents);
export const deleteDocument = (fileName) =>
  request(`/ingestion/documents/${encodeURIComponent(fileName)}`, { method: "DELETE" });

/**
 * Uploads a PDF. The response is a stream of progress events
 * (extracting -> chunking -> embedding -> storing -> saving -> done, or
 * error); each is handed to onEvent as it arrives.
 */
export async function uploadDocument(file, source, onEvent) {
  const form = new FormData();
  form.append("source", source);
  form.append("file", file);
  const res = await authedFetch("/ingestion/upload", { method: "POST", body: form });
  for await (const event of parseSSE(readText(res))) onEvent(event);
}

export const fetchShares = (fileName) =>
  request(`/ingestion/shares/${encodeURIComponent(fileName)}`).then((r) => r.shares);
export const shareDocument = (file_name, user_email) => request("/ingestion/shares", json("POST", { file_name, user_email }));
export const unshareDocument = (file_name, user_email) => request("/ingestion/shares", json("DELETE", { file_name, user_email }));

// ---- ask ----
export const searchChunks = (query, top_n) => request("/retrieval/search", json("POST", { query, top_n })).then((r) => r.results);

/** Streams the answer as plain text; onToken gets each piece as it arrives. */
export async function streamAnswer(query, top_n, onToken) {
  const res = await authedFetch("/generation/generate", json("POST", { query, top_n }));
  for await (const piece of readText(res)) onToken(piece);
}

export const evaluateAnswer = (query, answer, top_n) => request("/generation/eval", json("POST", { query, answer, top_n }));

// ---- audit ----
function qs(params) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined && v !== "") p.set(k, v);
  return p.toString();
}
export const fetchQueryEvents = (params) => request(`/audit/queries?${qs(params)}`).then((r) => r.events);
export const fetchIngestionEvents = (params) => request(`/audit/ingestions?${qs(params)}`).then((r) => r.events);
