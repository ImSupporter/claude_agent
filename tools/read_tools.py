from pathlib import Path
from langchain_core.tools import tool
from sqlalchemy import create_engine, text
from config import settings

engine = create_engine(settings.db_connection_string)


def _load_sql(filename: str) -> str:
    return (Path(__file__).parent.parent / "sql" / filename).read_text()


@tool
def get_user_info(user_id: str) -> dict:
    """사용자 기본 정보를 조회합니다."""
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(_load_sql("get_user_info.sql")), {"user_id": user_id}
            ).mappings().fetchone()
        if row is None:
            return {"error": f"사용자를 찾을 수 없습니다: {user_id}"}
        return dict(row)
    except Exception as e:
        return {"error": f"조회 중 오류가 발생했습니다: {e}"}


@tool
def get_payment_status(user_id: str) -> list[dict]:
    """사용자의 최근 결제 내역을 조회합니다."""
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(_load_sql("get_payment_status.sql")), {"user_id": user_id}
            ).mappings().fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": f"조회 중 오류가 발생했습니다: {e}"}]


READ_TOOLS = [get_user_info, get_payment_status]
