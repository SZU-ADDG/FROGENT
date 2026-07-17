"""Preserve admitted evidence and audit state when structured synthesis fails."""

from .contracts import StreamEvent


def synthesize_or_partial(synthesizer, question, evidence, reports, gaps, events) -> str:
    try:
        return synthesizer.synthesize(question, evidence, reports, tuple(sorted(set(gaps))))
    except Exception as exc:
        error_type = type(exc).__name__
        message = f"synthesis unavailable after bounded recovery: {error_type}: {exc}"
        gaps.append(message)
        events.append(StreamEvent("error", {"error_type": error_type, "message": str(exc),
                                             "stage": "synthesis", "recoverable": True},
                                  "synthesizer"))
        return _partial(evidence)


def _partial(evidence) -> str:
    lines = ["Evidence-bounded partial synthesis",
             "Status: source-study verdict unavailable; verified admitted evidence is preserved."]
    if not evidence:
        return "\n\n".join(lines + ["Admitted evidence: none."])
    claims = [f"- [{item.id}] {item.claim}" for item in evidence]
    return "\n\n".join(lines + ["Admitted evidence:\n" + "\n".join(claims)])
