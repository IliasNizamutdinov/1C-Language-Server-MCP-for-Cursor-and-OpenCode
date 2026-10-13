"""Скачивает официальную сборку BSL Language Server и проверяет контрольную сумму."""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

from bsl_mcp.constants import BSL_JAR_NAME, BSL_JAR_SHA256, BSL_JAR_URL, TESTED_BSL_VERSION


def download(destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    print(f"Загрузка BSL Language Server {TESTED_BSL_VERSION}")
    print(BSL_JAR_URL)
    urllib.request.urlretrieve(BSL_JAR_URL, temporary)
    digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
    if digest != BSL_JAR_SHA256:
        temporary.unlink(missing_ok=True)
        raise SystemExit(
            "Контрольная сумма не совпала с официальным релизом "
            f"{TESTED_BSL_VERSION}. Файл удалён.\n"
            f"Ожидалось: {BSL_JAR_SHA256}\n"
            f"Получено:  {digest}"
        )
    temporary.replace(destination)
    print(f"Сохранено: {destination}")
    print(f"SHA256: {digest}")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        destination = Path.home() / ".bsl-mcp" / BSL_JAR_NAME
    else:
        destination = Path(args[0]).expanduser()
    if destination.is_file():
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        if digest == BSL_JAR_SHA256:
            print(f"Файл уже загружен и совпадает с релизом {TESTED_BSL_VERSION}: {destination}")
            return 0
        print("Существующий файл имеет другую контрольную сумму и будет загружен заново.")
    download(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
