from app.services.agent import _clip
from tests.conftest import ASSESSMENT, make_client, submit, text_response, tool_use


def test_read_only_diagnosis_with_tools():
    client, llm = make_client([
        tool_use("get_incident_context", {"asset": "core-sw-01", "window_hours": 24}),
        submit(ASSESSMENT),
    ])
    sid = client.post("/api/sessions", json={}).json()["id"]
    r = client.post(f"/api/sessions/{sid}/chat", json={"message": "core-sw-01 昨晚开始丢包，什么原因？"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["assessment"]["summary"]
    assert data["assessment"]["hypotheses"][0]["evidence"]
    assert data["tool_calls"][0]["name"] == "get_incident_context"
    assert data["tool_calls"][0]["status"] == "ok"
    assert data["usage"]["input_tokens"] > 0
    assert len(llm.calls) == 2


def test_invalid_submit_is_rejected_then_accepted():
    bad = dict(ASSESSMENT)
    bad["hypotheses"] = [{"cause": "光模块", "confidence": "high", "evidence": [], "falsification": ""}]
    client, llm = make_client([submit(bad, "bad-1"), submit(ASSESSMENT, "good-1")])
    sid = client.post("/api/sessions", json={}).json()["id"]
    r = client.post(f"/api/sessions/{sid}/chat", json={"message": "查一下 core-sw-01"})
    assert r.status_code == 200
    assert r.json()["assessment"]["summary"]
    assert len(llm.calls) == 2


def test_unknown_tool_recovers():
    client, _ = make_client([
        tool_use("delete_everything", {}, "bad-tool"),
        submit(ASSESSMENT),
    ])
    sid = client.post("/api/sessions", json={}).json()["id"]
    r = client.post(f"/api/sessions/{sid}/chat", json={"message": "查 core-sw-01"})
    assert r.status_code == 200
    assert r.json()["tool_calls"][0]["status"] == "error"


def test_model_text_without_submit_warns():
    client, _ = make_client([text_response("我认为是光模块问题，但没有交卷工具。")])
    sid = client.post("/api/sessions", json={}).json()["id"]
    r = client.post(f"/api/sessions/{sid}/chat", json={"message": "查 core-sw-01"})
    assert r.status_code == 200
    assert r.json()["assessment"] is None
    assert r.json()["warnings"]


def test_max_turns_returns_warning():
    client, _ = make_client([tool_use("get_incident_context", {"asset": "core-sw-01"})], max_turns=1)
    sid = client.post("/api/sessions", json={}).json()["id"]
    r = client.post(f"/api/sessions/{sid}/chat", json={"message": "查 core-sw-01"})
    assert r.status_code == 200
    assert r.json()["assessment"] is None
    assert "最大轮数" in " ".join(r.json()["warnings"])


def test_clip_long_tool_result():
    clipped = _clip("x" * 30000)
    assert len(clipped) < 30000
    assert "已截断" in clipped


def test_fast_mode_prefetches_and_submits_once():
    client, llm = make_client([submit(ASSESSMENT)], fast_mode=True)
    sid = client.post("/api/sessions", json={}).json()["id"]
    r = client.post(f"/api/sessions/{sid}/chat", json={"message": "core-sw-01 昨晚开始丢包，什么原因？"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["assessment"]["summary"]
    assert data["tool_calls"][0]["name"] == "get_incident_context"
    assert len(llm.calls) == 1
    assert data["tool_calls"][0]["args"]["asset"] == "core-sw-01"


def test_progress_text_then_submit_is_nudged():
    client, llm = make_client([text_response("上下文已拿到，我再查一下。"), submit(ASSESSMENT)], fast_mode=False)
    sid = client.post("/api/sessions", json={}).json()["id"]
    r = client.post(f"/api/sessions/{sid}/chat", json={"message": "core-sw-01 丢包"})
    assert r.status_code == 200
    assert r.json()["assessment"]["summary"]
    assert len(llm.calls) == 2
