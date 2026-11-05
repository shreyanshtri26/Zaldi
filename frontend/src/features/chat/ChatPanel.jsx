import { useEffect, useRef, useState } from "react";
import BotAvatar from "../../shared/components/BotAvatar.jsx";
import Icon from "../../shared/components/Icon.jsx";
import { useSiteConfig } from "../../shared/context/SiteConfigContext.jsx";
import useLenis from "../../shared/hooks/useLenis.js";
import { AgentCompleted, AgentWorking } from "./AgentStatus.jsx";
import ProductCards from "./ProductCards.jsx";

function Reply({ message, onAdd, addingId, onOpenCart }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(message.text); setCopied(true); setTimeout(() => setCopied(false), 1200); } catch {}
  };
  return (
    <div className="turn">
      <BotAvatar />
      <div style={{ flex: 1, minWidth: 0 }}>
        {!message.error && <AgentCompleted route={message.route} ms={message.ms} />}
        <div className={`reply${message.error ? " error" : ""}`}>{message.text}</div>
        <ProductCards products={message.products} onAdd={onAdd} busyId={addingId} />
        {message.route === "cart" && message.cartCount > 0 && <button className="btn ghost sm cta" onClick={() => onOpenCart("cart")}><Icon name="cart" size={15} /> View cart</button>}
        {message.action === "collect_address" && <button className="btn sm cta" onClick={() => onOpenCart("address")}>Enter delivery details</button>}
        {!message.error && (
          <div className="reply-actions">
            <button className="icon-btn" onClick={copy} aria-label="Copy reply" title={copied ? "Copied" : "Copy"}><Icon name="copy" size={16} /></button>
          </div>
        )}
      </div>
    </div>
  );
}

function Composer({ busy, onSend, placeholder, boxRef, photo = true }) {
  const [input, setInput] = useState("");
  const [image, setImage] = useState(null);
  const file = useRef(null);
  function submit() {
    const text = input.trim();
    if ((!text && !image) || busy) return;
    setInput(""); setImage(null);
    if (boxRef.current) boxRef.current.style.height = "auto";
    onSend(text, image);
  }
  function grow(e) {
    setInput(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px";
  }
  return (
    <form className="composer" onSubmit={(e) => { e.preventDefault(); submit(); }}>
      <input ref={file} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={(e) => { setImage(e.target.files[0] || null); e.target.value = ""; }} />
      {photo && <button type="button" className="icon-btn" aria-label="Attach a photo" title="Search by photo" onClick={() => file.current.click()}><Icon name="image" size={18} /></button>}
      <div className="composer-main">
        {image && <span className="attach"><Icon name="image" size={13} />{image.name}<button type="button" aria-label="Remove photo" onClick={() => setImage(null)}>×</button></span>}
        <label className="sr" htmlFor="msg">Message</label>
        <textarea id="msg" ref={boxRef} rows={1} value={input} onChange={grow} placeholder={image ? "Add a note (optional)" : placeholder}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }} />
      </div>
      <button className="send" disabled={busy || (!input.trim() && !image)} aria-label="Send message"><Icon name="send" /></button>
    </form>
  );
}

// Empty state: composer sits in the middle of the canvas with suggestion chips. Once a chat starts it docks to the bottom.
export default function ChatPanel({ messages, busy, onSend, onAdd, addingId, onOpenCart }) {
  const { settings, quickActions } = useSiteConfig();
  const box = useRef(null);
  const wrapper = useRef(null);
  const end = useRef(null);
  const lenis = useLenis(wrapper);
  const empty = messages.length === 0;

  useEffect(() => {
    if (lenis.current) lenis.current.scrollTo(end.current, { offset: 200 });
    else end.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy, lenis]);

  const composer = <Composer busy={busy} onSend={onSend} placeholder={settings.input_placeholder} boxRef={box} photo={settings.photo_button !== "hide"} />;

  const pos = settings.bar_position;
  const inline = empty && pos === "center";
  const dock = (
    <div className={`composer-wrap ${pos === "top" ? "top" : ""}`}>
      {composer}
      {pos !== "top" && <div className="hint">Enter to send · Shift+Enter for a new line</div>}
    </div>
  );
  const chips = (
    <div className={`chips ${settings.cards_align} ${settings.cards_position}`}>
      {quickActions.map(({ id, icon, title, message }) => (
        <button key={id} className="chip" onClick={() => onSend(message)}><Icon name={icon} size={15} />{title}</button>
      ))}
    </div>
  );

  return (
    <div className="chat-area">
      {pos === "top" && dock}
      <div className="thread" ref={wrapper}>
        <div className="thread-in">
          {empty ? (
            <div className="welcome">
              <span className="mark lg" role="img" aria-label="Zaldi" style={{ display: "inline-block" }} />
              <h2>{settings.welcome_heading}</h2>
              <p>{settings.welcome_subtitle}</p>
              {settings.cards_position === "above" && chips}
              {inline && composer}
              {settings.cards_position !== "above" && chips}
            </div>
          ) : (
            <div className="col">
              {messages.map((m, i) =>
                m.role === "user"
                  ? <div key={i} className="turn user"><div className="bubble">{m.text}</div></div>
                  : <Reply key={i} message={m} onAdd={onAdd} addingId={addingId} onOpenCart={onOpenCart} />)}
              {busy && <div className="turn"><BotAvatar active /><AgentWorking /></div>}
              <div ref={end} />
            </div>
          )}
        </div>
      </div>
      {!inline && pos !== "top" && dock}
    </div>
  );
}
