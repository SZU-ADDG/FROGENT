"""Ordered retrieval execution telemetry shared by the research controller."""

from .harness import HarnessPhase, HarnessState
from .research_types import ResearchHit
from .retrieval import RetrievalCall, run_retrieval


def retrieve_queries(plan, queries, providers, context, state, policy, records, events,
                     completed, gaps, hits, counters):
    for item in queries:
        call = RetrievalCall(item.capability_id, item.source, item.query, item.limit)
        retrieval = run_retrieval(plan, (call,), providers, context, state, policy)
        records.extend(retrieval.ledger.records())
        emitted = tuple(event for event in retrieval.events if event.kind != "done")
        events.extend(emitted)
        counters["provider_calls"] += sum(event.kind == "tool.started" for event in emitted)
        for rank, hit in enumerate(retrieval.hits, 1):
            hits.append(ResearchHit(item.source, item.query, item.wave, rank,
                                    len(hits) + 1, hit.record_id))
        if retrieval.completed_calls:
            completed.append(query_key(item))
        else:
            gaps.append(f"retrieval failed: {item.source} {item.query}: {retrieval.state.error}")
        state = HarnessState(context.job_id, plan.as_of, HarnessPhase.RETRIEVAL,
                             retrieval.state.step_count, retrieval.state.tool_call_count)
    return state


def query_key(item) -> str:
    return "|".join((item.capability_id, item.source, item.query))
