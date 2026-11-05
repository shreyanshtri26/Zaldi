import { useEffect, useRef, useState } from "react";
import { addToCart, getCart, sendChat } from "../../api/client.js";
import AppShell from "../../shared/components/AppShell.jsx";
import Icon from "../../shared/components/Icon.jsx";
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
      <summary className="btn ghost sm"><Icon name="clock" size={15} /> History</summary>
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

  useEffect(() => { getCart().then(setCart).catch(() => {}); }, []);

  async function send(text, image) {
    const chatId = append(activeId, { role: "user", text: text || "Find something like this photo", image: Boolean(image) });
    const startedAt = Date.now();
    setBusy(true);
    try {
      const r = await sendChat(text, image);
      if (r.cart) setCart(r.cart);
      append(chatId, {
        role: "bot", text: r.response, route: r.type, ms: Date.now() - startedAt,
        products: r.products, relaxed: r.relaxed, action: r.action, cartCount: r.cart?.item_count,
      });
      if (r.action === "collect_address") setPanel("address");
    } catch (e) {
      append(chatId, { role: "bot", text: `Sorry, something went wrong: ${e.message}`, error: true });
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

  const nav = active && <span className="chat-title">{active.title}</span>;
  const actions = (
    <>
      <History chats={chats} activeId={activeId} onSelect={select} onRemove={remove} />
      <button className="btn ghost sm" onClick={newChat}><Icon name="plus" size={15} /> New chat</button>
      <PreferencesMenu />
      <button className="icon-btn cart-btn" aria-label={`Cart, ${cart.item_count} items`} title="Cart" onClick={() => setPanel("cart")}>
        <Icon name="cart" size={18} />{cart.item_count > 0 && <b className="badge">{cart.item_count}</b>}
      </button>
      <a className="icon-btn" href="/admin" aria-label="Admin panel" title="Admin panel"><Icon name="dash" size={17} /></a>
    </>
  );

  return (
    <AppShell nav={nav} actions={actions}>
      <ChatPanel messages={active?.messages || []} busy={busy} onSend={send} onAdd={add} addingId={adding} onOpenCart={setPanel} />
      {panel && <CartPanel key={panel} cart={cart} onCart={setCart} startAt={panel} onClose={() => setPanel(null)} />}
    </AppShell>
  );
}

export default function ChatPage() {
  return <ToastProvider><ChatScreen /></ToastProvider>;
}
