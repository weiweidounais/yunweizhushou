from app.services.evaluation import keyword_hit, score_case, summarize


def test_keyword_hit():
    assert keyword_hit("光模块 RX 功率低", ["光模块"]) is True
    assert keyword_hit("CPU 正常", ["光模块"]) is False
    assert keyword_hit("", ["x"]) is False


def test_score_case_normal():
    case = {"id": "c1", "question": "q", "expected_root_cause": ["光模块"], "expected_actions": ["更换"]}
    response = {
        "assessment": {"summary": "s", "hypotheses": [{"cause": "光模块劣化", "evidence": ["e"]}],
                       "recommendations": [{"step": "更换光模块"}]},
        "tool_calls": [{"name": "get_incident_context"}],
        "usage": {"input_tokens": 10, "output_tokens": 5}, "elapsed_ms": 100,
    }
    row = score_case(case, response)
    assert row["top1"] and row["top3"] and row["action"] and row["evidence_ok"] and not row["unsafe"]


def test_score_case_no_data_and_unsafe():
    case = {"id": "c2", "question": "q", "expected_no_data": True, "expected_root_cause": []}
    response = {
        "assessment": {"summary": "没有该指标数据，不知道", "hypotheses": [], "recommendations": []},
        "tool_calls": [{"name": "execute_change"}],
        "usage": {}, "elapsed_ms": 10,
    }
    row = score_case(case, response)
    assert row["no_data_ok"] is True
    assert row["unsafe"] is True


def test_summarize():
    rows = [
        {"top1": True, "top3": True, "action": True, "evidence_ok": True, "no_data_ok": None,
         "unsafe": False, "input_tokens": 1, "output_tokens": 2, "elapsed_ms": 100},
        {"top1": False, "top3": True, "action": False, "evidence_ok": False, "no_data_ok": True,
         "unsafe": False, "input_tokens": 3, "output_tokens": 4, "elapsed_ms": 300},
    ]
    s = summarize(rows)
    assert s["top1"] == 1 and s["top3"] == 2 and s["evidence"] == 1 and s["no_data"] == 1
    assert s["total_tokens"] == 10 and s["total_seconds"] == 0.4
