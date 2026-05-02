from langchain_anthropic import ChatAnthropic
from langchain_core.tools import BaseTool
from langgraph.types import interrupt
from pydantic import BaseModel
from typing import Literal
from graph.state import VocState
from prompts.templates import CLASSIFY_PROMPT, AGENT_SYSTEM_PROMPT, SUPERVISE_PROMPT
from tools.doc_retriever import query_documents, DocRetrievalError
from tools.read_tools import READ_TOOLS
from tools.write_tools import WRITE_TOOLS
from config import settings

VALID_VOC_TYPES = {"COMPLAINT", "INQUIRY", "REQUEST", "DATA_MODIFICATION", "SIMPLE"}
_MAX_ASK_ROUNDS = 3


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


def _select_tools(voc_type: str) -> list[BaseTool]:
    if voc_type == "DATA_MODIFICATION":
        return READ_TOOLS + WRITE_TOOLS
    return list(READ_TOOLS)


def _format_docs(docs: list[dict]) -> str:
    return "\n\n".join(f"[{d['title']}]\n{d['content']}" for d in docs)


def _format_history(history: list[dict]) -> str:
    if not history:
        return "없음"
    return "\n".join(f"{h['role']}: {h['content']}" for h in history)


class SuperviseDecision(BaseModel):
    action: Literal["answer", "retrieve", "ask"]
    question: str | None = None


def supervise_node(state: VocState) -> dict:
    if state["status"] == "error":
        return {"supervise_action": "end"}

    llm = ChatAnthropic(model=settings.model_name, api_key=settings.anthropic_api_key)
    llm_structured = llm.with_structured_output(SuperviseDecision)
    conversation_history = list(state.get("conversation_history", []))

    for _ in range(_MAX_ASK_ROUNDS):
        messages = SUPERVISE_PROMPT.format_messages(
            voc_type=state["voc_type"],
            voc_text=state["raw_input"],
            docs_context=_format_docs(state["retrieved_docs"]) or "없음",
            conversation_history=_format_history(conversation_history),
        )
        decision: SuperviseDecision = llm_structured.invoke(messages)

        if decision.action == "answer":
            return {
                "supervise_action": "answer",
                "conversation_history": conversation_history,
            }
        if decision.action == "retrieve":
            return {
                "supervise_action": "retrieve",
                "conversation_history": conversation_history,
            }
        if decision.action == "ask":
            user_answer = interrupt(decision.question)
            conversation_history.append({"role": "assistant", "content": decision.question})
            conversation_history.append({"role": "user", "content": user_answer})

    return {"supervise_action": "answer", "conversation_history": conversation_history}


def agent_node(state: VocState) -> dict:
    from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage as LCToolMessage

    llm = ChatAnthropic(model=settings.model_name, api_key=settings.anthropic_api_key)
    docs_context = _format_docs(state["retrieved_docs"])
    conversation_history = list(state.get("conversation_history", []))

    tools = _select_tools(state["voc_type"])
    llm_with_tools = llm.bind_tools(tools)
    tool_map = {t.name: t for t in tools}

    messages = [
        SystemMessage(content=AGENT_SYSTEM_PROMPT.format(
            docs_context=docs_context,
            conversation_history=_format_history(conversation_history),
        )),
        HumanMessage(content=state["raw_input"]),
    ]

    sql_results: list[dict] = []
    sql_tools_used: list[str] = []

    response = llm_with_tools.invoke(messages)
    while getattr(response, "tool_calls", None):
        messages.append(response)
        for tc in response.tool_calls:
            tool_result = tool_map[tc["name"]].invoke(tc["args"])
            sql_results.append({"tool": tc["name"], "result": tool_result})
            sql_tools_used.append(tc["name"])
            messages.append(LCToolMessage(content=str(tool_result), tool_call_id=tc["id"]))
        response = llm_with_tools.invoke(messages)

    return {
        "response": response.content,
        "sql_results": sql_results,
        "sql_tools_used": sql_tools_used,
        "conversation_history": conversation_history,
        "status": "done",
    }
