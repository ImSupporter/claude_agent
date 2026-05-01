import pytest
from unittest.mock import patch, MagicMock
from main import format_output, run_voc

def test_format_output_inquiry():
    state = {
        "voc_type": "INQUIRY",
        "retrieved_docs": [{"title": "결제 가이드"}, {"title": "오류 코드"}],
        "response": "결제는 설정에서 진행하세요.",
        "status": "done",
        "error_message": None,
    }
    output = format_output(state)
    assert "INQUIRY" in output
    assert "결제 가이드" in output
    assert "결제는 설정에서 진행하세요." in output

def test_format_output_error():
    state = {
        "voc_type": "",
        "retrieved_docs": [],
        "response": "",
        "status": "error",
        "error_message": "답변이 어렵습니다.",
    }
    output = format_output(state)
    assert "답변이 어렵습니다." in output

def test_run_voc_single_turn(capsys):
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "voc_type": "INQUIRY",
        "retrieved_docs": [{"title": "가이드"}],
        "response": "안내 드립니다.",
        "status": "done",
        "error_message": None,
    }
    mock_graph.get_state.return_value = MagicMock(next=[])
    with patch("main.build_graph", return_value=mock_graph):
        run_voc("결제 방법 알려주세요")
    captured = capsys.readouterr()
    assert "안내 드립니다." in captured.out
