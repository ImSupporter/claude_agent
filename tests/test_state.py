from graph.state import VocState


def test_voc_state_required_keys():
    state: VocState = {
        "raw_input": "결제가 안 돼요",
        "conversation_history": [],
        "voc_type": "",
        "supervise_action": "",
        "retrieved_docs": [],
        "doc_retrieval_attempts": 0,
        "sql_results": [],
        "sql_tools_used": [],
        "response": "",
        "status": "processing",
        "error_message": None,
    }
    assert state["raw_input"] == "결제가 안 돼요"
    assert state["status"] == "processing"
    assert state["error_message"] is None


def test_voc_state_supervise_action_field():
    state: VocState = {
        "raw_input": "결제가 안 돼요",
        "conversation_history": [],
        "voc_type": "",
        "supervise_action": "",
        "retrieved_docs": [],
        "doc_retrieval_attempts": 0,
        "sql_results": [],
        "sql_tools_used": [],
        "response": "",
        "status": "processing",
        "error_message": None,
    }
    assert state["supervise_action"] == ""
