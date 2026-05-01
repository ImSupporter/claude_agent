from pathlib import Path
from langchain_core.tools import tool
from sqlalchemy import create_engine, text
from config import settings

engine = create_engine(settings.db_connection_string)

def _load_sql(filename: str) -> str:
    return (Path(__file__).parent.parent / "sql" / filename).read_text()

@tool
def update_user_status(user_id: str, new_status: str) -> dict:
    """사용자의 상태를 변경합니다. new_status: active | inactive | suspended"""
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text(_load_sql("update_user_status.sql")),
                {"user_id": user_id, "new_status": new_status},
            )
        if result.rowcount == 0:
            return {"error": f"업데이트된 행이 없습니다: {user_id}"}
        return {"updated_rows": result.rowcount, "user_id": user_id, "new_status": new_status}
    except Exception as e:
        return {"error": f"수정 중 오류가 발생했습니다: {e}"}

WRITE_TOOLS = [update_user_status]
