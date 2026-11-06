import { useEffect, useRef, useState } from "react";
import { sendFeedback } from "../../api/client.js";
import Accent from "../../shared/components/Accent.jsx";
import BotAvatar from "../../shared/components/BotAvatar.jsx";
import Icon from "../../shared/components/Icon.jsx";
import Orb from "../../shared/components/Orb.jsx";
import { useSiteConfig } from "../../shared/context/SiteConfigContext.jsx";
import useLenis from "../../shared/hooks/useLenis.js";
import { AgentCompleted, AgentWorking } from "./AgentStatus.jsx";
import AdminPrompt from "./AdminPrompt.jsx";
import ProductCards from "./ProductCards.jsx";
import Typed from "./Typed.jsx";

function Reply({ message, onAdd, onSetQty, cartQty, addingId, onOpenCart, onSend, showReplies }) {
  const [copied, setCopied] = useState(false);
  const [rated, setRated] = useState(0);
  // A reply that has just arrived types itself in; older messages (history, reload) appear at once.
  const [animate] = useState(() => !message.error && Boolean(message.at) && Date.now() - message.at < 4000);
  const [done, setDone] = useState(!animate);
  const copy = async () => {
    try { await navigator.clipboard.writeText(message.text); setCopied(true); setTimeout(() => setCopied(false), 1200); } catch {}
  };
  const rate = (rating) => {
    setRated(rating);
    sendFeedback(message.chatId, rating).catch(() => setRated(0));
  };
  return (
    <div className="turn">
      <BotAvatar />
      <div style={{ flex: 1, minWidth: 0 }}>
        {!message.error && <AgentCompleted route={message.route} ms={message.ms} steps={message.steps} />}
        <div className={`reply${message.error ? " error" : ""}`}><Typed text={message.text} animate={animate} onDone={() => setDone(true)} /></div>
        {message.adminPrompt && showReplies && <AdminPrompt />}
        {done && <ProductCards products={message.products} onAdd={onAdd} onSetQty={onSetQty} cartQty={cartQty} busyId={addingId} />}
        {done && message.route === "cart" && message.cartCount > 0 && <button className="btn ghost sm cta" onClick={() => onOpenCart("cart")}><Icon name="cart" size={15} /> View cart</button>}
        {done && message.action === "collect_address" && <button className="btn sm cta" onClick={() => onOpenCart("address")}>Enter delivery details</button>}
        {done && showReplies && message.quickReplies?.length > 0 && (
          <div className="chips left quick" role="group" aria-label="Quick replies">
            {message.quickReplies.map((q) => <button key={q} className="chip" onClick={() => onSend(q)}>{q}</button>)}
          </div>
        )}
        {done && !message.error && (
          <div className="reply-actions">
            <button className="icon-btn" onClick={copy} aria-label="Copy reply" title={copied ? "Copied" : "Copy"}><Icon name="copy" size={16} /></button>
            {message.chatId && (
              <>
                <button className={`icon-btn${rated === 1 ? " on" : ""}`} onClick={() => rate(1)} aria-pressed={rated === 1} aria-label="Good answer" title="Good answer"><Icon name="thumbUp" size={16} /></button>
                <button className={`icon-btn${rated === -1 ? " on" : ""}`} onClick={() => rate(-1)} aria-pressed={rated === -1} aria-label="Bad answer" title="Bad answer"><Icon name="thumbDown" size={16} /></button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Composer({ busy, onSend, onListening, placeholder, boxRef, photo = true }) {
  const [input, setInput] = useState("");
  const [image, setImage] = useState(null);
  const file = useRef(null);
  const [listening, setListening] = useState(false);
  useEffect(() => { onListening?.(listening); }, [listening, onListening]);
  const Speech = typeof window !== "undefined" && (window.SpeechRecognition || window.webkitSpeechRecognition);
  function dictate() {
    const r = new Speech();
    r.lang = "en-IN"; r.interimResults = false;
    r.onresult = (e) => setInput((v) => (v ? v + " " : "") + e.results[0][0].transcript);
    r.onend = r.onerror = () => setListening(false);
    setListening(true); r.start();
  }
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
      {photo && <button type="button" className="icon-btn" aria-label="Attach a photo" title="Search by photo" onClick={() => file.current.click()}><svg width="18" height="18" fill="currentColor" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5"/><path d="M7.646 1.146a.5.5 0 0 1 .708 0l3 3a.5.5 0 0 1-.708.708L8.5 2.707V11.5a.5.5 0 0 1-1 0V2.707L5.354 4.854a.5.5 0 1 1-.708-.708z"/></svg></button>}
      <div className="composer-main">
        {image && <span className="attach"><Icon name="image" size={13} />{image.name}<button type="button" aria-label="Remove photo" onClick={() => setImage(null)}>×</button></span>}
        <label className="sr" htmlFor="msg">Message</label>
        <textarea id="msg" ref={boxRef} rows={1} value={input} onChange={grow} placeholder={image ? "Add a note (optional)" : placeholder}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }} />
      </div>
      {Speech && <button type="button" className={`icon-btn mic${listening ? " on" : ""}`} aria-label="Voice input" aria-pressed={listening} title="Speak your message" disabled={listening} onClick={dictate}><Icon name="mic" size={18} /></button>}
      <button className="send" disabled={busy || (!input.trim() && !image)} aria-label="Send message"><Icon name="send" /></button>
    </form>
  );
}

// Empty state: composer sits in the middle of the canvas with suggestion chips. Once a chat starts it docks to the bottom.
export default function ChatPanel({ messages, busy, onSend, onAdd, onSetQty, cartQty, addingId, onOpenCart }) {
  const { settings, quickActions } = useSiteConfig();
  const box = useRef(null);
  const wrapper = useRef(null);
  const end = useRef(null);
  const lenis = useLenis(wrapper);
  const empty = messages.length === 0;

  // One state for every orb on screen, derived from what the chat is doing right now.
  const [listening, setListening] = useState(false);
  const [hidden, setHidden] = useState(document.hidden);
  const [replied, setReplied] = useState(false);
  useEffect(() => {
    const on = () => setHidden(document.hidden);
    document.addEventListener("visibilitychange", on);
    return () => document.removeEventListener("visibilitychange", on);
  }, []);
  const last = messages[messages.length - 1];
  useEffect(() => {
    if (last?.role !== "bot") return;
    setReplied(true);
    const t = setTimeout(() => setReplied(false), 700);
    return () => clearTimeout(t);
  }, [last]);
  const orbState = hidden || last?.error ? "inactive" : busy ? "processing" : listening ? "listening" : replied ? "responding" : "idle";

  useEffect(() => {
    if (lenis.current) lenis.current.scrollTo(end.current, { offset: 200 });
    else end.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy, lenis]);

  const composer = <Composer busy={busy} onListening={setListening} onSend={onSend} placeholder={settings.input_placeholder} boxRef={box} photo={settings.photo_button !== "hide"} />;

  const pos = settings.bar_position;
  const inline = empty && pos === "center";
  const dock = (
    <div className={`composer-wrap ${pos === "top" ? "top" : ""}`}>
      {composer}
      {pos !== "top" && <div className="hint">Enter to send · Shift+Enter for a new line</div>}
    </div>
  );
  const chips = (
    <div className="chips help-line">
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
              <div className="welcome-orb"><Orb state={orbState} size={80} smoke /></div>
              <p className="greeting">{settings.welcome_greeting}</p>
              <h2><Accent text={settings.welcome_heading} /></h2>
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
                  : <Reply key={i} message={m} onAdd={onAdd} onSetQty={onSetQty} cartQty={cartQty} addingId={addingId} onOpenCart={onOpenCart} onSend={onSend} showReplies={i === messages.length - 1 && !busy} />)}
              {busy && <div className="turn"><div className="av-col"><BotAvatar active /><span>{settings.brand_name || "Zaldi"}</span></div><AgentWorking /></div>}
              <div ref={end} />
            </div>
          )}
        </div>
      </div>
      {!inline && pos !== "top" && dock}
    </div>
  );
}
