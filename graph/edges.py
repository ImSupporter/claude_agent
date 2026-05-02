from langgraph.graph import END
from graph.state import VocState


def route_after_supervise(state: VocState) -> str:
    action = state["supervise_action"]
    if action == "answer":
        return "agent"
    if action == "retrieve":
        return "retrieve"
    return END


def route_after_retrieve(state: VocState) -> str:
    return "supervise"
