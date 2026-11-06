"""Agents, their runs and approvals. Per-agent settings are one JSON `config` blob."""
import json

from zaldi.db.connection import connect

CONFIG_KEYS = ("purpose", "role", "objective", "rules", "style", "languages", "capabilities", "tools", "knowledge",
               "permissions", "approval_actions")

DEFAULTS = [
    ("Shopping Assistant", "Finds products, recommends items, and answers product questions.", "shopping-bag",
     {"capabilities": ["product_search", "product_comparison", "inventory_lookup"],
      "tools": ["catalogue_search", "inventory_api"], "permissions": ["read_products"]}),
    ("Order Support Agent", "Handles delivery, cancellation, refund, and order-related queries.", "package",
     {"capabilities": ["policy_lookup", "order_lookup"], "tools": ["order_api"],
      "permissions": ["read_policies", "read_orders"]}),
    ("Knowledge Agent", "Retrieves accurate information from store policies and knowledge sources.", "book",
     {"capabilities": ["policy_lookup", "knowledge_retrieval"], "tools": ["search"], "permissions": ["read_policies"]}),
    ("Content Agent", "Creates and improves product descriptions, SEO content, and storefront content.", "pen",
     {"capabilities": ["content_generation"], "tools": ["cms_api"],
      "permissions": ["read_products", "read_policies", "edit_policies"], "approval_actions": ["edit_policies"]}),
    ("Inventory Agent", "Monitors stock levels and identifies low-stock products.", "boxes",
     {"capabilities": ["inventory_lookup"], "tools": ["inventory_api"], "permissions": ["read_products"]}),
]


def _agent(row, stats=None) -> dict:
    out = dict(row) | {"config": json.loads(row["config"])}
    out["executions"] = stats["n"] if stats else 0
    out["success_rate"] = round(100 * stats["ok"] / stats["n"]) if stats and stats["n"] else None
    out["last_activity"] = stats["last"] if stats else None
    return out


def _stats(conn) -> dict:
    rows = conn.execute("SELECT agent_id, COUNT(*) n, CAST(SUM(CASE WHEN status != 'failed' THEN 1 ELSE 0 END) AS INTEGER) ok, MAX(created_at) last "
                        "FROM agent_runs GROUP BY agent_id")
    return {r["agent_id"]: r for r in rows}


def list_agents() -> list[dict]:
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM agents LIMIT 1").fetchone():
            for name, desc, icon, cfg in DEFAULTS:
                conn.execute("INSERT INTO agents (name, description, icon, status, config) VALUES (?,?,?,?,?)",
                             (name, desc, icon, "active", json.dumps(cfg)))
            conn.commit()
        stats = _stats(conn)
        return [_agent(r, stats.get(r["id"])) for r in conn.execute("SELECT * FROM agents ORDER BY id")]


def get_agent(agent_id: int) -> dict | None:
    return next((a for a in list_agents() if a["id"] == agent_id), None)


def save_agent(data: dict, agent_id: int | None = None) -> dict:
    cfg = {k: data["config"][k] for k in CONFIG_KEYS if k in data.get("config", {})}
    with connect() as conn:
        if agent_id is None:
            cur = conn.execute(
                "INSERT INTO agents (name, description, icon, model, status, config) VALUES (?,?,?,?,?,?)",
                (data["name"], data.get("description", ""), data.get("icon", "bot"), data.get("model", "gemini"),
                 data.get("status", "draft"), json.dumps(cfg)))
            agent_id = cur.lastrowid
        else:
            old = json.loads(conn.execute("SELECT config FROM agents WHERE id=?", (agent_id,)).fetchone()["config"])
            conn.execute("UPDATE agents SET name=COALESCE(?,name), description=COALESCE(?,description), "
                         "icon=COALESCE(?,icon), model=COALESCE(?,model), status=COALESCE(?,status), config=?, "
                         "updated_at=CURRENT_TIMESTAMP WHERE id=?",
                         (data.get("name"), data.get("description"), data.get("icon"), data.get("model"),
                          data.get("status"), json.dumps(old | cfg), agent_id))
        conn.commit()
    return get_agent(agent_id)


def delete_agent(agent_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM agents WHERE id=?", (agent_id,))
        conn.commit()


def _run(r) -> dict:
    return dict(r) | {"steps": json.loads(r["steps"])}


def add_run(agent_id: int, trigger: str, text: str, status: str, steps: list, result: str | None, error: str | None,
            duration_ms: int) -> dict:
    with connect() as conn:
        cur = conn.execute("INSERT INTO agent_runs (agent_id, trigger_, input, status, steps, result, error, duration_ms) "
                           "VALUES (?,?,?,?,?,?,?,?)",
                           (agent_id, trigger, text, status, json.dumps(steps), result, error, duration_ms))
        conn.commit()
        return _run(conn.execute("SELECT * FROM agent_runs WHERE id=?", (cur.lastrowid,)).fetchone())


def list_runs(agent_id: int | None = None, limit: int = 50) -> list[dict]:
    with connect() as conn:
        sql = "SELECT r.*, a.name agent_name FROM agent_runs r JOIN agents a ON a.id = r.agent_id"
        args: tuple = ()
        if agent_id:
            sql, args = sql + " WHERE r.agent_id=?", (agent_id,)
        return [_run(r) for r in conn.execute(sql + " ORDER BY r.id DESC LIMIT ?", (*args, limit))]


def list_approvals(status: str = "") -> list[dict]:
    with connect() as conn:
        sql = ("SELECT p.*, pol.title policy_title, a.name agent_name FROM approvals p "
               "JOIN policies pol ON pol.id = p.policy_id LEFT JOIN agents a ON a.id = p.agent_id")
        args: tuple = ()
        if status:
            sql, args = sql + " WHERE p.status=?", (status,)
        return [dict(r) for r in conn.execute(sql + " ORDER BY p.id DESC", args)]
