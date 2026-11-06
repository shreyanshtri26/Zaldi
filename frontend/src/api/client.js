import { getPage } from "../shared/embed.js";

// Anonymous shopper id: ties the cart, preferences and checkout to this browser.
export function sessionId() {
  try {
    let id = localStorage.getItem("zaldi_session");
    if (!id) { id = crypto.randomUUID(); localStorage.setItem("zaldi_session", id); }
    return id;
  } catch { return (sessionId.fallback ||= crypto.randomUUID()); }
}

// The store this browser is working with: from ?store=slug (the embedded widget) or the owner's sign-in.
export function storeSlug() {
  try {
    const fromUrl = new URLSearchParams(window.location.search).get("store");
    if (fromUrl) sessionStorage.setItem("zaldi_store", fromUrl);
    return sessionStorage.getItem("zaldi_store") || "";
  } catch { return ""; }
}
export function setStore(slug) { try { slug ? sessionStorage.setItem("zaldi_store", slug) : sessionStorage.removeItem("zaldi_store"); } catch {} }

async function request(path, { method = "GET", body, token, form } = {}) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: {
      "X-Session-Id": sessionId(),
      ...(storeSlug() ? { "X-Store": storeSlug() } : {}),
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { "X-Admin-Token": token } : {}),
    },
    body: form || (body ? JSON.stringify(body) : undefined),
  });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Something went wrong. Please try again in a moment.");
  return data;
}

export function sendChat(message, image, history) {
  if (!image) return request("/chat", { method: "POST", body: { message, history, page: getPage() || undefined } });
  const form = new FormData();
  form.append("message", message);
  form.append("image", image);
  return request("/chat", { method: "POST", form });
}

// --- Shopping: cart, preferences, checkout handshake ---
export const sendFeedback = (chat_id, rating) => request("/feedback", { method: "POST", body: { chat_id, rating } });
export const getMetrics = (token, days = 7) => request(`/admin/metrics?days=${days}`, { token });
export const accountLogin = (email, password) => request("/admin/account-login", { method: "POST", body: { email, password } });
export const signupStore = (body) => request("/signup", { method: "POST", body });
export const getEmbed = (token) => request("/admin/embed", { token });
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
export const uploadImage = (file, token) => {
  const form = new FormData();
  form.append("image", file);
  return request("/admin/upload", { method: "POST", form, token });
};
export const getCategories = () => request("/categories");
export const getSiteConfig = () => request("/site-config");
export const getAdminSettings = (token) => request("/admin/settings", { token });
export const saveAdminSettings = (settings, token) => request("/admin/settings", { method: "PUT", body: settings, token });
export const getStore = (token) => request("/admin/store", { token });
export const saveStore = (changes, token) => request("/admin/store", { method: "PUT", body: changes, token });
export const resetStore = (token) => request("/admin/store", { method: "DELETE", token });
export const testStore = (token) => request("/admin/store/test", { method: "POST", token });
export const getPrompts = (token) => request("/admin/prompts", { token });
export const savePrompt = (name, content, token) => request(`/admin/prompts/${name}`, { method: "PUT", body: { content }, token });
export const resetPrompt = (name, token) => request(`/admin/prompts/${name}`, { method: "DELETE", token });
