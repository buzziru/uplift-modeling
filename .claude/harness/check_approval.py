import json
import re
import sys

ASK = re.compile(
    r"정해 주실 것|정해 주세요|골라 주세요|승인해 주세요|할까요\?"
    r"|^#+ *승인 요청|^\*\*승인 요청|^승인 요청 *:",
    re.MULTILINE,
)
PRIOR = "확인한 앞 결정"
QUOTED = re.compile(r"```.*?```|`[^`\n]*`|^>.*$|\"[^\"\n]*\"|“[^”\n]*”", re.DOTALL | re.MULTILINE)
REASON = (
    "승인 요청 검사(.claude/harness/check_approval.py): 사용자에게 결정을 요청하는 부분에 "
    f'"{PRIOR}" 줄이 없다. 질문마다 SPEC.md, PENDING-DECISIONS.md, docs/ 기록 문서, '
    "이 대화의 앞 결정과 대조한다. 앞 결정이나 그 의도로 닫히면 질문을 거두고 "
    '"메인이 정함: <정한 내용>, 근거: <위치>" 한 줄로 바꾼다(CLAUDE.md 승인 지점 절). '
    f'닫히지 않으면 질문에 "{PRIOR}: <위치>, 닫히지 않는 이유: <한 줄>"을 붙인다. '
    "그다음 답변을 다시 쓴다."
)


def needs_review(message: str) -> bool:
    text = QUOTED.sub("", message)
    return bool(ASK.search(text)) and PRIOR not in message


def main() -> None:
    data = json.load(sys.stdin)
    if data.get("stop_hook_active"):
        return
    if needs_review(data.get("last_assistant_message") or ""):
        print(json.dumps({"decision": "block", "reason": REASON}, ensure_ascii=False))


if __name__ == "__main__":
    main()
