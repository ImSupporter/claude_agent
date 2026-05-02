# VOC Agent

사용자가 시스템에 남긴 VOC(불만사항 / 사용법 문의 / 요청사항 / 데이터 수정)를 자동으로 분류하고, 외부 문서 DB와 내부 데이터베이스를 조회하여 조치 및 답변을 생성하는 **LangGraph 기반 CLI 에이전트**입니다.

## 주요 기능

- **자동 분류**: Claude를 활용해 VOC를 5가지 유형으로 분류
- **문서 검색**: 분류 결과에 따라 외부 문서 DB REST API에서 관련 문서 자동 조회
- **멀티턴 대화**: 처리에 추가 정보가 필요한 경우 사용자에게 질문 후 답변 생성 (interrupt 기반)
- **DB 도구 통합**: 데이터 조회(SELECT) 및 수정(DML) SQL 도구를 에이전트가 직접 호출
- **그래프 시각화**: LangGraph 워크플로우를 Mermaid 다이어그램 또는 PNG로 출력

## 아키텍처

```
CLI 입력 (VOC 텍스트)
  → classify 노드  : VOC 유형 분류
  → retrieve 노드  : 관련 문서 조회 (SIMPLE 유형 제외)
  → agent 노드     : 멀티턴 추가 질의 + Tool use + 최종 답변 생성
  → CLI 출력
```

### 워크플로우 (`graph/`)

| 파일 | 역할 |
|------|------|
| `state.py` | `VocState` TypedDict — 노드 간 공유 상태 정의 |
| `nodes.py` | `classify_node`, `retrieve_node`, `agent_node` 구현 |
| `edges.py` | 분류 결과 및 조회 상태에 따른 조건부 라우팅 |
| `workflow.py` | `StateGraph` 조립 및 컴파일 |

### VOC 분류 체계

| 유형 | 설명 | 처리 방향 |
|------|------|-----------|
| `COMPLAINT` | 불만사항, 오류 신고 | 문서 조회 → 에이전트 답변 |
| `INQUIRY` | 사용법 문의 | 문서 조회 → 에이전트 답변 |
| `REQUEST` | 기능 요청, 개선 제안 | 문서 조회 → 에이전트 답변 |
| `DATA_MODIFICATION` | 데이터 수정 요청 | 문서 조회 → DB Tool 호출 → 에이전트 답변 |
| `SIMPLE` | 간단한 인사 / 단순 질문 | 문서 조회 생략 → 에이전트 직접 답변 |

## 설치 및 실행

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 열어 아래 항목을 입력합니다.

| 변수 | 필수 | 설명 |
|------|------|------|
| `ANTHROPIC_API_KEY` | ✅ | Anthropic API 키 |
| `DOC_API_BASE_URL` | ✅ | 문서 DB REST API 베이스 URL |
| `DB_CONNECTION_STRING` | ✅ | SQLAlchemy DB 연결 문자열 |
| `DOC_API_KEY` | | 문서 DB API 인증 키 (Bearer 토큰) |
| `MODEL_NAME` | | 사용할 Claude 모델 (기본값: `claude-sonnet-4-6`) |

### 3. 실행

```bash
# 대화형 모드 (기본)
python main.py

# 단일 VOC 처리
python main.py --input "결제 버튼이 눌리지 않아요"
python main.py -i "환불 신청은 어떻게 하나요?"

# 워크플로우 그래프 시각화
python main.py --draw                  # Mermaid 다이어그램을 콘솔에 출력
python main.py --draw graph.md         # Mermaid 텍스트 파일로 저장
python main.py --draw graph.png        # PNG 이미지로 저장 (pillow 필요)
```

## 디렉토리 구조

```
voc_agent/
├── main.py              # CLI 진입점 (argparse)
├── config.py            # 환경변수 및 설정 (pydantic-settings)
├── requirements.txt
├── .env.example
├── graph/
│   ├── workflow.py      # StateGraph 정의 및 컴파일
│   ├── nodes.py         # 노드 함수들
│   ├── edges.py         # 조건부 엣지 함수들
│   └── state.py         # VocState 스키마
├── tools/
│   └── doc_retriever.py # 문서 DB REST API 클라이언트
└── prompts/
    └── templates.py     # LangChain ChatPromptTemplate 모음
```

## 주요 의존성

| 패키지 | 용도 |
|--------|------|
| `langgraph` | 상태 기반 워크플로우 |
| `langchain-anthropic` | Claude LLM 연동 |
| `langchain-core` | PromptTemplate, RunnableSequence |
| `httpx` | 문서 DB REST API 호출 |
| `sqlalchemy` | DB Tool (SELECT / DML) |
| `pydantic-settings` | 환경변수 관리 |
| `python-dotenv` | .env 파일 로딩 |
