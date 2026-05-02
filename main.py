import argparse
import uuid
from langgraph.types import Command
from graph.workflow import build_graph
from graph.state import VocState
from pathlib import Path

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

def draw_graph(graph, output: str = None) -> None:
    if output and output.endswith(".png"):
        png_bytes = graph.get_graph().draw_mermaid_png()
        Path(output).write_bytes(png_bytes)
        print(f"그래프 이미지 저장: {output}")
    else:
        print(graph.get_graph().draw_mermaid())
        if output:
            Path(output).write_text(graph.get_graph().draw_mermaid(), encoding="utf-8")
            print(f"Mermaid 다이어그램 저장: {output}")

def run_voc(graph, voc_text: str) -> None:
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

def interactive_mode(graph) -> None:
    print("VOC 에이전트 대화형 모드 (종료: 'exit' 또는 Ctrl+C)")
    while True:
        try:
            voc = input("\n사용자 VOC 입력: ").strip()
            if voc.lower() == "exit":
                break
            if voc:
                run_voc(graph, voc)
        except KeyboardInterrupt:
            print("\n종료합니다.")
            break

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VOC 에이전트")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--input", "-i", type=str, help="처리할 VOC 텍스트 (없으면 대화형 모드)")
    group.add_argument("--interactive", action="store_true", help="대화형 모드")
    group.add_argument("--draw", nargs="?", const="", metavar="OUTPUT",
                       help="그래프 시각화. 경로 미지정 시 콘솔 출력, .png 확장자면 이미지로 저장, 그 외 경로면 Mermaid 텍스트로 저장")
    args = parser.parse_args()

    graph = build_graph()

    if args.draw is not None:
        draw_graph(graph, args.draw or None)
    elif args.input:
        run_voc(graph, args.input)
    else:
        interactive_mode(graph)
