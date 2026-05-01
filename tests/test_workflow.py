import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage
from graph.workflow import build_graph

def test_workflow_happy_path():
    docs = [{"title": "결제 가이드", "content": "결제는 설정에서..."}]
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = [
        MagicMock(content="INQUIRY"),
        MagicMock(content="NO"),
        AIMessage(content="안내 드립니다.", tool_calls=[]),
    ]
    mock_llm.bind_tools.return_value = mock_llm

    with patch("graph.nodes.query_documents", return_value=docs), \
         patch("graph.nodes.ChatAnthropic", return_value=mock_llm):
        graph = build_graph()
        config = {"configurable": {"thread_id": "test-1"}}
        result = graph.invoke(
            {
                "raw_input": "결제 방법을 알려주세요",
                "conversation_history": [],
                "voc_type": "",
                "retrieved_docs": [],
                "doc_retrieval_attempts": 0,
                "sql_results": [],
                "sql_tools_used": [],
                "response": "",
                "status": "processing",
                "error_message": None,
            },
            config,
        )
    assert result["status"] == "done"
    assert result["voc_type"] == "INQUIRY"
    assert result["response"] == "안내 드립니다."

def test_workflow_error_path():
    from tools.doc_retriever import DocRetrievalError
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="COMPLAINT")

    with patch("graph.nodes.query_documents", side_effect=DocRetrievalError("연결 실패")), \
         patch("graph.nodes.ChatAnthropic", return_value=mock_llm):
        graph = build_graph()
        config = {"configurable": {"thread_id": "test-2"}}
        result = graph.invoke(
            {
                "raw_input": "오류가 발생했어요",
                "conversation_history": [],
                "voc_type": "",
                "retrieved_docs": [],
                "doc_retrieval_attempts": 0,
                "sql_results": [],
                "sql_tools_used": [],
                "response": "",
                "status": "processing",
                "error_message": None,
            },
            config,
        )
    assert result["status"] == "error"
    assert result["error_message"] is not None
