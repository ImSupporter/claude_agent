from langgraph.graph import END
from graph.state import VocState
from graph.edges import route_after_supervise, route_after_retrieve


def _state(supervise_action: str = "", status: str = "processing") -> VocState:
    return {
        "raw_input": "", "conversation_history": [], "voc_type": "",
        "supervise_action": supervise_action,
        "retrieved_docs": [], "doc_retrieval_attempts": 0,
        "sql_results": [], "sql_tools_used": [],
        "response": "", "status": status, "error_message": None,
    }


def test_route_after_supervise_answer():
    assert route_after_supervise(_state(supervise_action="answer")) == "agent"


def test_route_after_supervise_retrieve():
    assert route_after_supervise(_state(supervise_action="retrieve")) == "retrieve"


def test_route_after_supervise_end():
    assert route_after_supervise(_state(supervise_action="end")) == END


def test_route_after_retrieve_always_returns_supervise():
    assert route_after_retrieve(_state(status="processing")) == "supervise"


def test_route_after_retrieve_error_still_returns_supervise():
    assert route_after_retrieve(_state(status="error")) == "supervise"
