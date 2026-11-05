// Anonymous shopper id: ties the cart, preferences and checkout to this browser.
export function sessionId() {
  try {
    let id = localStorage.getItem("zaldi_session");
    if (!id) { id = crypto.randomUUID(); localStorage.setItem("zaldi_session", id); }
    return id;
  } catch { return (sessionId.fallback ||= crypto.randomUUID()); }
}

async function request(path, { method = "GET", body, token, form } = {}) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: {
      "X-Session-Id": sessionId(),
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { "X-Admin-Token": token } : {}),
    },
    body: form || (body ? JSON.stringify(body) : undefined),
  });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

export function sendChat(message, image) {
  if (!image) return request("/chat", { method: "POST", body: { message } });
  const form = new FormData();
  form.append("message", message);
  form.append("image", image);
  return request("/chat", { method: "POST", form });
}

// --- Shopping: cart, preferences, checkout handshake ---
export const getCart = () => request("/cart");
export const addToCart = (product_id, quantity = 1) => request("/cart/items", { method: "POST", body: { product_id, quantity } });
export const setCartQuantity = (id, quantity) => request(`/cart/items/${id}`, { method: "PUT", body: { quantity } });
export const removeFromCart = (id) => request(`/cart/items/${id}`, { method: "DELETE" });
export const applyCoupon = (code) => request("/cart/coupon", { method: "POST", body: { code } });
export const getPreferences = () => request("/preferences");
export const savePreferences = (prefs) => request("/preferences", { method: "PUT", body: prefs });
export const prepareCheckout = (address, method) => request("/checkout/prepare", { method: "POST", body: { address, method } });
export const confirmCheckout = (token) => request("/checkout/confirm", { method: "POST", body: { token } });
export const cancelCheckout = (token) => request("/checkout/cancel", { method: "POST", body: { token } });
export const login = (token) => request("/admin/login", { method: "POST", token });
export const getStats = (token) => request("/admin/stats", { token });
export const listItems = (table, q = "") => request(`/${table}?q=${encodeURIComponent(q)}`);
export const createItem = (table, body, token) => request(`/${table}`, { method: "POST", body, token });
export const updateItem = (table, id, body, token) => request(`/${table}/${id}`, { method: "PUT", body, token });
export const deleteItem = (table, id, token) => request(`/${table}/${id}`, { method: "DELETE", token });

// --- CMS-managed content ---
export const getSiteConfig = () => request("/site-config");
export const getAdminSettings = (token) => request("/admin/settings", { token });
export const saveAdminSettings = (settings, token) => request("/admin/settings", { method: "PUT", body: settings, token });
export const getPrompts = (token) => request("/admin/prompts", { token });
export const savePrompt = (name, content, token) => request(`/admin/prompts/${name}`, { method: "PUT", body: { content }, token });
export const resetPrompt = (name, token) => request(`/admin/prompts/${name}`, { method: "DELETE", token });
