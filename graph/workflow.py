from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from graph.state import VocState
from graph.nodes import classify_node, supervise_node, retrieve_node, agent_node
from graph.edges import route_after_supervise, route_after_retrieve


def build_graph() -> StateGraph:
    builder = StateGraph(VocState)

    builder.add_node("classify", classify_node)
    builder.add_node("supervise", supervise_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("agent", agent_node)

    builder.set_entry_point("classify")
    builder.add_edge("classify", "supervise")
    builder.add_conditional_edges("supervise", route_after_supervise, {
        "agent": "agent",
        "retrieve": "retrieve",
        END: END,
    })
    builder.add_edge("retrieve", "supervise")
    builder.add_edge("agent", END)

    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)
