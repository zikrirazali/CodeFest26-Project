// Thin fetch wrapper that attaches the JWT and normalises errors.
const Store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch { /* private mode */ } },
};

const Api = {
  token: Store.get("tempa.token"),
  user: JSON.parse(Store.get("tempa.user") || "null"),

  setSession(token, user) {
    this.token = token; this.user = user;
    Store.set("tempa.token", token); Store.set("tempa.user", user ? JSON.stringify(user) : null);
  },

  async call(method, path, body) {
    const headers = { "Content-Type": "application/json" };
    if (this.token) headers.Authorization = `Bearer ${this.token}`;
    const res = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined });
    const data = await res.json().catch(() => ({}));
    if (res.status === 401 && this.token) {
      this.setSession(null, null);
      location.hash = "#/login";
    }
    if (!res.ok) {
      const detail = typeof data.detail === "string" ? data.detail : "error";
      throw Object.assign(new Error(detail), { status: res.status, data });
    }
    return data;
  },
  get(p) { return this.call("GET", p); },
  post(p, b) { return this.call("POST", p, b || {}); },
};
