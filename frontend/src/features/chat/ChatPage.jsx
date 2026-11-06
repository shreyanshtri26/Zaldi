import { useEffect, useRef, useState } from "react";
import { postToHost } from "../../shared/embed.js";
import { addToCart, getCart, sendChat, setCartQuantity } from "../../api/client.js";
import AppShell from "../../shared/components/AppShell.jsx";
import Icon from "../../shared/components/Icon.jsx";
import { useAuth } from "../../shared/context/AuthContext.jsx";
import { useSiteConfig } from "../../shared/context/SiteConfigContext.jsx";
import { ToastProvider, useToast } from "../../shared/context/ToastContext.jsx";
import CartPanel from "./CartPanel.jsx";
import ChatPanel from "./ChatPanel.jsx";
import PreferencesMenu from "./PreferencesMenu.jsx";
import useChats from "./useChats.js";

const EMPTY_CART = { items: [], item_count: 0, subtotal: 0, discount: 0, shipping: 0, total: 0, warnings: [], free_shipping_gap: 0 };

// Chat history lives in a popover in the top bar instead of a sidebar.
function History({ chats, activeId, onSelect, onRemove }) {
  const box = useRef(null);
  const close = () => { if (box.current) box.current.open = false; };
  return (
    <details className="history" ref={box}>
      <summary className="nav-btn" aria-label="History" data-tip="History"><Icon name="clock" size={20} /></summary>
      <div className="history-pop">
        {chats.map((c) => (
          <div key={c.id} className={`convo${c.id === activeId ? " active" : ""}`}>
            <button onClick={() => { onSelect(c.id); close(); }} title={c.title}>{c.title}</button>
            <button className="icon-btn" aria-label={`Delete ${c.title}`} onClick={() => onRemove(c.id)}><Icon name="trash" size={15} /></button>
          </div>
        ))}
        {!chats.length && <div className="empty">No chats yet</div>}
      </div>
    </details>
  );
}

function ChatScreen() {
  const { chats, active, activeId, select, newChat, append, remove } = useChats();
  const [busy, setBusy] = useState(false);
  const [cart, setCart] = useState(EMPTY_CART);
  const [panel, setPanel] = useState(null); // null | "cart" | "address"
  const [adding, setAdding] = useState(null);
  const toast = useToast();
  const { settings } = useSiteConfig();
  const { token, logout } = useAuth(); // the admin link is shown only while an admin is signed in

  useEffect(() => { getCart().then(setCart).catch(() => {}); }, []);

  // Top-bar popovers (<details>) close on Escape or a click outside them.
  useEffect(() => {
    const closeAll = (keep) => document.querySelectorAll("details.history[open]").forEach((d) => { if (d !== keep) d.open = false; });
    const onKey = (e) => e.key === "Escape" && closeAll();
    const onClick = (e) => closeAll(e.target.closest("details.history"));
    document.addEventListener("keydown", onKey);
    document.addEventListener("click", onClick);
    return () => { document.removeEventListener("keydown", onKey); document.removeEventListener("click", onClick); };
  }, []);

  async function send(text, image) {
    // Hidden chat commands: handled here, never sent to the assistant.
    const cmd = (text || "").trim().toLowerCase();
    if (!image && (cmd === "@admin login" || cmd === "@admin logout")) {
      const chatId = append(activeId, { role: "user", text: text.trim() });
      if (cmd === "@admin logout") { logout(); append(chatId, { role: "bot", text: "Admin mode is off." }); }
      else if (token) append(chatId, { role: "bot", text: "You are already in admin mode." });
      else append(chatId, { role: "bot", text: "Enter the admin password.", adminPrompt: true });
      return;
    }
    const chatId = append(activeId, { role: "user", text: text || "Find something like this photo", image: Boolean(image) });
    const startedAt = Date.now();
    setBusy(true);
    try {
      // the last few turns, so follow-ups like "add the cheaper one" have something to refer to
      const history = (active?.messages || []).filter((m) => m.text && !m.error).slice(-6).map((m) => ({ role: m.role === "user" ? "user" : "assistant", text: m.text }));
      const r = await sendChat(text, image, history);
      if (r.cart) setCart(r.cart);
      append(chatId, {
        role: "bot", text: r.response, route: r.type, ms: Date.now() - startedAt, at: Date.now(), steps: r.steps, quickReplies: r.quick_replies, chatId: r.chat_id,
        products: r.products, relaxed: r.relaxed, action: r.action, cartCount: r.cart?.item_count,
      });
      if (r.action === "collect_address") setPanel("address");
    } catch (e) {
      append(chatId, { role: "bot", text: e.message, error: true });
    } finally {
      setBusy(false);
    }
  }

  async function add(product) {
    setAdding(product.id);
    try { setCart(await addToCart(product.id)); toast(`Added ${product.product_name}`); postToHost("add-to-cart", { id: product.id, name: product.product_name, price: product.price }); }
    catch (e) { toast(e.message, "bad"); }
    finally { setAdding(null); }
  }

  // Left: start a conversation (and which one is open). Right: tools for this chat, then the shop.
  // Quantity of each product already in the cart, so cards in replies can show - 1 + instead of Add.
  const cartQty = Object.fromEntries(cart.items.map((i) => [i.id, i.quantity]));
  async function setQty(product, quantity) {
    setAdding(product.id);
    try { setCart(await setCartQuantity(product.id, quantity)); }
    catch (e) { toast(e.message, "bad"); }
    finally { setAdding(null); }
  }

  const nav = (
    <>
      {busy && <span className="chat-title">{settings.brand_name}</span>}
      <button className="nav-btn primary" onClick={newChat} aria-label="New chat" data-tip="New chat"><span className="plus"><Icon name="plus" size={14} /></span><span className="nav-label">New chat</span></button>
    </>
  );
  const actions = (
    <>
      <div className="nav-group" role="group" aria-label="Chat tools">
        <History chats={chats} activeId={activeId} onSelect={select} onRemove={remove} />
        <PreferencesMenu />
      </div>
      <div className="nav-group" role="group" aria-label="Shop">
        <button className="nav-btn cart-btn" aria-label={`Cart, ${cart.item_count} items`} data-tip="Cart" onClick={() => setPanel("cart")}>
          <Icon name="cart" size={20} />{cart.item_count > 0 && <b key={cart.item_count} className="badge pop">{cart.item_count}</b>}
        </button>
        {token && <a className="nav-btn" href="/admin" aria-label="Admin panel" data-tip="Admin"><Icon name="grid" size={20} /></a>}
      </div>
    </>
  );

  return (
    <AppShell nav={nav} actions={actions} raised>
      <ChatPanel messages={active?.messages || []} busy={busy} onSend={send} onAdd={add} onSetQty={setQty} cartQty={cartQty} addingId={adding} onOpenCart={setPanel} />
      {panel && <CartPanel key={panel} cart={cart} onCart={setCart} startAt={panel} onClose={() => setPanel(null)} />}
    </AppShell>
  );
}

export default function ChatPage() {
  return <ToastProvider><ChatScreen /></ToastProvider>;
}
