"""Запуск внешнего процесса без оболочки и с завершением всего дерева."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessResult:
    exit_code: int | None
    timed_out: bool
    stdout: str
    stderr: str


def _kill_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        except PermissionError:
            process.kill()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def run_command(argv: list[str], timeout_seconds: float, cwd: os.PathLike[str] | str) -> ProcessResult:
    """Запустить команду списком аргументов. По таймауту уничтожается всё дерево."""

    if not argv or any("\x00" in part for part in argv):
        raise ValueError("Пустая команда или нулевой символ в аргументе.")
    popen_kwargs: dict[str, object] = {
        "args": argv,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "stdin": subprocess.DEVNULL,
        "cwd": os.fspath(cwd),
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True
    try:
        process = subprocess.Popen(**popen_kwargs)
    except FileNotFoundError as error:
        raise FileNotFoundError(argv[0]) from error
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        _kill_process_tree(process)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            stdout, stderr = "", ""
        return ProcessResult(None, True, stdout or "", stderr or "")
    return ProcessResult(process.returncode, False, stdout or "", stderr or "")


def executable_exists(name: str) -> bool:
    if not name or "\x00" in name:
        return False
    if os.path.isabs(name) or os.sep in name:
        return os.path.isfile(name)
    return shutil.which(name) is not None
