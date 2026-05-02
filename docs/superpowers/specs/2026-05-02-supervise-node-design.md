# supervise_node 도입 설계 문서

**작성일:** 2026-05-02  
**상태:** 승인됨  
**관련 문서:** `2026-05-01-voc-agent-design.md` (기존 설계)

---

## 1. 변경 배경

기존 설계에서는 `route_after_classify` 엣지 함수가 `SIMPLE` 유형일 때 `retrieve` 를 건너뛰고 `agent`로 직접 라우팅했다. 이 방식은 분류 결과만으로 라우팅을 결정하므로, 문서가 있어도 불필요한 답변이 생성되거나 사용자에게 추가 질문이 필요한 경우를 처리할 수 없었다.

`supervise_node`를 도입해 LLM이 **현재 State를 보고 다음 행동을 스스로 판단**하도록 변경한다.

---

## 2. 새 그래프 흐름

```
CLI 입력
    ↓
[classify_node]  — voc_type 분류
    ↓
[supervise_node] — LLM이 현재 State로 행동 결정
    ├── "answer"   → [agent_node] → 출력
    ├── "retrieve" → [retrieve_node] → [supervise_node] (재판단)
    └── "end"      → (retrieve 실패 시) 종료
```

- `classify → supervise`: 무조건 direct edge
- `supervise → agent | retrieve | END`: `supervise_action` 필드 기반 조건부 엣지
- `retrieve → supervise`: 항상 복귀 (사이클)

---

## 3. supervise_node 역할

| 책임 | 설명 |
|------|------|
| 행동 판단 | LLM이 `SuperviseDecision` 구조화 출력으로 결정 |
| 사용자 추가 질문 | `action=="ask"` 시 `interrupt(question)`으로 사용자 답변 수집 → conversation_history 누적 → 재판단 |
| 에러 처리 | `status=="error"` 시 LLM 호출 없이 즉시 `"end"` 반환 |

**구조화 출력 스키마**
```python
class SuperviseDecision(BaseModel):
    action: Literal["answer", "retrieve", "ask"]
    question: str | None = None  # action=="ask"일 때만 사용
```

**노드 내부 루프 (의사코드)**
```
if status == "error" → return {"supervise_action": "end"}

loop:
  decision = LLM.with_structured_output(SuperviseDecision).invoke(SUPERVISE_PROMPT)
  if action == "answer"   → return {"supervise_action": "answer"}
  if action == "retrieve" → return {"supervise_action": "retrieve"}
  if action == "ask"      → interrupt(question) → 답변 수집 → history 추가 → loop 반복
```

---

## 4. agent_node 변경

기존 agent_node의 clarification 판단 + interrupt 로직을 **완전 제거**한다.  
supervise_node가 conversation_history를 완성한 상태로 넘겨주므로, agent_node는 **Tool 호출 + 최종 답변 생성만** 담당한다.

---

## 5. VocState 변경

기존 필드에 아래 1개 추가:

```python
supervise_action: str  # "" | "answer" | "retrieve" | "end"
```

---

## 6. edges.py 변경

| 함수 | 변경 |
|------|------|
| `route_after_classify` | **삭제** |
| `route_after_supervise` | **신규**: `supervise_action` 읽어 "agent" / "retrieve" / END 반환 |
| `route_after_retrieve` | **변경**: 항상 `"supervise"` 반환 (에러 여부 무관) |

---

## 7. prompts/templates.py 변경

| 항목 | 변경 |
|------|------|
| `NEEDS_CLARIFICATION_PROMPT` | **삭제** (supervise_node로 이동) |
| `SUPERVISE_PROMPT` | **신규**: voc_type, voc_text, docs_context, conversation_history를 입력받아 행동 결정 |

---

## 8. 디렉토리 구조 (변경 파일만)

```
graph/
├── state.py      — supervise_action 필드 추가
├── nodes.py      — supervise_node 추가, agent_node 단순화
├── edges.py      — route_after_supervise 추가, 기존 함수 수정/삭제
└── workflow.py   — 노드/엣지 재조립
prompts/
└── templates.py  — SUPERVISE_PROMPT 추가, NEEDS_CLARIFICATION_PROMPT 삭제
```
