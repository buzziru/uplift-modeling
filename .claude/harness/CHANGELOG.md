# 하네스 변경 이력

> 하네스 변경만 적는다. 칸 형식: solo-harness `docs/formats.md` 4절. 칸 안에 `|`를 쓰지 않는다.

| 날짜 | 종류 | 유형 | 대상 | 변경 | 사유 | 장치 | 근거 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-11-22 | 쌓임 | workflow | CLAUDE.md | 첫 구축 | 하네스 구축 | 장치 없음: 첫 구축 | build |
| 2026-11-22 | 쌓임 | workflow | `.claude/agents/pr-reviewer.md`, CLAUDE.md | PR 전 검토 에이전트와 절차 추가 | 모든 작업의 PR 전 검토를 작성 맥락과 분리된 에이전트로 한다 | 장치 없음: 에이전트 정의와 CLAUDE.md 절차 | 요청: 2026-11-22 |
| 2026-11-22 | 보완 | quality | `.claude/settings.json`, `.claude/rubrics/analysis.md`, CLAUDE.md | 거부 규칙 빈틈 보완, 루브릭을 파일로 판정 가능하게 고치고 R6·R7 추가, PR 전 검토 순서와 상한 처리 명시 | PR 전 검토 1라운드 지적 | 장치 없음: 거부 규칙과 문서 수정 | 요청: 2026-11-22 |
| 2026-11-22 | 보완 | quality | `.claude/settings.json`, `.claude/rubrics/analysis.md`, CLAUDE.md | 데이터 삭제·공개 설정 변경·.env 거부 규칙을 빈틈과 과잉 차단 없게 다시 씀, R2 기록 위치와 R7 그림 값 정의, R6 실패 판정, 추가 평가 뒤 검토 처리 | PR 전 검토 2라운드 should | 장치 없음: 거부 규칙과 문서 수정 | 요청: 2026-11-22 |
