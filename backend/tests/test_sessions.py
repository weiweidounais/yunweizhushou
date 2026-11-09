from tests.conftest import ASSESSMENT, make_client, submit, tool_use


def test_create_and_get_session():
    client, _ = make_client([])
    r = client.post("/api/sessions", json={"title": "测试会话"})
    assert r.status_code == 200
    sid = r.json()["id"]
    g = client.get(f"/api/sessions/{sid}")
    assert g.status_code == 200
    assert g.json()["title"] == "测试会话"


def test_missing_session_returns_error_envelope():
    client, _ = make_client([])
    r = client.get("/api/sessions/not-exists")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_empty_message_validation():
    client, _ = make_client([])
    sid = client.post("/api/sessions", json={}).json()["id"]
    r = client.post(f"/api/sessions/{sid}/chat", json={"message": ""})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_history_persisted():
    client, _ = make_client([tool_use("get_incident_context", {"asset": "core-sw-01"}), submit(ASSESSMENT)])
    sid = client.post("/api/sessions", json={}).json()["id"]
    r = client.post(f"/api/sessions/{sid}/chat", json={"message": "core-sw-01 丢包"})
    assert r.status_code == 200
    g = client.get(f"/api/sessions/{sid}").json()
    assert [m["role"] for m in g["messages"]] == ["user", "assistant"]
    assert g["messages"][1]["assessment"]["summary"]
