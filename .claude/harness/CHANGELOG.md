# 하네스 변경 이력

> 하네스 변경만 적는다. 칸 형식: solo-harness `docs/formats.md` 4절. 칸 안에 `|`를 쓰지 않는다.

| 날짜 | 종류 | 유형 | 대상 | 변경 | 사유 | 장치 | 근거 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-11-22 | 쌓임 | workflow | CLAUDE.md | 첫 구축 | 하네스 구축 | 장치 없음: 첫 구축 | build |
| 2026-11-22 | 쌓임 | workflow | `.claude/agents/pr-reviewer.md`, CLAUDE.md | PR 전 검토 에이전트와 절차 추가 | 모든 작업의 PR 전 검토를 작성 맥락과 분리된 에이전트로 한다 | 장치 없음: 에이전트 정의와 CLAUDE.md 절차 | 요청: 2026-11-22 |
| 2026-11-22 | 보완 | quality | `.claude/settings.json`, `.claude/rubrics/analysis.md`, CLAUDE.md | 거부 규칙 빈틈 보완, 루브릭을 파일로 판정 가능하게 고치고 R6·R7 추가, PR 전 검토 순서와 상한 처리 명시 | PR 전 검토 1라운드 지적 | 장치 없음: 거부 규칙과 문서 수정 | 요청: 2026-11-22 |
| 2026-11-22 | 보완 | quality | `.claude/settings.json`, `.claude/rubrics/analysis.md`, CLAUDE.md | 데이터 삭제는 인자에 data가 든 명령 전체로 넓히고, gh api는 PATCH만 막고, .env는 .env.example을 읽을 수 있게 다시 씀, R2 기록 위치와 R7 그림 값 정의, R6 실패 판정, 추가 평가 뒤 검토 처리 | PR 전 검토 2라운드 should | 장치 없음: 거부 규칙과 문서 수정 | 요청: 2026-11-22 |
| 2026-11-22 | 보완 | workflow | CLAUDE.md, `.claude/rubrics/analysis.md` | 되돌리기 어려운 대상은 대상 쪽에서 지키는 원칙, 평가·검토 공통 종료 규칙(평가 상한은 run-evaluation 멈춤 절), 정본은 가리키기만 하는 원칙 추가. 루브릭 항목마다 근거 위치 줄을 두고 아직 없는 경로에 기댄 R2 조건을 뺌 | PR 전 검토 세 라운드에서 거부 규칙 변형, 판정 근거 누락, 종료 분기 누락, 정본 요약 누락이 되풀이됨 | GitHub branch protection(main) | 요청: 2026-11-22 |
| 2026-11-22 | 보완 | workflow | CLAUDE.md, `.claude/agents/pr-reviewer.md` | 수정 전 같은 대상의 정본 확인과 바뀌기 전 표현 검색, 2라운드 반복 시 공통 원인 보고를 CLAUDE.md에 추가. pr-reviewer에 diff 밖 잔존 표현과 정본 충돌을 늘 보는 항목으로 추가 | 남은 검토 지적이 바꾼 표현의 다른 사본과 같은 대상의 정본을 확인하지 않아 생김. 사용자가 2라운드 반복 시 원인 보고를 지시 | 장치 없음: CLAUDE.md 절차와 에이전트 정의 | 요청: 2026-11-22 |
| 2026-11-22 | 보완 | workflow | CLAUDE.md, `.claude/agents/pr-reviewer.md` | 이미 정의된 용어는 정의를 가리키고 다시 나열하지 않는 규칙 추가, pr-reviewer에 새 문장의 용어 범위 확인 추가 | 전파 규칙 검토 두 라운드의 지적 여섯 건이 모두 기존 정의를 새 문장에서 다시 서술해 생김 | 장치 없음: CLAUDE.md 절차와 에이전트 정의 | 요청: 2026-11-22 |
| 2026-11-23 | 보완 | workflow | `.claude/agents/pr-reviewer.md` | CLAUDE.md 규칙을 다시 적은 줄을 지우고 템플릿 형식으로 맞춤. 늘 보는 항목에 범위, 남은 사용자 판단, 거부 규칙 꼴 빈틈 비지적을 들임 | 서브에이전트 맥락에 프로젝트 CLAUDE.md가 들어가므로 정의 안의 사본은 어긋날 자리만 만듦 | 장치 없음: 에이전트 정의 | 요청: 2026-11-23 |
| 2026-11-23 | 보완 | workflow | `.claude/skills/run-evaluation/SKILL.md`, CLAUDE.md | run-evaluation에 PR 전 검토 부르기, 평가·검토 순서, 검토 상한 2와 그 뒤 should 처리, 상한에서 묻기, 원인 종합 보고를 들이고 CLAUDE.md 하네스 절의 해당 줄 다섯을 평가·검토 한 줄로 바꿈 | 같은 절차가 하네스 절과 스킬에 나뉘어 있어 한쪽만 고치면 어긋남 | 장치 없음: 스킬과 CLAUDE.md 절차 | 요청: 2026-11-23 |
