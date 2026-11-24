---
name: kaggle-remote-runner
description: 로컬에서 개발한 실험의 본학습, HPO, GPU 실행을 Kaggle kernel에 올려 돌리고 출력을 받아 DuckDB에 실행으로 기록하는 절차. 실험을 Kaggle에서 돌릴지 정할 때, 학습 세트 dataset을 올리거나 버전을 낼 때, kernel을 push하고 상태·로그를 보고 출력을 받을 때 쓴다. Kaggle CLI 명령의 옵션은 Kaggle/kaggle-cli 저장소 `skills/`를 참고했다.
---

# Kaggle 원격 실행

로컬이 개발 환경이고 Kaggle은 실행기다. 무엇을 어디서 돌리는지는 `docs/ENGINEERING.md` "본학습, HPO, GPU 실행은 Kaggle kernel에서 하고 나머지는 로컬에서 한다" 절이 정본이다. Kaggle 실행도 실험 하나의 실행이므로 `experiments/TEMPLATE.md` 양식을 그대로 따른다.

## 지키는 것

올리는 데이터와 돌리는 커밋의 범위는 위 ENGINEERING.md 절을 따른다. 그 결정에서 나오는 실행 규칙은 다음과 같다.

- kernel을 push하기 전에, GitHub에 푸시한 커밋에 `experiment.md`의 질문과 설계 절이 있는지 본다. 없으면 kernel을 push하지 않는다. kernel이 푸시한 커밋에서만 돌므로, 이 확인 하나로 설계 절이 결과보다 먼저 커밋된다.
- dataset 폴더에 시험 세트 파일이 있으면 올리지 않는다.
- dataset과 kernel은 비공개로 둔다. 공개(`datasets create -u`, `"is_private": "false"`)는 공개 배포라 사용자에게 묻는다. `delete` 명령도 묻는다.
- 실패한 실행을 같은 코드로 다시 push하지 않는다. 로그로 원인을 찾고 로컬에서 작은 표본으로 재현해 고친 뒤 push한다.

## 준비(한 번)

1. CLI 설치: `uv tool install kaggle --with six`. Kaggle CLI 2.2.5는 `six` 의존성이 빠져 있어 함께 넣는다.
2. 인증: Kaggle에서 API 토큰을 만들어 Doppler 프로젝트 `uplift-modeling`(config `dev`)에 `KAGGLE_API_TOKEN`과 `KAGGLE_USERNAME`으로 넣는다. 토큰을 파일(`~/.kaggle/`)이나 저장소에 두지 않는다. 사용자가 할 일이다.
3. 명령은 모두 Doppler로 감싸 돌린다. 아래에서 `K`는 `doppler run -p uplift-modeling -c dev -- kaggle`을 줄인 것이다.
4. 확인: `K quota`가 GPU 남은 시간을 보이면 된다.

옵션이 헷갈리면 `K <group> <command> --help`로 설치된 CLI를 본다.

## 학습 세트 dataset

작업 폴더는 `data/kaggle/dataset/`다(`data/`는 커밋하지 않는다).

1. 처음: `K datasets init -p data/kaggle/dataset`로 `dataset-metadata.json`을 만들고 `id`를 `<KAGGLE_USERNAME>/uplift-hillstrom-train`으로, `title`을 기본값에서 `uplift-hillstrom-train`으로 고친다. DuckDB에서 학습 세트와 fold 배정을 Parquet로 내보내 같은 폴더에 둔다.
2. 올리기: `K datasets create -p data/kaggle/dataset -t -q`. `-t`는 Parquet를 CSV로 바꾸지 않게 한다. `-u`를 붙이지 않는다.
3. 분할이나 fold가 바뀌면 `K datasets version -p data/kaggle/dataset -t -q -m "<분할 시드, 행 수, 커밋>"`.
4. `K datasets status <id>`가 ready인지 본 뒤 kernel을 push한다.

## kernel 실행

작업 폴더는 `data/kaggle/<EXP-ID>/`다. 두 파일을 둔다.

`kernel-metadata.json`:

```json
{
  "id": "<KAGGLE_USERNAME>/<exp-id-소문자>",
  "title": "<exp-id-소문자>",
  "code_file": "entry.py",
  "language": "python",
  "kernel_type": "script",
  "is_private": "true",
  "enable_gpu": "<GPU가 필요하면 true>",
  "enable_internet": "true",
  "dataset_sources": ["<KAGGLE_USERNAME>/uplift-hillstrom-train"]
}
```

`title`과 `id`의 slug는 같아야 한다(제목을 소문자로 바꾸고 공백을 `-`로 바꾼 것이 slug다).

`entry.py`: 커밋을 받아 `uv.lock`대로 환경을 만들고 실험의 `run.py`를 돈다. Kaggle은 `/kaggle/working` 전체를 kernel 출력으로 저장하므로, 저장소와 가상환경은 그 밖(`/tmp/repo`)에 만들고 `/kaggle/working`에는 `run.py` 출력만 둔다. `uv`가 `.python-version`(3.12)을 맞추므로 Kaggle 이미지의 Python 버전에 기대지 않는다.

```python
import subprocess

SHA = "<푸시한 커밋>"
EXP = "<실험 폴더 이름>"
DATA = "/kaggle/input/uplift-hillstrom-train"


def sh(cmd: str) -> None:
    subprocess.run(cmd, shell=True, check=True)


sh("pip install -q uv")
sh(f"git clone -q https://github.com/buzziru/uplift-modeling.git /tmp/repo && git -C /tmp/repo checkout -q {SHA}")
sh(f"cd /tmp/repo && uv run --frozen python experiments/{EXP}/run.py --data {DATA} --out /kaggle/working")
```

`run.py`가 `--data`, `--out`을 받아 설정, 지표, 예측을 출력 폴더에 쓰는 형식과, 받아 온 출력을 DuckDB에 실행으로 적는 스크립트는 첫 Kaggle 실험(M2)에서 만들고 `docs/ENGINEERING.md`에 적는다.

순서:

1. 커밋을 푸시하고 `entry.py`의 `SHA`에 넣는다.
2. GPU 실행이면 `K quota`로 남은 시간이 `--timeout`보다 큰지 본다. 모자라면 push하지 않고 보고한다.
3. `K kernels push -p data/kaggle/<EXP-ID> -t <초> [--accelerator NvidiaTeslaT4]`. 출력에 찍힌 kernel 버전을 적어 둔다.
4. `K kernels status <id>`를 몇 분 간격으로 본다. 로그는 `K kernels logs <id>`로 보고, 계속 볼 때는 `--follow --interval 30` 이상으로 둔다.
5. 끝나면 `K kernels output <id>/<버전> -p data/kaggle/<EXP-ID>/output/v<버전>`로 받는다.
6. 받은 출력을 `docs/ENGINEERING.md`의 Kaggle 실행 절과 "분석 데이터와 실험 기록은 DuckDB 파일 하나에 두고 이것을 정본으로 한다" 절대로 기록한다.
