"""Chat history and dashboard statistics."""
from zaldi.db.connection import connect


def log_chat(query: str, response: str, route: str) -> None:
    with connect() as conn:
        conn.execute("INSERT INTO chat_logs (query, response, route) VALUES (?, ?, ?)", (query, response, route))


def recent_logs(limit: int = 50) -> list[dict]:
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM chat_logs ORDER BY id DESC LIMIT ?", (limit,))]


def stats(low_stock_threshold: int = 10) -> dict:
    with connect() as conn:
        def count(sql: str, *args) -> int:
            return conn.execute(sql, args).fetchone()[0]

        return {
            "products": count("SELECT COUNT(*) FROM products"),
            "policies": count("SELECT COUNT(*) FROM policies"),
            "chats": count("SELECT COUNT(*) FROM chat_logs"),
            "low_stock": count("SELECT COUNT(*) FROM products WHERE stock_quantity < ?", low_stock_threshold),
        }
