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
