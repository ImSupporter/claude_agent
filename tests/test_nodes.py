import pytest
from unittest.mock import patch, MagicMock
from pydantic import BaseModel
from typing import Literal
from graph.state import VocState
from graph.nodes import classify_node

def _base_state(**kwargs) -> VocState:
    return {
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
        conversation_history=[],
    )
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="결제 설정 메뉴에서 진행하세요.", tool_calls=[])
    mock_llm.bind_tools.return_value = mock_llm
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
    mock_llm.invoke.return_value = AIMessage(content="답변입니다.", tool_calls=[])
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    with patch("graph.nodes.ChatAnthropic", return_value=mock_llm):
        agent_node(state)
    bound_tools = mock_llm.bind_tools.call_args[0][0]
    tool_names = [t.name for t in bound_tools]
    assert "update_user_status" not in tool_names


def test_supervise_node_returns_answer_for_simple():
    """SIMPLE 유형: LLM이 answer 반환"""
    from graph.nodes import supervise_node, SuperviseDecision
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = SuperviseDecision(action="answer")
    mock_llm.with_structured_output.return_value = mock_structured
    with patch("graph.nodes.ChatAnthropic", return_value=mock_llm):
        result = supervise_node(_base_state(voc_type="SIMPLE"))
    assert result["supervise_action"] == "answer"

def test_supervise_node_returns_retrieve_when_no_docs():
    """문서 없는 COMPLAINT: LLM이 retrieve 반환"""
    from graph.nodes import supervise_node, SuperviseDecision
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = SuperviseDecision(action="retrieve")
    mock_llm.with_structured_output.return_value = mock_structured
    with patch("graph.nodes.ChatAnthropic", return_value=mock_llm):
        result = supervise_node(_base_state(voc_type="COMPLAINT"))
    assert result["supervise_action"] == "retrieve"

def test_supervise_node_returns_end_on_error():
    """status==error: LLM 호출 없이 즉시 end 반환"""
    from graph.nodes import supervise_node
    with patch("graph.nodes.ChatAnthropic") as mock_cls:
        result = supervise_node(_base_state(status="error"))
    mock_cls.assert_not_called()
    assert result["supervise_action"] == "end"

def test_supervise_node_interrupt_on_ask():
    """ask 후 interrupt → 재판단 → answer"""
    from graph.nodes import supervise_node, SuperviseDecision
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.side_effect = [
        SuperviseDecision(action="ask", question="사용자 ID가 무엇인가요?"),
        SuperviseDecision(action="answer"),
    ]
    mock_llm.with_structured_output.return_value = mock_structured
    with patch("graph.nodes.ChatAnthropic", return_value=mock_llm), \
         patch("graph.nodes.interrupt", return_value="user123"):
        result = supervise_node(_base_state(
            voc_type="COMPLAINT",
            retrieved_docs=[{"title": "가이드", "content": "내용"}],
        ))
    assert result["supervise_action"] == "answer"
    history = result["conversation_history"]
    assert history[0] == {"role": "assistant", "content": "사용자 ID가 무엇인가요?"}
    assert history[1] == {"role": "user", "content": "user123"}
