import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def load_fixture():
    def _load(name: str):
        with open(FIXTURES_DIR / name) as f:
            return json.load(f)
    return _load


@pytest.fixture
def tmp_run_dir(tmp_path):
    run_dir = tmp_path / "run"
    (run_dir / "raw").mkdir(parents=True)
    (run_dir / "norm").mkdir()
    (run_dir / "decoded").mkdir()
    return run_dir
