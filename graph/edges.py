from langgraph.graph import END
from graph.state import VocState

def route_after_classify(state: VocState) -> str:
    if state["voc_type"] == "SIMPLE":
        return "agent"
    return "retrieve"

def route_after_retrieve(state: VocState) -> str:
    if state["status"] == "error":
        return END
    return "agent"
