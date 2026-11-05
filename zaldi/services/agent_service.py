"""Run an agent against the real chat pipeline and record what it did; propose and decide policy changes."""
import time

from zaldi.db import agent_repo, content_repo
from zaldi.db.connection import connect
from zaldi.errors import ValidationError


def _steps(result: dict) -> list[dict]:
    """User-facing progress derived from what the pipeline actually returned (no internal reasoning)."""
    route = result.get("type", "unknown")
    steps = [{"label": "Checked the message for unsafe content", "status": "done"},
             {"label": f"Classified the request as: {route}", "status": "done"}]
    if route == "products":
        shown = {k: v for k, v in (result.get("filters") or {}).items() if v not in (None, [], "", False)}
        steps.append({"label": "Queried the product catalogue", "status": "done", "tool": "catalogue_search",
                      "detail": f"{len(result.get('products', []))} match(es)"})
        if shown:
            steps.append({"label": "Applied filters", "status": "done",
                          "detail": ", ".join(f"{k}={v}" for k, v in shown.items())})
        if result.get("relaxed"):
            steps.append({"label": "No exact match, relaxed: " + ", ".join(result["relaxed"]), "status": "done"})
    steps.append({"label": "Wrote the reply", "status": "done"})
    return steps


def test_agent(agent_id: int, message: str, session_id: str) -> dict:
    agent = agent_repo.get_agent(agent_id)
    if not agent:
        raise ValidationError("agent not found")
    if agent["status"] == "paused":
        raise ValidationError("agent is paused")
    from zaldi.services.chat_service import handle_query  # lazy: pulls in the LLM stack

    started = time.monotonic()
    result: dict = {}
    try:
        result = handle_query(message, session_id)
        status, steps, text, error = "success", _steps(result), result["response"], None
    except Exception as exc:
        status, steps, text, error = "failed", [{"label": "Run failed", "status": "failed"}], None, str(exc)
    run = agent_repo.add_run(agent_id, "test", message, status, steps, text, error,
                             int((time.monotonic() - started) * 1000))
    return run | {"products": result.get("products", [])}


def propose_policy_change(agent_id: int | None, policy_id: int, proposed: str, reason: str) -> dict:
    policy = content_repo.get_row("policies", policy_id)
    if not policy:
        raise ValidationError("policy not found")
    if not proposed.strip() or proposed.strip() == policy["content"].strip():
        raise ValidationError("proposed content must differ from the current policy")
    with connect() as conn:
        cur = conn.execute("INSERT INTO approvals (agent_id, policy_id, reason, current_content, proposed_content) "
                           "VALUES (?,?,?,?,?)", (agent_id, policy_id, reason.strip(), policy["content"], proposed.strip()))
        conn.commit()
    return next(a for a in agent_repo.list_approvals() if a["id"] == cur.lastrowid)


def decide(approval_id: int, approve: bool, edited: str | None = None) -> dict:
    """Approving writes the policy (the content repo then re-indexes it); rejecting changes nothing."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
        if not row:
            raise ValidationError("approval not found")
        if row["status"] != "pending":
            raise ValidationError(f"already {row['status']}")
        content = (edited or row["proposed_content"]).strip()
        conn.execute("UPDATE approvals SET status=?, proposed_content=?, decided_at=CURRENT_TIMESTAMP WHERE id=?",
                     ("approved" if approve else "rejected", content, approval_id))
        conn.commit()
    if approve:
        content_repo.update_row("policies", row["policy_id"], {"content": content})
    return next(a for a in agent_repo.list_approvals() if a["id"] == approval_id)
