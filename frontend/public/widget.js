/* Zaldi chat widget. Add to any site:
 *   <script src="https://YOUR-ZALDI-HOST/widget.js" async></script>
 * It adds a floating button that opens the assistant in an isolated frame, so it can never clash with the host page's styles. */
(function () {
  if (window.__zaldiWidget) return;
  window.__zaldiWidget = true;
  var host = new URL(document.currentScript ? document.currentScript.src : location.href).origin;
  var css = "position:fixed;z-index:2147483000;";
  var button = document.createElement("button");
  button.type = "button";
  button.setAttribute("aria-label", "Open Zaldi assistant");
  button.style.cssText = css + "right:20px;bottom:20px;width:56px;height:56px;border:0;border-radius:50%;cursor:pointer;" +
    "background:radial-gradient(circle at 50% 44%,#C1F75A,#79B83D 64%,#2F5A14);box-shadow:0 6px 20px rgba(0,0,0,.35)";
  var frame = document.createElement("iframe");
  frame.title = "Zaldi assistant";
  frame.hidden = true;
  frame.style.cssText = css + "right:20px;bottom:88px;width:min(400px,calc(100vw - 24px));height:min(640px,calc(100vh - 110px));" +
    "border:1px solid #303A31;border-radius:16px;background:#090B0A;box-shadow:0 12px 40px rgba(0,0,0,.45)";
  button.addEventListener("click", function () {
    if (!frame.src) frame.src = host + "/"; // load the assistant on first open, not on every page view
    frame.hidden = !frame.hidden;
    button.setAttribute("aria-expanded", String(!frame.hidden));
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !frame.hidden) { frame.hidden = true; button.focus(); } });
  document.body.appendChild(frame);
  document.body.appendChild(button);
})();
