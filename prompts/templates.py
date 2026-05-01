from langchain_core.prompts import ChatPromptTemplate

CLASSIFY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 고객 VOC를 분류하는 전문가입니다.
다음 VOC를 아래 4가지 유형 중 하나로 분류하세요.
반드시 유형 이름만 한 단어로 답변하세요.

유형:
- COMPLAINT: 불편사항, 오류 신고, 데이터 이상 문의
- INQUIRY: 사용법 문의, 기능 설명 요청
- REQUEST: 기능 추가 요청, 개선 제안
- DATA_MODIFICATION: 데이터 수정/변경 요청"""),
    ("human", "VOC: {voc_text}"),
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
- 데이터 조회/수정이 필요하면 제공된 도구를 사용하세요.
- 추가 정보가 필요하면 사용자에게 구체적으로 질문하세요."""

NEEDS_CLARIFICATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """고객의 VOC와 참고 문서를 검토하세요.
정확한 답변을 위해 추가 정보(예: 사용자 ID, 주문 번호 등)가 반드시 필요하면
질문 내용을 한 문장으로 답변하세요.
추가 정보 없이도 답변 가능하면 "NO"라고만 답변하세요."""),
    ("human", "VOC: {voc_text}\n\n참고 문서 요약: {docs_summary}"),
])
