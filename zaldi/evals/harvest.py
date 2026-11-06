"""Turn real failures into new test cases: ``python -m zaldi evals harvest``.

Picks chats that shoppers rated thumbs-down, or where the self-check had to repair or give up, redacts personal data, and
appends them to ``evals/harvested.jsonl`` (never twice). Review the file, fill in ``expect_tools`` for the ones worth keeping,
and move them into ``agent_cases.jsonl``: each real failure then becomes a permanent regression test.
"""
import json
from pathlib import Path

from zaldi.ai import guardrails
from zaldi.db import connect

OUT = Path(__file__).resolve().parents[2] / "evals" / "harvested.jsonl"


def harvest(limit: int = 50, out: Path = OUT) -> int:
    with connect(readonly=True) as conn:
        rows = conn.execute(
            "SELECT DISTINCT c.id, c.query, c.route, c.checked, f.rating FROM chat_logs c LEFT JOIN feedback f ON f.chat_id = c.id "
            "WHERE f.rating = -1 OR c.checked IN ('repaired', 'fallback') ORDER BY c.id DESC LIMIT ?", (limit,)).fetchall()
    have = {json.loads(line)["source_chat"] for line in out.read_text(encoding="utf-8").splitlines() if line.strip()} if out.exists() else set()
    new = []
    for r in rows:
        if r["id"] in have:
            continue
        query, _ = guardrails.redact_pii(r["query"])
        why = "thumbs down" if r["rating"] == -1 else f"self-check {r['checked']}"
        new.append({"id": f"harvested_{r['id']}", "source_chat": r["id"], "query": query, "expect_tools": [], "forbid_tools": [],
                    "kind": "harvested", "why": why})
    if new:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as f:
            f.writelines(json.dumps(c) + "\n" for c in new)
    return len(new)
