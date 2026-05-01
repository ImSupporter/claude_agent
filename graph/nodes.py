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
