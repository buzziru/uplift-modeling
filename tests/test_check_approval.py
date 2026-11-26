import importlib.util
import io
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "check_approval",
    Path(__file__).resolve().parents[1] / ".claude" / "harness" / "check_approval.py",
)
if SPEC is None or SPEC.loader is None:
    raise ImportError("check_approval.py를 불러오지 못했다")
check_approval = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_approval)


@pytest.mark.parametrize(
    "message",
    [
        "## 정해 주실 것\n1. 반응 모델의 정의",
        "무작위 타겟팅 기준을 정해 주세요.",
        "두 안 가운데 하나를 골라 주세요.",
        "이대로 진행할까요?",
        "### 승인 요청\n- 반응 모델: visit 기준",
        "**승인 요청**: 시험 세트 사용",
        "**승인 요청:** 시험 세트 사용",
        "승인 요청: 공개 배포",
        "진행할까요?\n`확인한 앞 결정` 줄을 쓴다.",
    ],
)
def test_needs_review_flags_request(message):
    assert check_approval.needs_review(message)


def test_needs_review_passes_request_with_prior_decision():
    message = (
        "## 정해 주실 것\n- 시험 세트 사용\n  확인한 앞 결정: `.claude/rules/approvals.md`, "
        "닫히지 않는 이유: 시험 세트 사용은 승인 지점이다"
    )
    assert not check_approval.needs_review(message)


@pytest.mark.parametrize(
    "message",
    [
        "승인 요청 Stop hook을 더했다.",
        "## 승인 요청 hook 추가\n본문",
        "**승인 요청 검사**를 더했다.",
        "`.claude/rules/approvals.md`의 승인 요청 문장을 고쳤다.",
        "반응 모델은 visit 기준으로 정했다.",
        "패턴 `정해 주세요`를 감지한다.",
        '"할까요?" 꼴은 감지한다.',
        "> 정해 주세요\n인용만 했다.",
        "```\n승인 요청: 예시\n```",
        "모든 검사를 통과했다.",
    ],
)
def test_needs_review_ignores_non_request(message):
    assert not check_approval.needs_review(message)


def run_main(monkeypatch, capsys, payload):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload, ensure_ascii=False)))
    check_approval.main()
    return capsys.readouterr().out


def test_main_blocks_once(monkeypatch, capsys):
    out = run_main(monkeypatch, capsys, {"last_assistant_message": "진행할까요?"})
    assert json.loads(out)["decision"] == "block"


def test_main_passes_when_stop_hook_active(monkeypatch, capsys):
    payload = {"stop_hook_active": True, "last_assistant_message": "진행할까요?"}
    assert run_main(monkeypatch, capsys, payload) == ""


def test_main_passes_missing_message(monkeypatch, capsys):
    assert run_main(monkeypatch, capsys, {"stop_hook_active": False}) == ""
