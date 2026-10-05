import pytest

from app.evaluation.agent_metrics import check_run, is_subsequence, pass_at_k, pass_hat_k, summarize


def test_pass_at_k_and_pass_hat_k_hand_worked():
    # 5 trials, 4 passed.
    assert pass_at_k(5, 4, 1) == pytest.approx(0.8)
    assert pass_at_k(5, 4, 2) == 1.0          # Only one failure: any 2 tries include a pass.
    assert pass_hat_k(5, 4, 1) == pytest.approx(0.8)
    assert pass_hat_k(5, 4, 2) == pytest.approx(0.6)   # C(4,2)/C(5,2) = 6/10
    assert pass_hat_k(5, 4, 5) == 0.0
    assert pass_hat_k(3, 3, 3) == 1.0


def test_invalid_counts_raise():
    with pytest.raises(ValueError):
        pass_at_k(3, 4, 1)


def test_tool_order_is_a_subsequence():
    assert is_subsequence(["search_knowledge", "calculate"], ["search_knowledge", "search_knowledge", "calculate"])
    assert not is_subsequence(["search_knowledge", "calculate"], ["calculate", "search_knowledge"])


def test_check_run_reports_every_failed_expectation():
    run = {"status": "completed", "answer": "About 200",
           "steps": [{"tool": "calculate", "status": "completed"}, {"tool": "create_follow_up", "status": "awaiting_approval"}]}
    failures = check_run(run, {"status": "completed", "answer_contains": ["180"],
                               "tools_in_order": ["search_knowledge"], "tools_not_proposed": ["create_follow_up"],
                               "max_writes": 0}, writes=1)
    assert len(failures) == 4


def test_summary_separates_quality_from_safety():
    rows = [{"task": "t", "category": "c", "passed": True, "turns": 2, "latency_s": 1.0},
            {"task": "t", "category": "c", "passed": False, "turns": 4, "latency_s": 3.0, "unapproved_writes": 1}]
    summary = summarize(rows, k=2)
    assert summary["tasks"]["t"]["pass@1"] == 0.5 and summary["tasks"]["t"]["pass^2"] == 0.0
    assert summary["unapproved_writes"] == 1
