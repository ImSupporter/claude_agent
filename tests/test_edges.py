from graph.state import VocState
from graph.edges import route_after_retrieve


def _state(status: str) -> VocState:
    return {
        "raw_input": "",
        "conversation_history": [],
        "voc_type": "",
        "retrieved_docs": [],
        "doc_retrieval_attempts": 0,
        "sql_results": [],
        "sql_tools_used": [],
        "response": "",
        "status": status,
        "error_message": None,
    }


def test_route_to_agent_when_processing():
    assert route_after_retrieve(_state("processing")) == "agent"


def test_route_to_end_when_error():
    assert route_after_retrieve(_state("error")) == "__end__"
