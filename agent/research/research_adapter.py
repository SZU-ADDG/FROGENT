"""Chat-to-research adapter for the research controller."""

from agent.core.chat_adapter import ChatRequest
from agent.core.contracts import ExecutionContext, StreamEvent
from agent.research.research_types import ResearchRequest
from agent.research.research_workflow import ResearchController


def run_research_request(
    request: ChatRequest,
    context: ExecutionContext,
    workflow_request: ResearchRequest,
    controller: ResearchController,
) -> tuple[StreamEvent, ...]:
    if (request.user_id, request.conversation_id, request.job_id) != (
            context.user_id, context.conversation_id, context.job_id):
        raise ValueError("chat request and execution context identities differ")
    if request.message != workflow_request.plan.question:
        raise ValueError("chat message and research question differ")
    result = controller.run(workflow_request, context)
    events = [item for item in result.events if item.kind != "done"]
    events.append(StreamEvent("message.delta", {"text": result.answer, "channel": "answer"}, "research"))
    events.append(StreamEvent("done", {"admitted": len(result.working_memory_ids),
                                        "coverage_gaps": list(result.coverage_gaps)}))
    return tuple(events)
