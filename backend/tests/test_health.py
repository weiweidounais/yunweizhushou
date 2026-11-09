from tests.conftest import make_client


def test_health_ok():
    client, _ = make_client([])
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["read_only"] is True
    assert body["model"] == "deepseek-chat"


def test_demo_cases_returns_three():
    client, _ = make_client([])
    r = client.get("/api/demo/cases")
    assert r.status_code == 200
    cases = r.json()["cases"]
    assert len(cases) == 3
    assert cases[0]["question"]
