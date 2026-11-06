/* Zaldi chat widget. Add to any site:
 *   <script src="https://YOUR-ZALDI-HOST/widget.js" data-store="your-store-id" async></script>
 * It adds a floating button that opens the assistant in an isolated frame, so it can never clash with the host page's styles.
 * Optional attributes: data-position="left", data-open="true".
 * Page API: Zaldi.open(), Zaldi.close(), Zaldi.setContext({title, price, sku, category}) to tell the assistant what the shopper is
 * viewing, and Zaldi.on("add-to-cart" | "product-open" | "ready", fn) to hear what the shopper does in the chat. */
(function () {
  if (window.__zaldiWidget) return;
  window.__zaldiWidget = true;
  var script = document.currentScript;
  var host = new URL(script ? script.src : location.href).origin;
  var store = (script && script.getAttribute("data-store")) || "";
  var side = script && script.getAttribute("data-position") === "left" ? "left" : "right";
  var css = "position:fixed;z-index:2147483000;";
  var button = document.createElement("button");
  button.type = "button";
  button.setAttribute("aria-label", "Open Zaldi assistant");
  button.style.cssText = css + side + ":20px;bottom:20px;width:56px;height:56px;border:0;border-radius:50%;cursor:pointer;" +
    "background:radial-gradient(circle at 50% 44%,#C1F75A,#79B83D 64%,#2F5A14);box-shadow:0 6px 20px rgba(0,0,0,.35)";
  var frame = document.createElement("iframe");
  frame.title = "Zaldi assistant";
  frame.hidden = true;
  frame.style.cssText = css + side + ":20px;bottom:88px;width:min(400px,calc(100vw - 24px));height:min(640px,calc(100vh - 110px));" +
    "border:1px solid #303A31;border-radius:16px;background:#090B0A;box-shadow:0 12px 40px rgba(0,0,0,.45)";

  var context = null;
  var listeners = {};
  function send(message) {
    if (frame.contentWindow) frame.contentWindow.postMessage(message, host); // only ever to the Zaldi host
  }
  function emit(type, data) {
    (listeners[type] || []).forEach(function (fn) { try { fn(data); } catch (e) { /* a host handler must not break the widget */ } });
    window.dispatchEvent(new CustomEvent("zaldi:" + type, { detail: data }));
  }
  window.addEventListener("message", function (e) {
    if (e.origin !== host || e.source !== frame.contentWindow) return; // messages from anyone else are ignored
    var m = e.data;
    if (!m || typeof m.type !== "string" || m.type.indexOf("zaldi:") !== 0) return;
    var type = m.type.slice(6);
    if (type === "ready" && context) send({ type: "zaldi:context", page: context });
    emit(type, m.data);
  });

  function setOpen(open) {
    if (open && !frame.src) frame.src = host + "/?embed=1" + (store ? "&store=" + encodeURIComponent(store) : ""); // load on first open, not on every page view
    frame.hidden = !open;
    button.setAttribute("aria-expanded", String(open));
  }
  button.addEventListener("click", function () { setOpen(frame.hidden); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !frame.hidden) { setOpen(false); button.focus(); } });
  window.Zaldi = {
    open: function () { setOpen(true); },
    close: function () { setOpen(false); },
    setContext: function (page) { context = page || null; send({ type: "zaldi:context", page: context }); },
    on: function (type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
  };
  document.body.appendChild(frame);
  document.body.appendChild(button);
  if (script && script.getAttribute("data-open") === "true") setOpen(true);
})();
