import time
import httpx
from config import settings


class DocRetrievalError(Exception):
    pass


def query_documents(query: str, max_retries: int = 3) -> list[dict]:
    """Query documents from the document API with retry logic.

    Args:
        query: The search query string
        max_retries: Maximum number of retry attempts (default: 3)

    Returns:
        A list of document dictionaries matching the query

    Raises:
        DocRetrievalError: If all retry attempts fail
    """
    headers = {"Authorization": f"Bearer {settings.doc_api_key}"} if settings.doc_api_key else {}
    last_exc: Exception | None = None

    for attempt in range(max_retries):
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{settings.doc_api_base_url}/search",
                    json={"query": query},
                    headers=headers,
                    timeout=10.0,
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            last_exc = e
            if attempt < max_retries - 1:
                time.sleep(1)

    raise DocRetrievalError(f"문서 조회 실패 ({max_retries}회 시도): {last_exc}")
