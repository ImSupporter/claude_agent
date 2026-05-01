# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

사용자가 시스템에 남긴 VOC(불편사항 / 사용법 문의 / 요청사항)를 분류하고, 외부 문서 DB REST API를 조회해 자동으로 조치 및 답변을 생성하는 LangGraph 기반 CLI 에이전트.

## 실행 방법

```bash
# 의존성 설치
pip install -r requirements.txt

# 에이전트 실행 (단일 VOC 입력)
python main.py --input "결제 버튼이 눌리지 않아요"

# 대화형 모드
python main.py --interactive

# 환경변수 설정
cp .env.example .env
# .env에 ANTHROPIC_API_KEY, DOC_API_BASE_URL 등 입력
```

## 아키텍처

### 전체 흐름

```
CLI 입력 (VOC 텍스트)
  → VocState 초기화
  → [분류 노드] 불편사항 / 사용법 문의 / 요청사항 판별
  → [문서 검색 노드] 외부 문서 DB REST API 호출
  → [답변 생성 노드] LangChain + Claude로 조치/답변 생성
  → CLI 출력
```

### LangGraph Workflow (`graph/`)

- **`state.py`** — `VocState` TypedDict 정의. 노드 간 공유되는 전체 상태 (입력 VOC, 분류 결과, 검색된 문서, 최종 답변, 처리 상태 등).
- **`nodes.py`** — 각 처리 단계를 함수로 구현. `classify_node`, `retrieve_docs_node`, `generate_response_node` 등. 각 노드는 `VocState`를 받아 업데이트된 `VocState`를 반환.
- **`edges.py`** — 조건부 라우팅 로직. 분류 결과에 따라 다음 노드를 결정하는 함수들.
- **`workflow.py`** — `StateGraph` 조립. 노드 등록, 엣지 연결, 그래프 컴파일.

### 문서 검색 (`tools/`)

- **`doc_retriever.py`** — 외부 문서 DB REST API 클라이언트. `query_documents(query: str) -> list[Document]` 형태로 래핑. httpx 또는 requests 사용.

### 설정 (`config.py`)

환경변수 로딩 (python-dotenv). `ANTHROPIC_API_KEY`, `DOC_API_BASE_URL`, `DOC_API_KEY` 등.

## 디렉토리 구조

```
voc_agent/
├── main.py              # CLI 진입점 (argparse)
├── graph/
│   ├── workflow.py      # StateGraph 정의 및 컴파일
│   ├── nodes.py         # 노드 함수들
│   ├── edges.py         # 조건부 엣지 함수들
│   └── state.py         # VocState 스키마
├── tools/
│   └── doc_retriever.py # 문서 DB REST API 클라이언트
├── prompts/
│   └── templates.py     # LangChain PromptTemplate 모음
├── config.py            # 환경변수 및 설정
├── requirements.txt
└── .env.example
```

## 주요 의존성

| 패키지 | 용도 |
|--------|------|
| `langgraph` | 상태 기반 워크플로우 |
| `langchain-anthropic` | Claude LLM 연동 |
| `langchain-core` | PromptTemplate, RunnableSequence |
| `httpx` | 문서 DB REST API 호출 |
| `python-dotenv` | 환경변수 로딩 |

## VOC 분류 체계

| 유형 | 설명 | 처리 방향 |
|------|------|-----------|
| `COMPLAINT` | 불편사항, 오류 신고 | 오류 원인 파악 + 조치 안내 |
| `INQUIRY` | 사용법 문의 | 관련 문서 검색 + 설명 생성 |
| `REQUEST` | 기능 요청, 개선 제안 | 접수 확인 + 유사 기능 안내 |

## 상태(VocState) 핵심 필드

```python
class VocState(TypedDict):
    raw_input: str           # 원본 VOC 텍스트
    voc_type: str            # COMPLAINT | INQUIRY | REQUEST
    retrieved_docs: list     # 문서 DB에서 조회된 문서 목록
    response: str            # 최종 생성 답변
    status: str              # processing | done | error
```
