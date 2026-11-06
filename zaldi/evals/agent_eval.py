"""End-to-end agent quality with a real model (needs a key and quota): ``python -m zaldi evals agent``.

Each case in ``evals/agent_cases.jsonl`` names the tools the agent should use, the tools it must not, and a kind. Per case we
record: tool choice correct, faithful (no amount in the reply that a tool did not return), refusal behaviour for attacks, plus
latency, tokens and estimated cost. The offline test suite exercises this same code with a scripted model, so a broken harness
is caught in CI even though the real numbers only exist when a model is reachable.
"""
import json
import time
from pathlib import Path

from zaldi.agent import verify
from zaldi.agent.loop import run_agent
from zaldi.ai import guardrails
from zaldi.ai.resilience import retry

CASES_FILE = Path(__file__).resolve().parents[2] / "evals" / "agent_cases.jsonl"


def load_cases(path: Path = CASES_FILE) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_case(case: dict, connector, llm, pause: float = 0.0) -> dict:
    """Run one case. An attack that the input guardrail refuses counts as handled without calling the model."""
    started = time.perf_counter()
    sid = f"eval-{case['id']}"
    try:
        safe, _ = guardrails.check_input(case["query"])
    except guardrails.Blocked:
        return {"id": case["id"], "kind": case["kind"], "tool_ok": True, "faithful": True, "blocked_by_guardrail": True,
                "tools": [], "latency_ms": 0, "cost_usd": 0.0, "tokens": 0, "error": None}
    try:
        result = retry(lambda: run_agent(safe, sid, connector, llm))
    except Exception as exc:  # a model outage is recorded as a failure of the case, not a crash of the run
        return {"id": case["id"], "kind": case["kind"], "tool_ok": False, "faithful": False, "blocked_by_guardrail": False,
                "tools": [], "latency_ms": round((time.perf_counter() - started) * 1000), "cost_usd": 0.0, "tokens": 0, "error": type(exc).__name__}
    used = [s["tool"] for s in result["steps"]]
    usage = result.get("usage", {})
    row = {"id": case["id"], "kind": case["kind"], "tools": used, "error": None, "blocked_by_guardrail": False,
           "tool_ok": all(t in used for t in case["expect_tools"]) and not any(t in used for t in case["forbid_tools"])
                      and (not case.get("expect_any") or any(t in used for t in case["expect_any"])),  # "at least one of": e.g. add it, or ask which size
           "faithful": result.get("checked") in ("ok", "ask", "repaired"), "self_check": result.get("checked"),
           "latency_ms": round((time.perf_counter() - started) * 1000), "cost_usd": usage.get("cost_usd", 0.0),
           "tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0)}
    time.sleep(pause)
    return row


def summarize(rows: list[dict]) -> dict:
    n = len(rows) or 1
    lat = sorted(r["latency_ms"] for r in rows if not r["blocked_by_guardrail"]) or [0]
    by_kind: dict[str, list[dict]] = {}
    for r in rows:
        by_kind.setdefault(r["kind"], []).append(r)
    return {"cases": len(rows), "tool_choice_accuracy": round(sum(r["tool_ok"] for r in rows) / n, 3),
            "faithfulness": round(sum(r["faithful"] for r in rows) / n, 3),
            "model_errors": sum(1 for r in rows if r["error"]),
            "latency_ms_p50": lat[len(lat) // 2], "latency_ms_p95": lat[min(len(lat) - 1, int(len(lat) * 0.95))],
            "cost_usd_total": round(sum(r["cost_usd"] for r in rows), 5), "cost_usd_per_chat": round(sum(r["cost_usd"] for r in rows) / n, 5),
            "tokens_per_chat": round(sum(r["tokens"] for r in rows) / n),
            "by_kind": {k: round(sum(r["tool_ok"] for r in v) / len(v), 2) for k, v in sorted(by_kind.items())}}


def run_all(connector, llm, pause: float = 1.0) -> dict:
    from zaldi.telemetry import model_name

    rows = [run_case(c, connector, llm, pause) for c in load_cases()]
    return {"summary": summarize(rows) | {"model": model_name(llm)}, "rows": rows}
