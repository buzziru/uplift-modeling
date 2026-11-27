import importlib.util
import json
import sys
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "run_checks", Path(__file__).resolve().parents[1] / "scripts" / "run_checks.py"
)
if SPEC is None or SPEC.loader is None:
    raise ImportError("scripts/run_checks.py를 불러오지 못했다")
run_checks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run_checks)

PYTHON = Path(sys.executable).as_posix()
PASS = f'{PYTHON} -c "print(1)"'
FAIL = f"{PYTHON} -c \"import sys; print('broken'); sys.exit(3)\""


@pytest.fixture
def run_config(tmp_path, capsys):
    def run(commands):
        config = tmp_path / "config.json"
        config.write_text(json.dumps({"check": commands}), encoding="utf-8")
        code = run_checks.main(config)
        return code, capsys.readouterr().out

    return run


@pytest.mark.parametrize(("commands", "code"), [([PASS, PASS], 0), ([PASS, FAIL], 1)])
def test_main_exits_nonzero_when_any_check_fails(run_config, commands, code):
    assert run_config(commands)[0] == code


def test_main_prints_only_failed_check_output(run_config):
    _, out = run_config([PASS, FAIL])
    assert out.splitlines() == [f"$ {FAIL} (exit 3)", "broken", "1/2 passed"]
