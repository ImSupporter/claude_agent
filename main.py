import argparse
import uuid
from langgraph.types import Command
from graph.workflow import build_graph
from graph.state import VocState

SEPARATOR = "━" * 40

VOC_TYPE_KO = {
    "COMPLAINT": "불편사항",
    "INQUIRY": "사용법 문의",
    "REQUEST": "요청사항",
    "DATA_MODIFICATION": "데이터 수정",
}

def format_output(state: dict) -> str:
    if state["status"] == "error":
        return f"\n{SEPARATOR}\n⚠️  {state['error_message']}\n{SEPARATOR}\n"
    voc_label = VOC_TYPE_KO.get(state["voc_type"], state["voc_type"])
    doc_titles = ", ".join(f"[{d['title']}]" for d in state["retrieved_docs"]) or "없음"
    return (
        f"\n{SEPARATOR}\n"
        f"VOC 유형   : {voc_label} ({state['voc_type']})\n"
        f"참고 문서  : {doc_titles}\n"
        f"{SEPARATOR}\n"
        f"{state['response']}\n"
        f"{SEPARATOR}\n"
    )

def _initial_state(voc_text: str) -> VocState:
    return {
        "raw_input": voc_text,
        "conversation_history": [],
        "voc_type": "",
        "retrieved_docs": [],
        "doc_retrieval_attempts": 0,
        "sql_results": [],
        "sql_tools_used": [],
        "response": "",
        "status": "processing",
        "error_message": None,
    }

def run_voc(voc_text: str) -> None:
    graph = build_graph()
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    result = graph.invoke(_initial_state(voc_text), config)

    while graph.get_state(config).next:
        interrupts = result.get("__interrupt__", [])
        if not interrupts:
            break
        question = interrupts[0].value
        print(f"\n에이전트: {question}")
        user_answer = input("사용자: ").strip()
        result = graph.invoke(Command(resume=user_answer), config)

    print(format_output(result))

def interactive_mode() -> None:
    print("VOC 에이전트 대화형 모드 (종료: 'exit' 또는 Ctrl+C)")
    while True:
        try:
            voc = input("\n사용자 VOC 입력: ").strip()
            if voc.lower() == "exit":
                break
            if voc:
                run_voc(voc)
        except KeyboardInterrupt:
            print("\n종료합니다.")
            break

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VOC 에이전트")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", "-i", type=str, help="처리할 VOC 텍스트")
    group.add_argument("--interactive", action="store_true", help="대화형 모드")
    args = parser.parse_args()

    if args.interactive:
        interactive_mode()
    else:
        run_voc(args.input)
