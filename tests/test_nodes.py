import pytest
from unittest.mock import patch, MagicMock
from graph.state import VocState
from graph.nodes import classify_node

def _base_state(**kwargs) -> VocState:
    return {
        "raw_input": "결제가 안 돼요",
        "conversation_history": [],
        "voc_type": "",
        "retrieved_docs": [],
        "doc_retrieval_attempts": 0,
        "sql_results": [],
        "sql_tools_used": [],
        "response": "",
        "status": "processing",
        "error_message": None,
        **kwargs,
    }

def test_classify_node_complaint():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="COMPLAINT")
    with patch("graph.nodes.ChatAnthropic", return_value=mock_llm):
        result = classify_node(_base_state())
    assert result["voc_type"] == "COMPLAINT"

def test_classify_node_data_modification():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="DATA_MODIFICATION")
    with patch("graph.nodes.ChatAnthropic", return_value=mock_llm):
        result = classify_node(_base_state(raw_input="사용자 상태를 inactive로 바꿔주세요"))
    assert result["voc_type"] == "DATA_MODIFICATION"

def test_classify_node_strips_whitespace():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="  INQUIRY  \n")
    with patch("graph.nodes.ChatAnthropic", return_value=mock_llm):
        result = classify_node(_base_state())
    assert result["voc_type"] == "INQUIRY"

from graph.nodes import retrieve_node
from tools.doc_retriever import DocRetrievalError

def test_retrieve_node_success():
    docs = [{"title": "결제 가이드", "content": "결제 방법..."}]
    with patch("graph.nodes.query_documents", return_value=docs):
        result = retrieve_node(_base_state())
    assert result["retrieved_docs"] == docs
    assert result["status"] == "processing"
    assert result["doc_retrieval_attempts"] == 1

def test_retrieve_node_failure():
    with patch("graph.nodes.query_documents", side_effect=DocRetrievalError("실패")):
        result = retrieve_node(_base_state())
    assert result["status"] == "error"
    assert "답변이 어렵습니다" in result["error_message"]
    assert result["doc_retrieval_attempts"] == 1

from langchain_core.messages import AIMessage
from graph.nodes import agent_node

def test_agent_node_generates_response():
    state = _base_state(
        voc_type="INQUIRY",
        retrieved_docs=[{"title": "가이드", "content": "결제는 설정 메뉴에서..."}],
    )
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [
        MagicMock(content="NO"),
        AIMessage(content="결제 설정 메뉴에서 진행하세요.", tool_calls=[]),
    ]
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    with patch("graph.nodes.ChatAnthropic", return_value=mock_llm):
        result = agent_node(state)
    assert result["response"] == "결제 설정 메뉴에서 진행하세요."
    assert result["status"] == "done"

def test_agent_node_write_tools_only_for_data_modification():
    state = _base_state(
        voc_type="COMPLAINT",
        retrieved_docs=[{"title": "가이드", "content": "..."}],
    )
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [
        MagicMock(content="NO"),
        AIMessage(content="답변입니다.", tool_calls=[]),
    ]
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    with patch("graph.nodes.ChatAnthropic", return_value=mock_llm):
        agent_node(state)
    bound_tools = mock_llm.bind_tools.call_args[0][0]
    tool_names = [t.name for t in bound_tools]
    assert "update_user_status" not in tool_names
