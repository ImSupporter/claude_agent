# VOC Agent 설계 문서

**작성일:** 2026-05-01  
**상태:** 승인됨

---

## 1. 프로젝트 개요

사용자가 시스템에 남긴 VOC(Voice of Customer)를 분류하고, 외부 문서 DB REST API 및 미리 정의된 SQL Tool을 활용해 자동으로 조치·답변을 생성하는 LangGraph 기반 CLI 에이전트.

### 목표
- VOC 유형 자동 분류 (LLM 기반)
- 문서 DB 검색 결과를 근거로 답변 생성
- 데이터 조회/수정 요청 시 SQL Tool 자동 실행
- 멀티턴 대화로 정보 부족 시 사용자에게 추가 질문
- 향후 메신저 REST API 발신으로 확장 가능한 구조

---

## 2. VOC 유형 분류 체계

| 유형 | 설명 | SQL Tool 접근 |
|------|------|--------------|
| `COMPLAINT` | 불편사항, 오류 신고, "내 데이터 왜이래요?" | read_tools (SELECT만) |
| `INQUIRY` | 사용법 문의 | read_tools (SELECT만) |
| `REQUEST` | 기능 요청, 개선 제안 | read_tools (SELECT만) |
| `DATA_MODIFICATION` | 데이터 수정 요청 | read_tools + write_tools |

- 분류는 Claude LLM이 수행 (키워드 기반 아님)
- `write_tools`는 `DATA_MODIFICATION` 유형에서만 에이전트에 제공 → 안전성 확보

---

## 3. 전체 아키텍처 및 그래프 흐름

```
CLI 입력 (VOC 텍스트)
        ↓
  [classify_node]
    LLM이 voc_type 판별
        ↓
  [retrieve_node]
    POST /search 호출 (최대 3회 재시도)
    실패 시 → status=error, "답변 불가" 출력 후 종료
        ↓
  [interrupt?]  ──── 에이전트가 추가 정보 필요 판단 시
    사용자 질문 → 답변 → conversation_history 누적
    (멀티턴 루프, MemorySaver checkpointer)
        ↓
  [agent_node]
    voc_type에 따라 tool 집합 결정
    ├── COMPLAINT / INQUIRY / REQUEST → read_tools만 제공
    └── DATA_MODIFICATION             → read_tools + write_tools 제공
    Claude가 필요한 SQL Tool 선택적 호출
    최종 response 생성
        ↓
  [output]
    구조화 출력 (유형 + 참고문서 + 답변)

  [향후 확장]
    → send_message_node (메신저 REST API 발신)
```

---

## 4. VocState 스키마

```python
class VocState(TypedDict):
    # 입력
    raw_input: str                    # 원본 VOC 텍스트
    conversation_history: list[dict]  # 멀티턴 대화 이력

    # 분류
    voc_type: str                     # COMPLAINT | INQUIRY | REQUEST | DATA_MODIFICATION

    # 문서 검색
    retrieved_docs: list[dict]        # POST /search 결과
    doc_retrieval_attempts: int       # 재시도 횟수 (최대 3)

    # SQL 실행
    sql_results: list[dict]           # SELECT/DML 실행 결과
    sql_tools_used: list[str]         # 실행된 Tool 이름 목록

    # 출력
    response: str                     # 최종 답변 텍스트
    status: str                       # processing | done | error | awaiting_input
    error_message: str | None         # 에러 시 안내 메시지
```

---

## 5. 외부 문서 DB API

- **방식:** `POST /search`
- **요청 body:** `{"query": "<VOC 텍스트 또는 키워드>"}`
- **응답:** 관련 문서 목록 `[{"title": "...", "content": "..."}]`
- **재시도:** 최대 3회, 1초 간격
- **실패 처리:** 3회 모두 실패 시 `status=error`, 아래 메시지 출력 후 종료
  > "현재 관련 정보를 조회할 수 없어 답변이 어렵습니다. 잠시 후 다시 시도해 주세요."

---

## 6. SQL Tool 설계

### 구조
```
tools/
├── read_tools.py    # SELECT 쿼리 함수들 (@tool 데코레이터)
└── write_tools.py   # INSERT/UPDATE/DELETE 쿼리 함수들 (@tool 데코레이터)
```

- 각 Tool은 미리 정의된 SQL 파일을 로드해 실행하는 Python 함수
- LangChain `@tool` 데코레이터로 래핑
- SQL 실행 실패 시 에러 메시지를 `sql_results`에 담아 Claude가 답변에 포함

### 예시
```python
@tool
def get_user_payment_status(user_id: str) -> dict:
    """사용자의 결제 상태를 조회합니다."""
    # SQL 파일 로드 후 실행
    ...
```

---

## 7. 에러 처리

| 상황 | 처리 방식 |
|------|-----------|
| 문서 DB API 3회 실패 | `status=error` → "답변 불가" 안내 메시지 출력 후 종료 |
| SQL Tool 실행 실패 | 에러를 `sql_results`에 포함 → Claude가 "조회 중 오류가 발생했습니다" 형태로 답변 |
| LLM 호출 실패 | 예외 상위 전파 → CLI에서 캐치 후 안내 메시지 출력 |

---

## 8. CLI 출력 형식

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VOC 유형   : 사용법 문의 (INQUIRY)
참고 문서  : [결제 프로세스 가이드], [오류 코드 목록]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
결제 버튼이 눌리지 않는 경우, 브라우저 캐시를
삭제하신 후 다시 시도해 주세요. ...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 향후 메신저 발신 확장
- `response` + `voc_type` + `sql_results`를 JSON 직렬화
- `send_message_node`를 그래프에 추가하면 메신저 REST API 연동 가능

---

## 9. 디렉토리 구조

```
voc_agent/
├── main.py                  # CLI 진입점 (argparse)
├── graph/
│   ├── workflow.py          # StateGraph 정의 및 컴파일
│   ├── nodes.py             # classify, retrieve, agent 노드 함수
│   ├── edges.py             # 조건부 라우팅 함수
│   └── state.py             # VocState 스키마
├── tools/
│   ├── read_tools.py        # SELECT SQL Tool (@tool)
│   └── write_tools.py       # DML SQL Tool (@tool)
├── sql/
│   └── *.sql                # 미리 정의된 SQL 파일들
├── prompts/
│   └── templates.py         # LangChain PromptTemplate 모음
├── config.py                # 환경변수 및 설정
├── requirements.txt
└── .env.example
```

---

## 10. 주요 의존성

| 패키지 | 용도 |
|--------|------|
| `langgraph` | 상태 기반 워크플로우, interrupt(), MemorySaver |
| `langchain-anthropic` | Claude LLM 연동 |
| `langchain-core` | PromptTemplate, @tool 데코레이터 |
| `httpx` | 문서 DB REST API 호출 |
| `python-dotenv` | 환경변수 로딩 |

---

## 11. 환경변수

| 변수명 | 설명 |
|--------|------|
| `ANTHROPIC_API_KEY` | Claude API 키 |
| `DOC_API_BASE_URL` | 문서 DB REST API 베이스 URL |
| `DOC_API_KEY` | 문서 DB API 인증 키 |
| `DB_CONNECTION_STRING` | SQL 실행용 DB 연결 문자열 |
