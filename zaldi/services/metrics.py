"""Numbers for the admin metrics page: volume, speed, cost, how often the agent and its self-check fire, tool health, feedback."""
from datetime import datetime, timedelta, timezone

from zaldi.db import connect
from zaldi.errors import ValidationError


def _percentile(sorted_values: list[int], p: float) -> int:
    return sorted_values[min(len(sorted_values) - 1, int(len(sorted_values) * p))] if sorted_values else 0


def summary(days: int = 7) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(days=int(days))).strftime("%Y-%m-%d %H:%M:%S")  # same text format the tables store
    with connect(readonly=True) as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT id, route, latency_ms, input_tokens, output_tokens, cost_usd, model, variant, checked, substr(created_at, 1, 10) AS day "
            "FROM chat_logs WHERE created_at >= ?", (since,))]
        tools = [dict(r) for r in conn.execute(
            "SELECT tool, COUNT(*) AS calls, CAST(SUM(1 - ok) AS INTEGER) AS failures, CAST(AVG(ms) AS INTEGER) AS avg_ms FROM audit_log "
            "WHERE created_at >= ? GROUP BY tool ORDER BY calls DESC", (since,))]
        feedback = {r["variant"]: dict(r) for r in conn.execute(
            "SELECT COALESCE(c.variant, 'A') AS variant, CAST(SUM(CASE WHEN f.rating = 1 THEN 1 ELSE 0 END) AS INTEGER) AS up, CAST(SUM(CASE WHEN f.rating = -1 THEN 1 ELSE 0 END) AS INTEGER) AS down FROM feedback f "
            "JOIN chat_logs c ON c.id = f.chat_id WHERE f.created_at >= ? GROUP BY COALESCE(c.variant, 'A')", (since,))}
    latencies = sorted(r["latency_ms"] for r in rows if r["latency_ms"] is not None)
    agent = [r for r in rows if r["route"] == "agent"]
    per_day: dict[str, dict] = {}
    for r in rows:
        d = per_day.setdefault(r["day"], {"day": r["day"], "chats": 0, "cost_usd": 0.0})
        d["chats"] += 1
        d["cost_usd"] = round(d["cost_usd"] + (r["cost_usd"] or 0), 6)
    return {
        "days": days, "chats": len(rows), "agent_chats": len(agent),
        "latency_ms": {"p50": _percentile(latencies, 0.5), "p95": _percentile(latencies, 0.95)},
        "tokens": sum((r["input_tokens"] or 0) + (r["output_tokens"] or 0) for r in rows),
        "cost_usd": round(sum(r["cost_usd"] or 0 for r in rows), 5),
        "cost_usd_per_agent_chat": round(sum(r["cost_usd"] or 0 for r in agent) / len(agent), 5) if agent else 0.0,
        "self_check": {k: sum(1 for r in agent if r["checked"] == k) for k in ("ok", "repaired", "fallback", "ask")},
        "models": {m: sum(1 for r in rows if r["model"] == m) for m in sorted({r["model"] for r in rows if r["model"]})},
        "tools": tools, "feedback": feedback, "per_day": sorted(per_day.values(), key=lambda d: d["day"]),
    }


def record_feedback(chat_id: int, rating: int, comment: str = "") -> None:
    if rating not in (-1, 1):
        raise ValidationError("rating must be 1 or -1")
    with connect() as conn:
        if conn.execute("SELECT 1 FROM chat_logs WHERE id = ?", (chat_id,)).fetchone() is None:
            raise ValidationError("unknown chat")
        conn.execute("DELETE FROM feedback WHERE chat_id = ?", (chat_id,))  # one rating per answer: the latest wins
        conn.execute("INSERT INTO feedback (chat_id, rating, comment) VALUES (?, ?, ?)",
                     (chat_id, rating, " ".join((comment or "").split())[:300]))
