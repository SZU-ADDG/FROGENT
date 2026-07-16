"""Minimal v4 compatibility boundary for the research controller."""

from .contracts import ExecutionContext, StreamEvent
from .research_types import ResearchRequest
from .research_workflow import ResearchController
from .v4_adapter import V4ChatRequest


def run_v4_research(request: V4ChatRequest, context: ExecutionContext,
                    workflow_request: ResearchRequest,
                    controller: ResearchController) -> tuple[StreamEvent, ...]:
    if (request.user_id, request.conversation_id, request.job_id) != (
            context.user_id, context.conversation_id, context.job_id):
        raise ValueError("v4 request and execution context identities differ")
    if request.message != workflow_request.plan.question:
        raise ValueError("v4 message and research question differ")
    result = controller.run(workflow_request, context)
    events = [item for item in result.events if item.kind != "done"]
    events.append(StreamEvent("message.delta", {"text": result.answer, "channel": "answer"}, "research"))
    events.append(StreamEvent("done", {"admitted": len(result.working_memory_ids),
                                        "coverage_gaps": list(result.coverage_gaps)}))
    return tuple(events)
