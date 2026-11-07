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
// Like sendChat, but each tool step is reported as it finishes (onStep), then the answer is returned. Photos use sendChat.
export async function sendChatStream(message, history, onStep) {
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Session-Id": sessionId(), ...(storeSlug() ? { "X-Store": storeSlug() } : {}) },
    body: JSON.stringify({ message, history, page: getPage() || undefined }),
  });
  if (!res.ok || !res.body) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || "Something went wrong. Please try again in a moment.");
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let cut;
    while ((cut = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      const event = /^event: (.+)$/m.exec(block)?.[1];
      const data = /^data: (.+)$/m.exec(block)?.[1];
      if (!event || !data) continue;
      const payload = JSON.parse(data);
      if (event === "step") onStep?.(payload);
      else if (event === "error") throw new Error(payload.error || "Something went wrong. Please try again in a moment.");
      else if (event === "done") return payload;
    }
  }
  throw new Error("The answer was cut off. Please try again.");
}
export const accountLogin = (email, password) => request("/admin/account-login", { method: "POST", body: { email, password } });
export const signupStore = (body) => request("/signup", { method: "POST", body });
export const getEmbed = (token) => request("/admin/embed", { token });
// AI model: provider, keys (write-only), model dropdown, test
export const getAiSettings = (token) => request("/admin/ai-key", { token });
export const saveAiKey = (provider, api_key, token) => request("/admin/ai-key", { method: "PUT", body: { provider, api_key }, token });
export const removeAiKey = (provider, token) => request(`/admin/ai-key?provider=${provider}`, { method: "DELETE", token });
export const testAiKey = (provider, token) => request("/admin/ai-key/test", { method: "POST", body: { provider }, token });
export const getAiModels = (provider, token) => request(`/admin/ai-models?provider=${provider}`, { token });
export const saveAiModel = (provider, model, token) => request("/admin/ai-model", { method: "PUT", body: { provider, model }, token });
export const resetAiModel = (provider, token) => request(`/admin/ai-model?provider=${provider}`, { method: "DELETE", token });
export const saveAiProvider = (provider, token) => request("/admin/ai-provider", { method: "PUT", body: { provider }, token });
export const resetAiProvider = (token) => request("/admin/ai-provider", { method: "DELETE", token });
// Server settings (server admin only) and account password
export const getServerSettings = (token) => request("/admin/server", { token });
export const changeServerPassword = (current, next, token) => request("/admin/server/password", { method: "PUT", body: { current, new: next }, token });
export const removeServerPassword = (current, token) => request("/admin/server/password", { method: "DELETE", body: { current }, token });
export const testDatabase = (url, token) => request("/admin/server/database/test", { method: "POST", body: { url }, token });
export const saveDatabase = (url, token) => request("/admin/server/database", { method: "PUT", body: { url }, token });
export const removeDatabase = (token) => request("/admin/server/database", { method: "DELETE", token });
export const copyDatabase = (url, replace, confirm, token) => request("/admin/server/database/copy", { method: "POST", body: { url, replace, confirm }, token });
export const restartServer = (confirm, token) => request("/admin/server/restart", { method: "POST", body: { confirm }, token });
export const changeAccountPassword = (current, next, token) => request("/admin/account/password", { method: "PUT", body: { current, new: next }, token });
// Sign-in steps, password reset, and the account's own two-step settings
export const accountLoginTwoStep = (challenge, code) => request("/admin/account-login/two-step", { method: "POST", body: { challenge, code } });
export const forgotPassword = (email) => request("/admin/forgot-password", { method: "POST", body: { email } });
export const resetPassword = (token, next) => request("/admin/password-reset", { method: "POST", body: { token, new: next } });
export const getTwoStep = (token) => request("/admin/account/two-step", { token });
export const setupTwoStep = (password, token) => request("/admin/account/two-step/setup", { method: "POST", body: { password }, token });
export const enableTwoStep = (code, token) => request("/admin/account/two-step/enable", { method: "POST", body: { code }, token });
export const disableTwoStep = (password, code, token) => request("/admin/account/two-step/disable", { method: "POST", body: { password, code }, token });
// Stores and accounts (server admin)
export const listStoresAdmin = (token) => request("/admin/stores", { token });
export const createStoreAdmin = (slug, name, token) => request("/admin/stores", { method: "POST", body: { slug, name }, token });
export const setStoreStatus = (slug, status, token) => request(`/admin/stores/${slug}`, { method: "PUT", body: { status }, token });
export const deleteStoreAdmin = (slug, confirm, token) => request(`/admin/stores/${slug}`, { method: "DELETE", body: { confirm }, token });
export const listAccountsAdmin = (slug, token) => request(`/admin/stores/${slug}/accounts`, { token });
export const createAccountAdmin = (slug, body, token) => request(`/admin/stores/${slug}/accounts`, { method: "POST", body, token });
export const setAccountRole = (slug, email, role, token) => request(`/admin/stores/${slug}/accounts/${encodeURIComponent(email)}`, { method: "PUT", body: { role }, token });
export const deleteAccountAdmin = (slug, email, token) => request(`/admin/stores/${slug}/accounts/${encodeURIComponent(email)}`, { method: "DELETE", token });
export const accountResetLink = (slug, email, token) => request(`/admin/stores/${slug}/accounts/${encodeURIComponent(email)}/reset-link`, { method: "POST", token });
export const accountTwoStepOff = (slug, email, token) => request(`/admin/stores/${slug}/accounts/${encodeURIComponent(email)}/two-step/disable`, { method: "POST", token });
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
