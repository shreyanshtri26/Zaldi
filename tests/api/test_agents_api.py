from tests.helpers import ADMIN_HEADERS

SID = {"X-Session-Id": "11111111-1111-4111-8111-111111111111"}


def _agents(client):
    return client.get("/api/admin/agents", headers=ADMIN_HEADERS).get_json()["agents"]


def test_requires_admin_token(client):
    assert client.get("/api/admin/agents").status_code == 401
    assert client.get("/api/admin/approvals").status_code == 401


def test_default_agents_are_seeded(client):
    names = [a["name"] for a in _agents(client)]
    assert names == ["Shopping Assistant", "Order Support Agent", "Knowledge Agent", "Content Agent", "Inventory Agent"]


def test_create_validates_and_rejects_duplicates(client):
    assert client.post("/api/admin/agents", json={}, headers=ADMIN_HEADERS).status_code == 400
    ok = client.post("/api/admin/agents", json={"name": "Bridal", "config": {"tools": ["search"]}}, headers=ADMIN_HEADERS)
    assert ok.status_code == 201 and ok.get_json()["status"] == "draft"
    assert client.post("/api/admin/agents", json={"name": "Bridal"}, headers=ADMIN_HEADERS).status_code == 400
    bad = client.patch(f"/api/admin/agents/{ok.get_json()['id']}", json={"status": "weird"}, headers=ADMIN_HEADERS)
    assert bad.status_code == 400


def test_pause_duplicate_and_delete(client):
    first = _agents(client)[0]
    paused = client.patch(f"/api/admin/agents/{first['id']}", json={"status": "paused"}, headers=ADMIN_HEADERS)
    assert paused.get_json()["status"] == "paused"
    assert client.post(f"/api/admin/agents/{first['id']}/test", json={"message": "hi"},
                       headers=ADMIN_HEADERS | SID).status_code == 400  # paused agents do not run
    copy = client.post(f"/api/admin/agents/{first['id']}/duplicate", headers=ADMIN_HEADERS).get_json()
    assert copy["name"].endswith("(copy)") and copy["status"] == "draft"
    assert client.delete(f"/api/admin/agents/{copy['id']}", headers=ADMIN_HEADERS).status_code == 204
    assert len(_agents(client)) == 5


def test_test_run_uses_real_pipeline_and_is_recorded(client):
    agent = _agents(client)[0]
    run = client.post(f"/api/admin/agents/{agent['id']}/test", json={"message": "red sarees under 5000"},
                      headers=ADMIN_HEADERS | SID).get_json()
    assert run["status"] == "success" and run["products"]
    assert any(s.get("tool") == "catalogue_search" for s in run["steps"])
    runs = client.get(f"/api/admin/runs?agent_id={agent['id']}", headers=ADMIN_HEADERS).get_json()["runs"]
    assert len(runs) == 1 and runs[0]["input"] == "red sarees under 5000"
    assert _agents(client)[0]["executions"] == 1


def test_approval_changes_policy_only_when_approved(client):
    policy = client.get("/api/policies").get_json()[0]
    new = "Returns accepted within 10 days."
    ap = client.post("/api/admin/approvals", json={"policy_id": policy["id"], "proposed_content": new, "reason": "test"},
                     headers=ADMIN_HEADERS).get_json()
    assert client.get("/api/policies").get_json()[0]["content"] == policy["content"]  # untouched while pending
    assert client.post("/api/admin/approvals", json={"policy_id": policy["id"], "proposed_content": policy["content"]},
                       headers=ADMIN_HEADERS).status_code == 400
    done = client.post(f"/api/admin/approvals/{ap['id']}/approve", headers=ADMIN_HEADERS).get_json()
    assert done["status"] == "approved"
    assert client.get("/api/policies").get_json()[0]["content"] == new
    assert client.post(f"/api/admin/approvals/{ap['id']}/reject", headers=ADMIN_HEADERS).status_code == 400  # decided once


def test_rejected_approval_leaves_policy_alone(client):
    policy = client.get("/api/policies").get_json()[0]
    ap = client.post("/api/admin/approvals", json={"policy_id": policy["id"], "proposed_content": "x changed"},
                     headers=ADMIN_HEADERS).get_json()
    client.post(f"/api/admin/approvals/{ap['id']}/reject", headers=ADMIN_HEADERS)
    assert client.get("/api/policies").get_json()[0]["content"] == policy["content"]
