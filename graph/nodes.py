from langchain_anthropic import ChatAnthropic
from langchain_core.tools import BaseTool
from langgraph.types import interrupt
from graph.state import VocState
from prompts.templates import CLASSIFY_PROMPT, AGENT_SYSTEM_PROMPT, NEEDS_CLARIFICATION_PROMPT
from tools.doc_retriever import query_documents, DocRetrievalError
from tools.read_tools import READ_TOOLS
from tools.write_tools import WRITE_TOOLS
from config import settings

VALID_VOC_TYPES = {"COMPLAINT", "INQUIRY", "REQUEST", "DATA_MODIFICATION"}


def classify_node(state: VocState) -> dict:
    llm = ChatAnthropic(model=settings.model_name, api_key=settings.anthropic_api_key)
    messages = CLASSIFY_PROMPT.format_messages(voc_text=state["raw_input"])
    response = llm.invoke(messages)
    voc_type = response.content.strip()
    if voc_type not in VALID_VOC_TYPES:
        voc_type = "INQUIRY"
    return {"voc_type": voc_type}


def retrieve_node(state: VocState) -> dict:
    attempts = state.get("doc_retrieval_attempts", 0) + 1
    try:
        docs = query_documents(state["raw_input"])
        return {
            "retrieved_docs": docs,
            "doc_retrieval_attempts": attempts,
            "status": "processing",
        }
    except DocRetrievalError:
        return {
            "doc_retrieval_attempts": attempts,
            "status": "error",
            "error_message": "현재 관련 정보를 조회할 수 없어 답변이 어렵습니다. 잠시 후 다시 시도해 주세요.",
        }
