from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from bsl_mcp.config import Settings
from bsl_mcp.service import CheckService

FAKE = Path(__file__).with_name("fake_analyzer.py")


@pytest.fixture
def roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


def service_with_fake(root: Path, **overrides: object) -> CheckService:
    settings = Settings(
        java=sys.executable,
        jar=None,
        timeout_seconds=float(overrides.pop("timeout_seconds", 5)),
        allowed_roots=(root,),
        max_code_bytes=int(overrides.pop("max_code_bytes", 1000)),
        max_file_bytes=int(overrides.pop("max_file_bytes", 1000)),
        max_files=int(overrides.pop("max_files", 10)),
        max_concurrent=int(overrides.pop("max_concurrent", 2)),
        fail_on=str(overrides.pop("fail_on", "syntax")),
        command_prefix=(sys.executable, str(FAKE)),
    )
    return CheckService(settings)


def write_module(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
