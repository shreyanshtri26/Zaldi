"""Order lookup and returns. The agent may *stage* a return; only the shopper's own confirmation message makes it final.

The confirmation is matched by ``chat_service`` with a fixed pattern, never by the model, and is bound to the session that staged it.
"""
import json
import re
import secrets

from zaldi.db import connect
from zaldi.errors import ValidationError

CONFIRM = re.compile(r"^\s*confirm return\s+([a-f0-9]{8})\s*$", re.I)
RETURNABLE = "confirmed"


def list_orders(session_id: str, limit: int = 5) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT id, status, summary, created_at FROM orders WHERE session_id=? AND status IN ('confirmed','pending') "
                            "ORDER BY created_at DESC LIMIT ?", (session_id, limit)).fetchall()
    out = []
    for r in rows:
        s = json.loads(r["summary"])
        out.append({"order_id": r["id"], "status": r["status"], "placed": r["created_at"], "total": s["totals"]["total"],
                    "items": [f"{i['quantity']} x {i['product_name']}" for i in s["items"]]})
    return out


def stage_return(session_id: str, order_id: str, reason: str) -> dict:
    reason = " ".join((reason or "").split())[:200]
    if len(reason) < 3:
        raise ValidationError("a short reason is needed")
    with connect() as conn:
        order = conn.execute("SELECT status FROM orders WHERE id=? AND session_id=?", (order_id, session_id)).fetchone()
        if order is None:
            raise ValidationError("that order was not found for this shopper")
        if order["status"] != RETURNABLE:
            raise ValidationError(f"only confirmed orders can be returned (this one is {order['status']})")
        if conn.execute("SELECT 1 FROM returns WHERE order_id=? AND status IN ('pending','confirmed')", (order_id,)).fetchone():
            raise ValidationError("a return for this order already exists")
        return_id = secrets.token_hex(4)
        conn.execute("INSERT INTO returns (id, session_id, order_id, reason) VALUES (?,?,?,?)", (return_id, session_id, order_id, reason))
    return {"return_id": return_id, "order_id": order_id, "reason": reason}


def confirm_return(session_id: str, return_id: str) -> dict:
    with connect() as conn:
        done = conn.execute("UPDATE returns SET status='confirmed' WHERE id=? AND session_id=? AND status='pending'",
                            (return_id, session_id)).rowcount
    if not done:
        raise ValidationError("that return request is not pending for this session")
    return {"return_id": return_id, "status": "confirmed"}
