---
name: kaggle-remote-runner
description: 로컬에서 개발한 실험의 본학습, HPO, GPU 실행을 Kaggle kernel에 올려 돌리고 출력을 받아 DuckDB에 실행으로 기록하는 절차. 실험을 Kaggle에서 돌릴지 정할 때, 학습 세트 dataset을 올리거나 버전을 낼 때, scripts/kaggle.py로 kernel을 push하고 상태를 보고 출력을 합칠 때 쓴다. Kaggle CLI 명령의 옵션은 Kaggle/kaggle-cli 저장소 `skills/`를 참고했다.
---

# Kaggle 원격 실행

로컬이 개발 환경이고 Kaggle은 실행기다. Kaggle 실행도 실험 하나의 실행이므로 `experiments/TEMPLATE.md` 양식을 그대로 따른다. Kaggle 실행은 `scripts/kaggle.py`가 맡는다. 하위 명령이 무엇을 확인하고 어디에 쓰는지는 그 파일과 `src/uplift/kaggle_jobs.py`가, kernel 안에서 도는 `run.py compute`의 옵션은 `experiments/CLAUDE.md`가 정본이다. 이 스킬은 순서와 스크립트가 막지 않는 것만 적는다.

## 어디서 돌리나

- 로컬: 작은 실험과 디버깅, EDA, 데이터 검증, feature engineering, 모델 평가와 분석. 시험 세트 평가도 로컬에서 한다.
- Kaggle: 모델의 본학습과 HPO는 모두 Kaggle kernel에서 돌린다. 기본은 CPU kernel이고, LightGBM이 여기에 든다. XGBoost, CatBoost처럼 GPU로 학습 시간이 줄어드는 모델만 GPU kernel을 쓴다.
- Kaggle에는 학습 세트와 `folds`만 비공개 dataset으로 올리고 시험 세트는 올리지 않는다. 원격 HPO가 시험 세트를 읽을 수 없게 하기 위해서다.

## 준비(한 번)

1. 인증: Kaggle에서 API 토큰을 만들어 Doppler 프로젝트 `uplift-modeling`(config `dev`)에 `KAGGLE_API_TOKEN`과 `KAGGLE_USERNAME`으로 넣는다. 토큰을 파일(`~/.kaggle/`)이나 저장소에 두지 않는다. 사용자가 할 일이다.
2. CLI는 따로 설치하지 않는다. `scripts/kaggle.py`가 Doppler로 감싼 `uvx --with six kaggle`을 부른다. Kaggle CLI 2.2.5는 `six` 의존성이 빠져 있어 함께 넣는다.
3. CLI를 직접 부를 때(로그, quota, `--help`)는 `doppler run -p uplift-modeling -c dev -- uvx --with six kaggle`로 감싼다. 아래에서 `K`는 이것을 줄인 것이다.

## 순서

1. dataset: 처음이면 `uv run python scripts/kaggle.py dataset`, 분할이나 fold가 바뀌었으면 `uv run python scripts/kaggle.py dataset --version-message "<분할 시드, 행 수, 커밋>"`.
2. 실험 커밋을 origin에 push한다. kernel은 push한 커밋을 받아 돈다.
3. `uv run python scripts/kaggle.py push <실험 폴더 이름> [--part <이름>] [--args "<compute 옵션>"]`. `--part`는 여러 번 줄 수 있고, 줄 때마다 kernel이 하나씩 생긴다.
4. `uv run python scripts/kaggle.py watch`로 모든 작업이 끝날 때까지 상태를 본다. 동시 CPU 세션 상한에 걸려 queued로 남은 kernel은 watch가 자리가 날 때 push한다. 로그는 `K kernels logs <USER>/<slug>`로 본다.
5. `uv run python scripts/kaggle.py pull`로 끝난 kernel의 출력을 받아 메인 DuckDB에 합친다. 출력에 찍힌 `run_id`로 `run.py export`를 돈다.

## 지키는 것

스크립트가 막지 않는 것이다.

- dataset과 kernel은 비공개로 둔다. 공개(`datasets create -u`, `"is_private": "false"`)는 공개 배포라 사용자에게 묻는다. `delete` 명령도 묻는다.
- 실패한 실행을 같은 코드로 다시 push하지 않는다. 로그로 원인을 찾고 로컬에서 `run.py smoke`로 재현해 고친 뒤 push한다.
- `scripts/kaggle.py`는 CPU kernel만 만든다. GPU kernel을 쓸 모델이 생기면 그 작업에서 스크립트에 GPU 설정(`enable_gpu`, push의 `--accelerator NvidiaTeslaT4`)과 push 전 `K quota` 확인을 더한다. 모델 라이브러리마다 첫 GPU 실행에서는 로그로 GPU가 실제로 쓰였는지(라이브러리가 장치를 잡았다는 출력, `nvidia-smi`) 확인하고, 안 쓰였으면 CPU kernel과 같은 시간을 GPU 한도로 쓰는 셈이라 멈추고 보고한다.

옵션이 헷갈리면 `uv run python scripts/kaggle.py <하위 명령> --help`와 `K <group> <command> --help`로 본다.
