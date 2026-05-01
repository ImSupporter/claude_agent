import pytest
from unittest.mock import patch, MagicMock
from tools.doc_retriever import query_documents, DocRetrievalError


def test_query_documents_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"title": "결제 가이드", "content": "결제 방법 안내..."}
    ]
    with patch("httpx.Client.post", return_value=mock_response):
        docs = query_documents("결제 오류")
    assert len(docs) == 1
    assert docs[0]["title"] == "결제 가이드"


def test_query_documents_retries_on_failure():
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = Exception("서버 오류")
    with patch("httpx.Client.post", return_value=mock_response):
        with patch("time.sleep"):
            with pytest.raises(DocRetrievalError):
                query_documents("결제 오류")


def test_query_documents_succeeds_on_second_attempt():
    fail = MagicMock()
    fail.raise_for_status.side_effect = Exception("일시 오류")
    success = MagicMock()
    success.raise_for_status.return_value = None
    success.json.return_value = [{"title": "문서", "content": "내용"}]
    with patch("httpx.Client.post", side_effect=[fail, success]):
        with patch("time.sleep"):
            docs = query_documents("쿼리")
    assert len(docs) == 1
