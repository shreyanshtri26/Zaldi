import { useEffect, useRef, useState } from "react";
import { addToCart, getCart, sendChat } from "../../api/client.js";
import AppShell from "../../shared/components/AppShell.jsx";
import Icon from "../../shared/components/Icon.jsx";
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
    const chatId = append(activeId, { role: "user", text: text || "Find something like this photo", image: Boolean(image) });
    const startedAt = Date.now();
    setBusy(true);
    try {
      const r = await sendChat(text, image);
      if (r.cart) setCart(r.cart);
      append(chatId, {
        role: "bot", text: r.response, route: r.type, ms: Date.now() - startedAt, at: Date.now(),
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
    try { setCart(await addToCart(product.id)); toast(`Added ${product.product_name}`); }
    catch (e) { toast(e.message, "bad"); }
    finally { setAdding(null); }
  }

  const started = (active?.messages?.length || 0) > 0; // the welcome page already says "Zaldi", so the bar adds the name only once a chat is under way
  // Left: start a conversation (and which one is open). Right: tools for this chat, then the shop.
  const nav = (
    <>
      {started && <span className="chat-title">{settings.brand_name}</span>}
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
        <a className="nav-btn" href="/admin" aria-label="Apps and admin panel" data-tip="Apps"><Icon name="grid" size={20} /></a>
      </div>
    </>
  );

  return (
    <AppShell nav={nav} actions={actions} raised>
      <ChatPanel messages={active?.messages || []} busy={busy} onSend={send} onAdd={add} addingId={adding} onOpenCart={setPanel} />
      {panel && <CartPanel key={panel} cart={cart} onCart={setCart} startAt={panel} onClose={() => setPanel(null)} />}
    </AppShell>
  );
}

export default function ChatPage() {
  return <ToastProvider><ChatScreen /></ToastProvider>;
}
