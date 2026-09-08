from app.dto.agent import ApprovalDecision, ToolRequest, ToolRisk


def requires_approval(request: ToolRequest) -> bool:
    return request.risk is not ToolRisk.READ_ONLY


def authorize(request: ToolRequest, decision: ApprovalDecision | None) -> bool:
    if not requires_approval(request):
        return True
    return bool(decision and decision.approved and decision.approver_id)
