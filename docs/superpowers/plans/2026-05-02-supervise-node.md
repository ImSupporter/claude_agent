# supervise_node 도입 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `classify_node` 다음에 LLM 기반 `supervise_node`를 삽입해, 행동 판단(직접 답변 / 문서 조회 / 사용자 추가 질문)을 에이전트에서 분리하고 `agent_node`를 순수 답변 생성기로 단순화한다.

**Architecture:** classify → supervise (LLM 구조화 출력으로 "answer"/"retrieve"/"ask" 결정) → retrieve(필요 시) → supervise(재판단) → agent. supervise_node가 interrupt도 담당하며, agent_node는 Tool 호출 + 답변 생성만 수행한다.

**Tech Stack:** Python 3.11+, langgraph>=0.2, langchain-anthropic, pydantic, pytest, pytest-mock

---

## 파일 구조

| 파일 | 변경 내용 |
|------|-----------|
| `graph/state.py` | `supervise_action: str` 필드 추가 |
| `prompts/templates.py` | `SUPERVISE_PROMPT` 추가, `NEEDS_CLARIFICATION_PROMPT` 삭제 |
| `graph/nodes.py` | `supervise_node` 추가 (SuperviseDecision 포함), `agent_node` 단순화 |
| `graph/edges.py` | `route_after_supervise` 추가, `route_after_classify` 삭제, `route_after_retrieve` 변경 |
| `graph/workflow.py` | 노드/엣지 재조립 |
| `tests/test_state.py` | `supervise_action` 필드 테스트 추가 |
| `tests/test_nodes.py` | `supervise_node` 테스트 추가, `agent_node` 테스트 갱신 |
| `tests/test_edges.py` | 엣지 테스트 전체 갱신 |
| `tests/test_workflow.py` | 워크플로우 통합 테스트 갱신 |

---

## Task 1: VocState에 supervise_action 필드 추가

**Files:**
- Modify: `graph/state.py`
- Modify: `tests/test_state.py`

- [ ] **Step 1: 테스트 추가 (tests/test_state.py)**

```python
def test_voc_state_supervise_action_field():
    state: VocState = {
        "raw_input": "결제가 안 돼요",
        "conversation_history": [],
        "voc_type": "",
        "supervise_action": "",
        "retrieved_docs": [],
        "doc_retrieval_attempts": 0,
        "sql_results": [],
        "sql_tools_used": [],
        "response": "",
        "status": "processing",
        "error_message": None,
    }
    assert state["supervise_action"] == ""
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

```bash
pytest tests/test_state.py::test_voc_state_supervise_action_field -v
```

Expected: `FAILED` — TypedDict에 `supervise_action` 키가 없어 mypy/타입 오류, 또는 키 없이 통과. 타입 에러가 없으면 키가 없는 것을 확인하기 위해 아래처럼도 실행.

```bash
python -c "from graph.state import VocState; import inspect; print(VocState.__annotations__)"
```

Expected: `supervise_action` 없음.

- [ ] **Step 3: graph/state.py에 필드 추가**

```python
from typing import TypedDict

class VocState(TypedDict):
    raw_input: str
    conversation_history: list[dict]
    voc_type: str
    supervise_action: str
    retrieved_docs: list[dict]
    doc_retrieval_attempts: int
    sql_results: list[dict]
    sql_tools_used: list[str]
    response: str
    status: str
    error_message: str | None
```

- [ ] **Step 4: main.py의 _initial_state에 supervise_action 추가**

`main.py` 의 `_initial_state` 함수를 아래와 같이 수정:

```python
def _initial_state(voc_text: str) -> VocState:
    return {
        "raw_input": voc_text,
        "conversation_history": [],
        "voc_type": "",
        "supervise_action": "",
        "retrieved_docs": [],
        "doc_retrieval_attempts": 0,
        "sql_results": [],
        "sql_tools_used": [],
        "response": "",
        "status": "processing",
        "error_message": None,
    }
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
pytest tests/test_state.py -v
```

Expected: 전체 `PASSED`

- [ ] **Step 6: tests/test_nodes.py의 _base_state 업데이트**

`tests/test_nodes.py`의 기존 `_base_state` 함수에 `supervise_action` 필드 추가:

```python
def _base_state(**kwargs) -> VocState:
    return {
        "raw_input": "결제가 안 돼요",
        "conversation_history": [],
        "voc_type": "",
        "supervise_action": "",
        "retrieved_docs": [],
        "doc_retrieval_attempts": 0,
        "sql_results": [],
        "sql_tools_used": [],
        "response": "",
        "status": "processing",
        "error_message": None,
        **kwargs,
    }
```

- [ ] **Step 7: 커밋**

```bash
git add graph/state.py main.py tests/test_state.py tests/test_nodes.py
git commit -m "feat: VocState에 supervise_action 필드 추가"
```

---

## Task 2: SUPERVISE_PROMPT 추가 및 NEEDS_CLARIFICATION_PROMPT 제거

**Files:**
- Modify: `prompts/templates.py`

- [ ] **Step 1: SUPERVISE_PROMPT 추가 및 NEEDS_CLARIFICATION_PROMPT 삭제**

`prompts/templates.py` 전체를 아래와 같이 교체:

```python
from langchain_core.prompts import ChatPromptTemplate

CLASSIFY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 고객 VOC를 분류하는 전문가입니다.
다음 VOC를 아래 5가지 유형 중 하나로 분류하세요.
반드시 유형 이름만 한 단어로 답변하세요.

유형:
- COMPLAINT: 불편사항, 오류 신고, 데이터 이상 문의
- INQUIRY: 사용법 문의, 기능 설명 요청
- REQUEST: 기능 추가 요청, 개선 제안
- DATA_MODIFICATION: 데이터 수정/변경 요청
- SIMPLE: 간단한 인사, 단순 질문 (문서 조회 불필요)"""),
    ("human", "VOC: {voc_text}"),
])

SUPERVISE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 VOC 처리 워크플로우의 수퍼바이저입니다.
현재 상태를 분석하여 다음 행동 중 하나를 결정하세요:

- answer: 현재 정보만으로 충분히 답변 가능합니다.
  (예: SIMPLE 유형 / 관련 문서가 이미 충분히 조회됨 / 대화를 통해 필요한 정보가 수집됨)
- retrieve: 정확한 답변을 위해 관련 문서 조회가 먼저 필요합니다.
  (문서가 아직 조회되지 않았고, 내용 기반 답변이 필요한 경우)
- ask: 답변하려면 사용자에게 추가 정보(예: 사용자 ID, 주문번호 등)를 먼저 받아야 합니다.
  (question 필드에 사용자에게 물어볼 질문을 작성하세요)

VOC 유형: {voc_type}
원본 VOC: {voc_text}
조회된 문서: {docs_context}
대화 이력: {conversation_history}"""),
    ("human", "다음 행동을 결정하세요."),
])

AGENT_SYSTEM_PROMPT = """당신은 고객 VOC 처리 전문 에이전트입니다.
아래 참고 문서와 제공된 도구를 활용해 고객의 문제를 해결하거나 안내하세요.

[참고 문서]
{docs_context}

[대화 이력]
{conversation_history}

규칙:
- 답변은 한국어로 작성하세요.
- 문서에 근거한 정확한 정보만 제공하세요.
- 데이터 조회/수정이 필요하면 제공된 도구를 사용하세요."""
```

- [ ] **Step 2: 임포트 확인**

```bash
python -c "from prompts.templates import CLASSIFY_PROMPT, SUPERVISE_PROMPT, AGENT_SYSTEM_PROMPT; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: NEEDS_CLARIFICATION_PROMPT가 제거됐는지 확인**

```bash
python -c "from prompts.templates import NEEDS_CLARIFICATION_PROMPT"
```

Expected: `ImportError: cannot import name 'NEEDS_CLARIFICATION_PROMPT'`

- [ ] **Step 4: 커밋**

```bash
git add prompts/templates.py
git commit -m "feat: SUPERVISE_PROMPT 추가 및 NEEDS_CLARIFICATION_PROMPT 제거"
```

---

## Task 3: supervise_node 구현

**Files:**
- Modify: `graph/nodes.py`
- Modify: `tests/test_nodes.py`

- [ ] **Step 1: 테스트 추가 (tests/test_nodes.py)**

파일 상단 import에 아래 추가:

```python
from pydantic import BaseModel
from typing import Literal
from graph.nodes import supervise_node
```

테스트 함수 추가 (`_base_state`는 Task 1에서 이미 업데이트됨):

```python
def test_supervise_node_returns_answer_for_simple():
    """SIMPLE 유형: LLM이 answer 반환"""
    from graph.nodes import SuperviseDecision
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = SuperviseDecision(action="answer")
    mock_llm.with_structured_output.return_value = mock_structured
    with patch("graph.nodes.ChatAnthropic", return_value=mock_llm):
        result = supervise_node(_base_state(voc_type="SIMPLE"))
    assert result["supervise_action"] == "answer"

def test_supervise_node_returns_retrieve_when_no_docs():
    """문서 없는 COMPLAINT: LLM이 retrieve 반환"""
    from graph.nodes import SuperviseDecision
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = SuperviseDecision(action="retrieve")
    mock_llm.with_structured_output.return_value = mock_structured
    with patch("graph.nodes.ChatAnthropic", return_value=mock_llm):
        result = supervise_node(_base_state(voc_type="COMPLAINT"))
    assert result["supervise_action"] == "retrieve"

def test_supervise_node_returns_end_on_error():
    """status==error: LLM 호출 없이 즉시 end 반환"""
    with patch("graph.nodes.ChatAnthropic") as mock_cls:
        result = supervise_node(_base_state(status="error"))
    mock_cls.assert_not_called()
    assert result["supervise_action"] == "end"

def test_supervise_node_interrupt_on_ask():
    """ask 후 interrupt → 재판단 → answer"""
    from graph.nodes import SuperviseDecision
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.side_effect = [
        SuperviseDecision(action="ask", question="사용자 ID가 무엇인가요?"),
        SuperviseDecision(action="answer"),
    ]
    mock_llm.with_structured_output.return_value = mock_structured
    with patch("graph.nodes.ChatAnthropic", return_value=mock_llm), \
         patch("graph.nodes.interrupt", return_value="user123"):
        result = supervise_node(_base_state(
            voc_type="COMPLAINT",
            retrieved_docs=[{"title": "가이드", "content": "내용"}],
        ))
    assert result["supervise_action"] == "answer"
    history = result["conversation_history"]
    assert history[0] == {"role": "assistant", "content": "사용자 ID가 무엇인가요?"}
    assert history[1] == {"role": "user", "content": "user123"}
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

```bash
pytest tests/test_nodes.py::test_supervise_node_returns_answer_for_simple -v
```

Expected: `FAILED` — `supervise_node` 없음

- [ ] **Step 3: graph/nodes.py에 SuperviseDecision 및 supervise_node 추가**

파일 상단 import에 추가:

```python
from pydantic import BaseModel
from typing import Literal
from prompts.templates import CLASSIFY_PROMPT, AGENT_SYSTEM_PROMPT, SUPERVISE_PROMPT
```

(기존 `NEEDS_CLARIFICATION_PROMPT` import 제거)

`classify_node` 아래에 추가:

```python
class SuperviseDecision(BaseModel):
    action: Literal["answer", "retrieve", "ask"]
    question: str | None = None


def supervise_node(state: VocState) -> dict:
    if state["status"] == "error":
        return {"supervise_action": "end"}

    llm = ChatAnthropic(model=settings.model_name, api_key=settings.anthropic_api_key)
    llm_structured = llm.with_structured_output(SuperviseDecision)
    conversation_history = list(state.get("conversation_history", []))

    while True:
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
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_nodes.py::test_supervise_node_returns_answer_for_simple \
       tests/test_nodes.py::test_supervise_node_returns_retrieve_when_no_docs \
       tests/test_nodes.py::test_supervise_node_returns_end_on_error \
       tests/test_nodes.py::test_supervise_node_interrupt_on_ask -v
```

Expected: 4개 `PASSED`

- [ ] **Step 5: 커밋**

```bash
git add graph/nodes.py tests/test_nodes.py
git commit -m "feat: supervise_node 구현 (LLM 구조화 출력, interrupt 루프)"
```

---

## Task 4: edges.py 갱신

**Files:**
- Modify: `graph/edges.py`
- Modify: `tests/test_edges.py`

- [ ] **Step 1: tests/test_edges.py 전체 교체**

```python
from langgraph.graph import END
from graph.state import VocState
from graph.edges import route_after_supervise, route_after_retrieve


def _state(supervise_action: str = "", status: str = "processing") -> VocState:
    return {
        "raw_input": "", "conversation_history": [], "voc_type": "",
        "supervise_action": supervise_action,
        "retrieved_docs": [], "doc_retrieval_attempts": 0,
        "sql_results": [], "sql_tools_used": [],
        "response": "", "status": status, "error_message": None,
    }


def test_route_after_supervise_answer():
    assert route_after_supervise(_state(supervise_action="answer")) == "agent"


def test_route_after_supervise_retrieve():
    assert route_after_supervise(_state(supervise_action="retrieve")) == "retrieve"


def test_route_after_supervise_end():
    assert route_after_supervise(_state(supervise_action="end")) == END


def test_route_after_retrieve_always_returns_supervise():
    assert route_after_retrieve(_state(status="processing")) == "supervise"


def test_route_after_retrieve_error_still_returns_supervise():
    assert route_after_retrieve(_state(status="error")) == "supervise"
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

```bash
pytest tests/test_edges.py -v
```

Expected: `ImportError` — `route_after_supervise` 없음

- [ ] **Step 3: graph/edges.py 전체 교체**

```python
from langgraph.graph import END
from graph.state import VocState


def route_after_supervise(state: VocState) -> str:
    action = state["supervise_action"]
    if action == "answer":
        return "agent"
    if action == "retrieve":
        return "retrieve"
    return END


def route_after_retrieve(state: VocState) -> str:
    return "supervise"
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_edges.py -v
```

Expected: 5개 `PASSED`

- [ ] **Step 5: 커밋**

```bash
git add graph/edges.py tests/test_edges.py
git commit -m "feat: route_after_supervise 추가, route_after_classify 제거, route_after_retrieve 단순화"
```

---

## Task 5: agent_node 단순화

**Files:**
- Modify: `graph/nodes.py`
- Modify: `tests/test_nodes.py`

- [ ] **Step 1: tests/test_nodes.py의 agent_node 테스트 갱신**

기존 `test_agent_node_generates_response` 테스트를 아래로 교체 (interrupt mock 제거):

```python
def test_agent_node_generates_response():
    state = _base_state(
        voc_type="INQUIRY",
        retrieved_docs=[{"title": "가이드", "content": "결제는 설정 메뉴에서..."}],
        conversation_history=[],
    )
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="결제 설정 메뉴에서 진행하세요.", tool_calls=[])
    mock_llm.bind_tools.return_value = mock_llm
    with patch("graph.nodes.ChatAnthropic", return_value=mock_llm):
        result = agent_node(state)
    assert result["response"] == "결제 설정 메뉴에서 진행하세요."
    assert result["status"] == "done"


def test_agent_node_write_tools_only_for_data_modification():
    state = _base_state(
        voc_type="COMPLAINT",
        retrieved_docs=[{"title": "가이드", "content": "..."}],
    )
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="답변입니다.", tool_calls=[])
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    with patch("graph.nodes.ChatAnthropic", return_value=mock_llm):
        agent_node(state)
    bound_tools = mock_llm.bind_tools.call_args[0][0]
    tool_names = [t.name for t in bound_tools]
    assert "update_user_status" not in tool_names
```

- [ ] **Step 2: 테스트 실행 (현재 상태 확인)**

```bash
pytest tests/test_nodes.py::test_agent_node_generates_response \
       tests/test_nodes.py::test_agent_node_write_tools_only_for_data_modification -v
```

Expected: 현재 코드에 interrupt/clarification 로직이 있으므로 mock 개수 불일치 등으로 FAILED 가능.

- [ ] **Step 3: graph/nodes.py의 agent_node 교체**

기존 `agent_node` 함수를 아래로 교체:

```python
def agent_node(state: VocState) -> dict:
    from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage as LCToolMessage

    llm = ChatAnthropic(model=settings.model_name, api_key=settings.anthropic_api_key)
    docs_context = _format_docs(state["retrieved_docs"])
    conversation_history = state.get("conversation_history", [])

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
        "conversation_history": list(conversation_history),
        "status": "done",
    }
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_nodes.py -v
```

Expected: 전체 `PASSED`

- [ ] **Step 5: 커밋**

```bash
git add graph/nodes.py tests/test_nodes.py
git commit -m "refactor: agent_node에서 interrupt/clarification 로직 제거 (supervise_node로 이동)"
```

---

## Task 6: workflow.py 재조립

**Files:**
- Modify: `graph/workflow.py`
- Modify: `tests/test_workflow.py`

- [ ] **Step 1: tests/test_workflow.py 전체 교체**

```python
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage
from pydantic import BaseModel
from typing import Literal
from graph.workflow import build_graph


class SuperviseDecision(BaseModel):
    action: Literal["answer", "retrieve", "ask"]
    question: str | None = None


def _initial_state(raw_input: str) -> dict:
    return {
        "raw_input": raw_input,
        "conversation_history": [],
        "voc_type": "",
        "supervise_action": "",
        "retrieved_docs": [],
        "doc_retrieval_attempts": 0,
        "sql_results": [],
        "sql_tools_used": [],
        "response": "",
        "status": "processing",
        "error_message": None,
    }


def test_workflow_simple_path():
    """SIMPLE 유형: retrieve 없이 classify → supervise → agent"""
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = SuperviseDecision(action="answer")
    mock_llm.with_structured_output.return_value = mock_structured
    mock_llm.invoke.side_effect = [
        MagicMock(content="SIMPLE"),
        AIMessage(content="안녕하세요!", tool_calls=[]),
    ]
    mock_llm.bind_tools.return_value = mock_llm

    with patch("graph.nodes.ChatAnthropic", return_value=mock_llm):
        graph = build_graph()
        result = graph.invoke(
            _initial_state("안녕"),
            {"configurable": {"thread_id": "test-simple"}},
        )
    assert result["status"] == "done"
    assert result["voc_type"] == "SIMPLE"
    assert result["response"] == "안녕하세요!"


def test_workflow_inquiry_with_retrieve():
    """INQUIRY 유형: classify → supervise(retrieve) → retrieve → supervise(answer) → agent"""
    docs = [{"title": "결제 가이드", "content": "결제는 설정에서..."}]
    mock_llm = MagicMock()
    mock_structured_1 = MagicMock()
    mock_structured_1.invoke.return_value = SuperviseDecision(action="retrieve")
    mock_structured_2 = MagicMock()
    mock_structured_2.invoke.return_value = SuperviseDecision(action="answer")
    mock_llm.with_structured_output.side_effect = [mock_structured_1, mock_structured_2]
    mock_llm.invoke.side_effect = [
        MagicMock(content="INQUIRY"),
        AIMessage(content="안내 드립니다.", tool_calls=[]),
    ]
    mock_llm.bind_tools.return_value = mock_llm

    with patch("graph.nodes.query_documents", return_value=docs), \
         patch("graph.nodes.ChatAnthropic", return_value=mock_llm):
        graph = build_graph()
        result = graph.invoke(
            _initial_state("결제 방법을 알려주세요"),
            {"configurable": {"thread_id": "test-inquiry"}},
        )
    assert result["status"] == "done"
    assert result["voc_type"] == "INQUIRY"
    assert result["response"] == "안내 드립니다."


def test_workflow_error_path():
    """retrieve 실패: supervise가 end 반환 → 워크플로우 종료"""
    from tools.doc_retriever import DocRetrievalError

    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = SuperviseDecision(action="retrieve")
    mock_llm.with_structured_output.return_value = mock_structured
    mock_llm.invoke.return_value = MagicMock(content="COMPLAINT")

    with patch("graph.nodes.query_documents", side_effect=DocRetrievalError("연결 실패")), \
         patch("graph.nodes.ChatAnthropic", return_value=mock_llm):
        graph = build_graph()
        result = graph.invoke(
            _initial_state("오류가 발생했어요"),
            {"configurable": {"thread_id": "test-error"}},
        )
    assert result["status"] == "error"
    assert result["error_message"] is not None
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

```bash
pytest tests/test_workflow.py -v
```

Expected: `FAILED` — 기존 workflow에 supervise_node 없음

- [ ] **Step 3: graph/workflow.py 전체 교체**

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from graph.state import VocState
from graph.nodes import classify_node, supervise_node, retrieve_node, agent_node
from graph.edges import route_after_supervise, route_after_retrieve


def build_graph() -> StateGraph:
    builder = StateGraph(VocState)

    builder.add_node("classify", classify_node)
    builder.add_node("supervise", supervise_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("agent", agent_node)

    builder.set_entry_point("classify")
    builder.add_edge("classify", "supervise")
    builder.add_conditional_edges("supervise", route_after_supervise, {
        "agent": "agent",
        "retrieve": "retrieve",
        END: END,
    })
    builder.add_edge("retrieve", "supervise")
    builder.add_edge("agent", END)

    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_workflow.py -v
```

Expected: 3개 `PASSED`

- [ ] **Step 5: 전체 테스트 통과 확인**

```bash
pytest -v
```

Expected: 전체 `PASSED`

- [ ] **Step 6: 커밋**

```bash
git add graph/workflow.py tests/test_workflow.py
git commit -m "feat: workflow에 supervise_node 삽입 및 retrieve→supervise 사이클 구성"
```

---

## Task 7: 기존 docs 업데이트 및 커밋

**Files:**
- Already modified: `docs/superpowers/specs/2026-05-01-voc-agent-design.md`
- Already created: `docs/superpowers/specs/2026-05-02-supervise-node-design.md`
- Create: `docs/superpowers/plans/2026-05-02-supervise-node.md` (이 파일)

- [ ] **Step 1: 커밋**

```bash
git add docs/
git commit -m "docs: supervise_node 설계 문서 추가 및 기존 설계 문서 갱신"
```

---

## 완료 기준

- [ ] `pytest -v` 전체 통과
- [ ] `python main.py --draw` 실행 시 그래프에 `supervise` 노드 포함됨
- [ ] `python main.py -i "안녕"` → SIMPLE 분류 후 retrieve 없이 즉시 답변
- [ ] `python main.py -i "결제 오류가 있어요"` → supervise가 retrieve 판단 후 문서 조회 → 답변
- [ ] retrieve 실패 시 에러 메시지 출력 후 정상 종료
