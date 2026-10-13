"""Подмена анализатора для модульных тестов. Это не проверка синтаксиса 1С."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


def _argument(name: str) -> str:
    args = sys.argv[1:]
    return args[args.index(name) + 1]


def main() -> int:
    mode = os.environ.get("FAKE_ANALYZER_MODE", "report")
    if mode == "sleep":
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        pid_file = os.environ.get("FAKE_CHILD_PID_FILE")
        if pid_file:
            Path(pid_file).write_text(str(child.pid), encoding="utf-8")
        time.sleep(60)
        return 0
    if mode == "crash":
        sys.stdout.write("fake analyzer failed\n")
        return 3
    output_dir = Path(_argument("--outputDir"))
    output_dir.mkdir(parents=True, exist_ok=True)
    if mode == "no-report":
        return 0
    if mode == "bad-json":
        (output_dir / "bsl-json.json").write_text("{", encoding="utf-8")
        return 0
    source_dir = Path(_argument("--srcDir"))
    fileinfos = []
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".bsl", ".os"}:
            continue
        text = path.read_text(encoding="utf-8")
        diagnostics = []
        if "СИНТАКСИС" in text:
            diagnostics.append(
                {
                    "code": "ParseError",
                    "message": "Ошибка разбора исходного кода",
                    "severity": "Error",
                    "source": "fake-analyzer",
                    "range": {
                        "start": {"line": 0, "character": 0},
                        "end": {"line": 0, "character": 1},
                    },
                }
            )
        relative = path.relative_to(source_dir).as_posix()
        fileinfos.append(
            {
                "path": f"file:///workspace/{relative}",
                "mdoRef": path.resolve().as_uri(),
                "diagnostics": diagnostics,
            }
        )
    report = {"date": "test", "fileinfos": fileinfos, "sourceDir": str(source_dir)}
    (output_dir / "bsl-json.json").write_text(
        json.dumps(report, ensure_ascii=False),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
