// When the assistant runs inside a frame on a shop's website (?embed=1), it talks to that page through messages.
// The page can tell it what the shopper is looking at; it tells the page when the shopper adds or opens a product.
const params = new URLSearchParams(window.location.search);
export const embedded = params.get("embed") === "1" && window.parent !== window;

let pageContext = null;
export const getPage = () => pageContext;

export function postToHost(type, data) {
  if (embedded) window.parent.postMessage({ type: `zaldi:${type}`, data }, "*"); // the widget on the page checks who sent it
}

if (embedded) {
  window.addEventListener("message", (e) => {
    if (e.source !== window.parent || e.data?.type !== "zaldi:context") return;
    const p = e.data.page;
    pageContext = p && typeof p === "object" ? { title: p.title, price: p.price, sku: p.sku, category: p.category } : null;
  });
  postToHost("ready");
}
