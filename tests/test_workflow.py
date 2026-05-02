import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage
from pydantic import BaseModel
from typing import Literal
from graph.workflow import build_graph


class SuperviseDecision(BaseModel):
    action: Literal["answer", "retrieve", "ask"]
    question: str | None = None


def _initial_state(raw_input: str) -> dict:
    return {
        "raw_input": raw_input,
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


def test_workflow_simple_path():
    """SIMPLE 유형: retrieve 없이 classify → supervise → agent"""
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = SuperviseDecision(action="answer")
    mock_llm.with_structured_output.return_value = mock_structured
    mock_llm.invoke.side_effect = [
        MagicMock(content="SIMPLE"),
        AIMessage(content="안녕하세요!", tool_calls=[]),
    ]
    mock_llm.bind_tools.return_value = mock_llm

    with patch("graph.nodes.ChatAnthropic", return_value=mock_llm):
        graph = build_graph()
        result = graph.invoke(
            _initial_state("안녕"),
            {"configurable": {"thread_id": "test-simple"}},
        )
    assert result["status"] == "done"
    assert result["voc_type"] == "SIMPLE"
    assert result["response"] == "안녕하세요!"


def test_workflow_inquiry_with_retrieve():
    """INQUIRY 유형: classify → supervise(retrieve) → retrieve → supervise(answer) → agent"""
    docs = [{"title": "결제 가이드", "content": "결제는 설정에서..."}]
    mock_llm = MagicMock()
    mock_structured_1 = MagicMock()
    mock_structured_1.invoke.return_value = SuperviseDecision(action="retrieve")
    mock_structured_2 = MagicMock()
    mock_structured_2.invoke.return_value = SuperviseDecision(action="answer")
    # side_effect의 순서가 중요: supervise_node는 총 2회 호출되며, 매 호출마다
    # ChatAnthropic()이 동일한 mock_llm 인스턴스를 반환하고 with_structured_output도
    # 동일 인스턴스에서 순서대로 호출된다.
    # 1번째 호출: supervise(retrieve 결정) → mock_structured_1 반환
    # 2번째 호출: retrieve 후 재진입한 supervise(answer 결정) → mock_structured_2 반환
    mock_llm.with_structured_output.side_effect = [mock_structured_1, mock_structured_2]
    mock_llm.invoke.side_effect = [
        MagicMock(content="INQUIRY"),
        AIMessage(content="안내 드립니다.", tool_calls=[]),
    ]
    mock_llm.bind_tools.return_value = mock_llm

    with patch("graph.nodes.query_documents", return_value=docs), \
         patch("graph.nodes.ChatAnthropic", return_value=mock_llm):
        graph = build_graph()
        result = graph.invoke(
            _initial_state("결제 방법을 알려주세요"),
            {"configurable": {"thread_id": "test-inquiry"}},
        )
    assert result["status"] == "done"
    assert result["voc_type"] == "INQUIRY"
    assert result["response"] == "안내 드립니다."


def test_workflow_error_path():
    """retrieve 실패: supervise가 end 반환 → 워크플로우 종료"""
    from tools.doc_retriever import DocRetrievalError

    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = SuperviseDecision(action="retrieve")
    mock_llm.with_structured_output.return_value = mock_structured
    mock_llm.invoke.return_value = MagicMock(content="COMPLAINT")

    with patch("graph.nodes.query_documents", side_effect=DocRetrievalError("연결 실패")), \
         patch("graph.nodes.ChatAnthropic", return_value=mock_llm):
        graph = build_graph()
        result = graph.invoke(
            _initial_state("오류가 발생했어요"),
            {"configurable": {"thread_id": "test-error"}},
        )
    assert result["status"] == "error"
    assert result["error_message"] is not None
