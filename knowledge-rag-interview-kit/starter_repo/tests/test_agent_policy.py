from app.dto.agent import ApprovalDecision, ToolRequest, ToolRisk
from app.agent.policy import authorize, requires_approval


def test_read_only_tool_does_not_require_approval() -> None:
    request = ToolRequest(
        run_id="run-1",
        tool_name="search_knowledge",
        arguments={"query": "revenue policy"},
        risk=ToolRisk.READ_ONLY,
    )
    assert not requires_approval(request)
    assert authorize(request, None)


def test_write_tool_requires_named_approver() -> None:
    request = ToolRequest(
        run_id="run-2",
        tool_name="create_follow_up",
        arguments={"owner": "engagement-team"},
        risk=ToolRisk.INTERNAL_WRITE,
        idempotency_key="run-2:create-follow-up:1",
    )
    assert requires_approval(request)
    assert not authorize(request, None)
    assert authorize(
        request,
        ApprovalDecision(approved=True, approver_id="reviewer-1"),
    )
