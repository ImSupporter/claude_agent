# VOC Agent 아키텍처

## 개요

고객 VOC(불편사항 / 사용법 문의 / 요청사항)를 자동으로 분류하고, 외부 문서 DB를 조회해 조치 및 답변을 생성하는 LangGraph 기반 CLI 에이전트.

---

## 그래프 흐름

```
[입력 VOC]
    │
    ▼
┌─────────┐
│classify │  VOC를 5가지 유형 중 하나로 분류
└────┬────┘
     │
     ▼
┌──────────┐   answer ──────────────────┐
│supervise │                            ▼
│          │   retrieve ──► [retrieve] ─┘ (사이클)
│          │
│          │   end ──────────────────► [END]
└──────────┘
     │ answer
     ▼
┌───────┐
│ agent │  도구 호출 + 최종 답변 생성
└───┬───┘
    │
    ▼
  [END]
```

`retrieve → supervise` 는 사이클을 형성합니다. supervise가 문서 조회 후 충분한 정보가 모였다고 판단하면 answer로 전환해 agent로 진행합니다.

---

## 노드 설명

### `classify_node`

LLM을 호출해 VOC를 5가지 유형 중 하나로 분류합니다.

| 유형 | 설명 |
|------|------|
| `COMPLAINT` | 불편사항, 오류 신고, 데이터 이상 문의 |
| `INQUIRY` | 사용법 문의, 기능 설명 요청 |
| `REQUEST` | 기능 추가 요청, 개선 제안 |
| `DATA_MODIFICATION` | 데이터 수정/변경 요청 |
| `SIMPLE` | 간단한 인사, 단순 질문 (문서 조회 불필요) |

분류 결과를 `VocState.voc_type`에 저장합니다.

---

### `supervise_node`

LLM 구조화 출력(`SuperviseDecision`)으로 다음 행동을 결정합니다.

```python
class SuperviseDecision(BaseModel):
    action: Literal["answer", "retrieve", "ask"]
    question: str | None = None
```

| 결정 | 조건 | 다음 노드 |
|------|------|----------|
| `answer` | 현재 정보로 답변 가능 (SIMPLE, 문서 충분, 대화 완료) | `agent` |
| `retrieve` | 문서 조회가 필요한 경우 | `retrieve` |
| `ask` | 사용자에게 추가 정보가 필요한 경우 | — (interrupt 후 재판단) |

`ask` 결정 시 LangGraph의 `interrupt()`로 실행을 중단하고 사용자 답변을 기다립니다. 답변이 `conversation_history`에 추가된 뒤 같은 루프 안에서 재판단합니다. 최대 3회(`_MAX_ASK_ROUNDS`)까지 반복합니다.

`state["status"] == "error"`이면 LLM 호출 없이 즉시 `"end"`를 반환해 그래프를 종료합니다.

---

### `retrieve_node`

외부 문서 DB REST API를 호출해 VOC와 관련된 문서를 조회합니다. 최대 3회 재시도하며 모두 실패하면 `status = "error"`를 설정합니다.

- 성공: `retrieved_docs` 업데이트, `supervise`로 복귀
- 실패: `status = "error"`, `error_message` 설정, `supervise`로 복귀 (supervise가 즉시 end 처리)

---

### `agent_node`

`supervise_node`의 지시(`answer`)를 받아 최종 답변을 생성합니다. Tool calling 루프로 필요한 DB 조회/수정을 수행합니다.

**VOC 유형별 도구 선택:**
- `DATA_MODIFICATION`: READ_TOOLS + WRITE_TOOLS (조회 + 수정)
- 그 외: READ_TOOLS만 (조회 전용)

**사용 가능한 도구:**

| 도구 | 유형 | 설명 |
|------|------|------|
| `get_user_info` | READ | 사용자 기본 정보 조회 |
| `get_payment_status` | READ | 최근 결제 내역 조회 |
| `update_user_status` | WRITE | 사용자 상태 변경 |

---

## 상태 스키마 (`VocState`)

```python
class VocState(TypedDict):
    raw_input: str               # 원본 VOC 텍스트
    conversation_history: list[dict]  # supervise ask/answer 대화 이력
    voc_type: str                # COMPLAINT | INQUIRY | REQUEST | DATA_MODIFICATION | SIMPLE
    supervise_action: str        # answer | retrieve | end
    retrieved_docs: list[dict]   # 조회된 문서 목록
    doc_retrieval_attempts: int  # 문서 조회 시도 횟수
    sql_results: list[dict]      # 도구 호출 결과
    sql_tools_used: list[str]    # 사용된 도구 이름 목록
    response: str                # 최종 생성 답변
    status: str                  # processing | done | error
    error_message: str | None    # 에러 발생 시 메시지
```

---

## 외부 연동

### 문서 DB API (`tools/doc_retriever.py`)

```
POST {DOC_API_BASE_URL}/search
Body: {"query": "<voc_text>"}
Auth: Bearer {DOC_API_KEY}
```

- 응답: `list[dict]` — 각 항목은 `title`, `content` 포함
- 타임아웃: 10초, 최대 3회 재시도

### DB (`tools/read_tools.py`, `tools/write_tools.py`)

SQLAlchemy + `sql/` 디렉토리의 `.sql` 파일을 사용합니다.

---

## 설정 (`config.py`)

| 환경변수 | 기본값 | 설명 |
|---------|-------|------|
| `ANTHROPIC_API_KEY` | — | Claude API 키 |
| `DOC_API_BASE_URL` | — | 문서 DB API 베이스 URL |
| `DOC_API_KEY` | `""` | 문서 DB API 인증 키 |
| `DB_CONNECTION_STRING` | — | SQLAlchemy DB 연결 문자열 |
| `MODEL_NAME` | `claude-sonnet-4-6` | 사용할 Claude 모델 |

---

## 디렉토리 구조

```
voc_agent/
├── main.py                  # CLI 진입점 (단일/대화형/그래프 시각화)
├── config.py                # 환경변수 로딩 (pydantic-settings)
├── graph/
│   ├── state.py             # VocState TypedDict
│   ├── nodes.py             # classify, supervise, retrieve, agent 노드
│   ├── edges.py             # route_after_supervise 라우팅 함수
│   └── workflow.py          # StateGraph 조립 및 컴파일
├── prompts/
│   └── templates.py         # CLASSIFY_PROMPT, SUPERVISE_PROMPT, AGENT_SYSTEM_PROMPT
├── tools/
│   ├── doc_retriever.py     # 문서 DB REST API 클라이언트
│   ├── read_tools.py        # get_user_info, get_payment_status
│   └── write_tools.py       # update_user_status
└── sql/
    ├── get_user_info.sql
    ├── get_payment_status.sql
    └── update_user_status.sql
```

---

## 주요 의존성

| 패키지 | 용도 |
|--------|------|
| `langgraph` | 상태 기반 워크플로우, interrupt, MemorySaver |
| `langchain-anthropic` | Claude LLM 연동 |
| `langchain-core` | PromptTemplate, Tool |
| `pydantic` | SuperviseDecision 구조화 출력 스키마 |
| `sqlalchemy` | DB 쿼리 실행 |
| `httpx` | 문서 DB REST API 호출 |
| `pydantic-settings` | 환경변수 로딩 |
