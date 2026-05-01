import pytest
from unittest.mock import patch, MagicMock
from tools.read_tools import get_user_info, get_payment_status, READ_TOOLS


def test_get_user_info_success():
    mock_conn = MagicMock()
    mock_result = MagicMock()
    mock_result.mappings.return_value.fetchone.return_value = {
        "user_id": "u001", "name": "홍길동", "email": "hong@example.com",
        "status": "active", "created_at": "2025-01-01"
    }
    mock_conn.__enter__ = lambda s: mock_conn
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.execute.return_value = mock_result

    with patch("tools.read_tools.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = get_user_info.invoke({"user_id": "u001"})

    assert result["user_id"] == "u001"
    assert result["name"] == "홍길동"


def test_get_user_info_not_found():
    mock_conn = MagicMock()
    mock_result = MagicMock()
    mock_result.mappings.return_value.fetchone.return_value = None
    mock_conn.__enter__ = lambda s: mock_conn
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.execute.return_value = mock_result

    with patch("tools.read_tools.engine") as mock_engine:
        mock_engine.connect.return_value = mock_conn
        result = get_user_info.invoke({"user_id": "not_exist"})

    assert result == {"error": "사용자를 찾을 수 없습니다: not_exist"}


def test_read_tools_list():
    assert len(READ_TOOLS) == 2
    tool_names = [t.name for t in READ_TOOLS]
    assert "get_user_info" in tool_names
    assert "get_payment_status" in tool_names
