"""Agent Studio API (admin only): agents, test runs, execution history and policy-change approvals."""
import sqlite3

from flask import Blueprint, jsonify, request

from zaldi.api.auth import admin_required
from zaldi.api.shop import session_id
from zaldi.db import agent_repo
from zaldi.errors import ValidationError
from zaldi.services import agent_service

bp = Blueprint("agents", __name__, url_prefix="/admin")
STATUSES = {"active", "paused", "draft"}


def _body() -> dict:
    return request.get_json(silent=True) or {}


def _valid(data: dict, creating: bool) -> dict:
    if creating and not str(data.get("name", "")).strip():
        raise ValidationError("name is required")
    if "name" in data:
        data["name"] = str(data["name"]).strip()[:60]
    if data.get("status") not in (None, *STATUSES):
        raise ValidationError("status must be active, paused or draft")
    if not isinstance(data.get("config", {}), dict):
        raise ValidationError("config must be an object")
    return data


def _agent_or_404(agent_id: int) -> dict:
    agent = agent_repo.get_agent(agent_id)
    if not agent:
        raise ValidationError("agent not found")
    return agent


def _save(data: dict, agent_id: int | None = None) -> dict:
    try:
        return agent_repo.save_agent(data, agent_id)
    except sqlite3.IntegrityError as exc:
        raise ValidationError("an agent with that name already exists") from exc


@bp.get("/agents")
@admin_required
def list_agents():
    return jsonify(agents=agent_repo.list_agents())


@bp.post("/agents")
@admin_required
def create_agent():
    return jsonify(_save(_valid(_body(), True))), 201


@bp.get("/agents/<int:agent_id>")
@admin_required
def get_agent(agent_id):
    return jsonify(_agent_or_404(agent_id))


@bp.patch("/agents/<int:agent_id>")
@admin_required
def patch_agent(agent_id):
    _agent_or_404(agent_id)
    return jsonify(_save(_valid(_body(), False), agent_id))


@bp.delete("/agents/<int:agent_id>")
@admin_required
def delete_agent(agent_id):
    _agent_or_404(agent_id)
    agent_repo.delete_agent(agent_id)
    return "", 204


@bp.post("/agents/<int:agent_id>/duplicate")
@admin_required
def duplicate_agent(agent_id):
    src = _agent_or_404(agent_id)
    names = {a["name"] for a in agent_repo.list_agents()}
    name, n = f"{src['name']} (copy)", 2
    while name in names:
        name, n = f"{src['name']} (copy {n})", n + 1
    return jsonify(_save(src | {"name": name, "status": "draft"})), 201


@bp.post("/agents/<int:agent_id>/test")
@admin_required
def test_agent(agent_id):
    message = str(_body().get("message", "")).strip()
    if not message:
        raise ValidationError("message is required")
    return jsonify(agent_service.test_agent(agent_id, message, session_id()))


@bp.get("/runs")
@admin_required
def list_runs():
    return jsonify(runs=agent_repo.list_runs(request.args.get("agent_id", type=int)))


@bp.get("/approvals")
@admin_required
def list_approvals():
    return jsonify(approvals=agent_repo.list_approvals(request.args.get("status", "")))


@bp.post("/approvals")
@admin_required
def propose():
    d = _body()
    return jsonify(agent_service.propose_policy_change(
        d.get("agent_id"), int(d.get("policy_id", 0)), str(d.get("proposed_content", "")), str(d.get("reason", "")))), 201


@bp.post("/approvals/<int:approval_id>/<action>")
@admin_required
def decide(approval_id, action):
    if action not in ("approve", "reject"):
        raise ValidationError("action must be approve or reject")
    return jsonify(agent_service.decide(approval_id, action == "approve", _body().get("content")))
