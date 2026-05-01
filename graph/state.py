from typing import TypedDict


class VocState(TypedDict):
    raw_input: str
    conversation_history: list[dict]
    voc_type: str
    retrieved_docs: list[dict]
    doc_retrieval_attempts: int
    sql_results: list[dict]
    sql_tools_used: list[str]
    response: str
    status: str
    error_message: str | None
