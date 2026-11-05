import { useEffect, useState } from "react";
import { applyCoupon, cancelCheckout, confirmCheckout, prepareCheckout, removeFromCart, setCartQuantity } from "../../api/client.js";
import Icon from "../../shared/components/Icon.jsx";
import { inr } from "../../shared/utils/format.js";

const FIELDS = [["full_name", "Full name", "name"], ["phone", "Mobile number", "tel"], ["line1", "Address", "street-address"],
  ["city", "City", "address-level2"], ["state", "State", "address-level1"], ["pincode", "PIN code", "postal-code"]];
const PREP_STEPS = ["Opening checkout in a secure browser", "Filling in your delivery details", "Stopping before payment"];

function Totals({ t }) {
  return (
    <dl className="totals">
      <dt>Subtotal</dt><dd>{inr(t.subtotal)}</dd>
      {t.discount > 0 && <><dt>Discount</dt><dd>-{inr(t.discount)}</dd></>}
      <dt>Shipping</dt><dd>{t.shipping ? inr(t.shipping) : "Free"}</dd>
      <dt className="grand">Total</dt><dd className="grand">{inr(t.total)}</dd>
    </dl>
  );
}

// Cart + checkout in one slide-over: cart -> address -> (browser prepares the order) -> review & confirm -> done.
// Nothing is ordered until the customer presses "Confirm order"; payment is never taken here.
export default function CartPanel({ cart, onCart, onClose, startAt = "cart" }) {
  const [step, setStep] = useState(startAt === "address" && cart.items.length ? "address" : "cart");
  const [address, setAddress] = useState({});
  const [method, setMethod] = useState("standard");
  const [order, setOrder] = useState(null);
  const [error, setError] = useState("");
  const [coupon, setCoupon] = useState("");
  const [prep, setPrep] = useState(0);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  useEffect(() => {
    if (step !== "preparing") return;
    const t = setInterval(() => setPrep((n) => Math.min(n + 1, PREP_STEPS.length - 1)), 1200);
    return () => clearInterval(t);
  }, [step]);

  const run = async (fn) => { setError(""); try { return await fn(); } catch (e) { setError(e.message); } };
  const edit = (fn) => run(async () => onCart(await fn()));

  const submitAddress = async (e) => {
    e.preventDefault();
    setStep("preparing"); setPrep(0);
    const prepared = await run(() => prepareCheckout(address, method));
    if (prepared) { setOrder(prepared); setStep("review"); } else setStep("address");
  };
  const confirm = async () => {
    const done = await run(() => confirmCheckout(order.token));
    if (done) { setOrder({ ...order, ...done }); setStep("done"); onCart({ ...cart, items: [], item_count: 0, subtotal: 0, discount: 0, shipping: 0, total: 0 }); }
  };
  const cancel = async () => { await run(() => cancelCheckout(order.token)); setOrder(null); setStep("cart"); };

  return (
    <>
      <div className="overlay" onClick={onClose} />
      <aside className="drawer cart-panel" role="dialog" aria-label="Your cart">
        <header>
          {step === "cart" ? "Your cart" : step === "address" ? "Delivery details" : step === "review" ? "Review and confirm" : step === "done" ? "Order placed" : "Preparing your order"}
          <span className="spacer" /><button className="icon-btn" aria-label="Close" onClick={onClose}><Icon name="x" /></button>
        </header>
        <div className="cart-body">
          {error && <p className="form-error" role="alert">{error}</p>}

          {step === "cart" && (cart.items.length === 0 ? <div className="empty">Your cart is empty.<br />Ask Zaldi to find something you like.</div> : (
            <>
              <ul className="cart-lines">
                {cart.items.map((i) => (
                  <li key={i.id}>
                    <div><b>{i.product_name}</b><span>{[i.brand, i.color].filter(Boolean).join(" · ")} · {inr(i.price)}</span></div>
                    <div className="qty">
                      <button aria-label="Decrease" onClick={() => edit(() => setCartQuantity(i.id, i.quantity - 1))}>−</button>
                      <span>{i.quantity}</span>
                      <button aria-label="Increase" onClick={() => edit(() => setCartQuantity(i.id, i.quantity + 1))}>+</button>
                    </div>
                    <strong>{inr(i.line_total)}</strong>
                    <button className="icon-btn" aria-label={`Remove ${i.product_name}`} onClick={() => edit(() => removeFromCart(i.id))}><Icon name="trash" size={15} /></button>
                  </li>
                ))}
              </ul>
              {cart.warnings.map((w) => <p key={w} className="form-error">{w}</p>)}
              <form className="coupon" onSubmit={(e) => { e.preventDefault(); coupon && edit(() => applyCoupon(coupon)).then(() => setCoupon("")); }}>
                <input className="input" placeholder="Coupon code" value={coupon} onChange={(e) => setCoupon(e.target.value)} aria-label="Coupon code" />
                <button className="btn ghost sm">Apply</button>
              </form>
              <Totals t={cart} />
              {cart.free_shipping_gap > 0 && <p className="hint-line">Add {inr(cart.free_shipping_gap)} more for free shipping.</p>}
            </>
          ))}

          {step === "address" && (
            <form id="address-form" onSubmit={submitAddress} className="address-form">
              {FIELDS.map(([key, label, ac]) => (
                <label key={key} className={key === "line1" ? "full" : ""}>{label}
                  <input className="input" required autoComplete={ac} value={address[key] || ""} onChange={(e) => setAddress({ ...address, [key]: e.target.value })} />
                </label>
              ))}
              <fieldset className="full">
                <legend>Delivery</legend>
                <label className="radio"><input type="radio" name="method" checked={method === "standard"} onChange={() => setMethod("standard")} /> Standard, 4-7 days</label>
                <label className="radio"><input type="radio" name="method" checked={method === "express"} onChange={() => setMethod("express")} /> Express, 1-2 days in metros · Rs. 149</label>
              </fieldset>
              <p className="hint-line full"><Icon name="shield" size={14} /> This form goes straight to checkout. It is never sent to the AI.</p>
            </form>
          )}

          {step === "preparing" && (
            <ol className="plan prep">
              {PREP_STEPS.map((label, i) => (
                <li key={label} className={i < prep ? "done" : i === prep ? "now" : ""}><span className="plan-dot">{i < prep && <Icon name="check" size={11} />}</span>{label}</li>
              ))}
            </ol>
          )}

          {step === "review" && order && (
            <>
              <div className="approval">
                <b><Icon name="shield" size={15} /> Waiting for your approval</b>
                <p>{order.notice}</p>
              </div>
              <ul className="cart-lines compact">
                {order.items.map((i) => <li key={i.id}><div><b>{i.quantity} × {i.product_name}</b></div><strong>{inr(i.line_total)}</strong></li>)}
              </ul>
              <Totals t={order.totals} />
              <p className="ship-to">Ship to {order.ship_to.full_name}, {order.ship_to.line1}, {order.ship_to.city} {order.ship_to.pincode} · {order.ship_to.phone}</p>
            </>
          )}

          {step === "done" && order && (
            <div className="approval ok"><b><Icon name="check" size={15} /> Order {order.order_id} confirmed</b><p>{order.message}</p></div>
          )}
        </div>

        <footer>
          {step === "cart" && cart.items.length > 0 && <button className="btn" onClick={() => setStep("address")}>Checkout · {inr(cart.total)}</button>}
          {step === "address" && <><button type="button" className="btn ghost" onClick={() => setStep("cart")}>Back</button><button className="btn" form="address-form">Prepare my order</button></>}
          {step === "review" && <><button className="btn ghost" onClick={cancel}>Cancel</button><button className="btn" onClick={confirm}>Confirm order · {inr(order.totals.total)}</button></>}
          {step === "done" && <button className="btn" onClick={onClose}>Done</button>}
        </footer>
      </aside>
    </>
  );
}
