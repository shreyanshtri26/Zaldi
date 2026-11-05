"""Session cart and pricing. Prices are INR and GST-inclusive (see the GST policy), so totals add no tax line."""
import json

from zaldi.db import connect
from zaldi.errors import ValidationError

FREE_SHIPPING_MIN = 999  # policy: free shipping above Rs. 999 (measured before discounts)
SHIPPING_FEE = 79
COUPONS = {"WELCOME10": 10}  # code -> percent off (policy: first-time users). Single use per cart, no stacking.
MAX_PER_LINE = 10


def _stock(conn, product_id: int) -> tuple[dict, int]:
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if row is None:
        raise ValidationError("that product does not exist")
    return dict(row), row["stock_quantity"]


def add_item(session_id: str, product_id: int, quantity: int = 1) -> dict:
    """Add ``quantity`` of a product (merging with an existing line). Never exceeds stock."""
    if quantity < 1:
        raise ValidationError("quantity must be at least 1")
    with connect() as conn:
        product, stock = _stock(conn, product_id)
        have = conn.execute("SELECT quantity FROM cart_items WHERE session_id=? AND product_id=?",
                            (session_id, product_id)).fetchone()
        wanted = (have["quantity"] if have else 0) + quantity
        if stock == 0:
            raise ValidationError(f"{product['product_name']} is out of stock")
        if wanted > min(stock, MAX_PER_LINE):
            raise ValidationError(f"only {min(stock, MAX_PER_LINE)} of {product['product_name']} can be ordered at once")
        conn.execute("INSERT INTO cart_items (session_id, product_id, quantity) VALUES (?,?,?) "
                     "ON CONFLICT(session_id, product_id) DO UPDATE SET quantity = excluded.quantity",
                     (session_id, product_id, wanted))
    return get_cart(session_id)


def set_quantity(session_id: str, product_id: int, quantity: int) -> dict:
    """Set a line's quantity; 0 removes it."""
    if quantity < 0:
        raise ValidationError("quantity cannot be negative")
    if quantity == 0:
        return remove_item(session_id, product_id)
    with connect() as conn:
        product, stock = _stock(conn, product_id)
        if quantity > min(stock, MAX_PER_LINE):
            raise ValidationError(f"only {min(stock, MAX_PER_LINE)} of {product['product_name']} can be ordered at once")
        updated = conn.execute("UPDATE cart_items SET quantity=? WHERE session_id=? AND product_id=?",
                               (quantity, session_id, product_id)).rowcount
    if not updated:
        raise ValidationError("that product is not in your cart")
    return get_cart(session_id)


def remove_item(session_id: str, product_id: int) -> dict:
    with connect() as conn:
        conn.execute("DELETE FROM cart_items WHERE session_id=? AND product_id=?", (session_id, product_id))
    return get_cart(session_id)


def clear_cart(session_id: str) -> dict:
    with connect() as conn:
        conn.execute("DELETE FROM cart_items WHERE session_id=?", (session_id,))
        conn.execute("UPDATE session_state SET coupon=NULL WHERE session_id=?", (session_id,))
    return get_cart(session_id)


def apply_coupon(session_id: str, code: str) -> dict:
    code = code.strip().upper()
    if code not in COUPONS:
        raise ValidationError(f"{code or 'that'} is not a valid coupon code")
    with connect() as conn:
        conn.execute("INSERT INTO session_state (session_id, coupon) VALUES (?,?) "
                     "ON CONFLICT(session_id) DO UPDATE SET coupon=excluded.coupon", (session_id, code))
    return get_cart(session_id)


def get_cart(session_id: str) -> dict:
    """Current lines (with live price/stock) and the price breakdown."""
    with connect() as conn:
        lines = [dict(r) for r in conn.execute(
            "SELECT p.id, p.product_code, p.product_name, p.brand, p.color, p.size, p.price, p.image_url, "
            "p.stock_quantity, c.quantity FROM cart_items c JOIN products p ON p.id = c.product_id "
            "WHERE c.session_id = ? ORDER BY p.id", (session_id,))]
        state = conn.execute("SELECT coupon FROM session_state WHERE session_id=?", (session_id,)).fetchone()
    warnings = []
    for line in lines:
        line["line_total"] = line["price"] * line["quantity"]
        if line["quantity"] > line["stock_quantity"]:
            warnings.append(f"{line['product_name']}: only {line['stock_quantity']} left in stock")
    coupon = state["coupon"] if state and state["coupon"] in COUPONS else None
    subtotal = sum(line["line_total"] for line in lines)
    discount = round(subtotal * COUPONS[coupon] / 100) if coupon else 0
    shipping = 0 if not lines or subtotal >= FREE_SHIPPING_MIN else SHIPPING_FEE
    return {"items": lines, "item_count": sum(line["quantity"] for line in lines), "subtotal": subtotal,
            "coupon": coupon, "discount": discount, "shipping": shipping, "total": subtotal - discount + shipping,
            "warnings": warnings, "free_shipping_gap": max(0, FREE_SHIPPING_MIN - subtotal) if lines else 0}


# ---- what the customer was last shown, so "add the first one" has a referent ----
def remember_results(session_id: str, product_ids: list[int]) -> None:
    with connect() as conn:
        conn.execute("INSERT INTO session_state (session_id, last_results) VALUES (?,?) "
                     "ON CONFLICT(session_id) DO UPDATE SET last_results=excluded.last_results, updated_at=CURRENT_TIMESTAMP",
                     (session_id, json.dumps(product_ids)))


def last_results(session_id: str) -> list[int]:
    with connect() as conn:
        row = conn.execute("SELECT last_results FROM session_state WHERE session_id=?", (session_id,)).fetchone()
    return json.loads(row["last_results"]) if row else []
