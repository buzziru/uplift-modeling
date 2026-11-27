import json
import re
import sys

ASK = re.compile(
    r"정해 주실 것|정해 주세요|골라 주세요|승인해 주세요|할까요\?"
    r"|^#+ *승인 요청 *$|^\*\*승인 요청 *:?\*\*|^승인 요청 *:",
    re.MULTILINE,
)
PRIOR = "확인한 앞 결정"
QUOTED = re.compile(
    r"```.*?```|`[^`\n]*`|^>.*$|\"[^\"\n]*\"|“[^”\n]*”", re.DOTALL | re.MULTILINE
)
REASON = (
    "승인 요청 검사(.claude/harness/check_approval.py): 사용자에게 결정을 요청했는데 "
    f'"{PRIOR}" 줄이 없다. 앞 답변은 사용자에게 이미 보였으므로 다시 쓰지 않고 '
    "짧은 보충만 쓴다. 질문마다 정본, 기록 문서, 이 대화의 앞 결정과 대조한다. "
    "앞 결정이나 그 의도로 닫히는 질문은 거두고, 어느 결정으로 닫혔는지와 처리를 "
    "한두 줄로 쓴 뒤 `.claude/rules/approvals.md`의 메인이 정하는 줄대로 처리한다. "
    "닫히지 않는 질문은 그 질문과 `.claude/rules/approvals.md`의 앞 결정 줄만 다시 쓴다."
)


def needs_review(message: str) -> bool:
    text = QUOTED.sub("", message)
    return bool(ASK.search(text)) and PRIOR not in text


def main() -> None:
    data = json.load(sys.stdin)
    if data.get("stop_hook_active"):
        return
    if needs_review(data.get("last_assistant_message") or ""):
        print(json.dumps({"decision": "block", "reason": REASON}, ensure_ascii=False))


if __name__ == "__main__":
    main()
