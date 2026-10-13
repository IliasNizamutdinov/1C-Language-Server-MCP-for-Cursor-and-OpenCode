"""Сценарии проверки: файл, список, каталог и переданный текст."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from bsl_mcp.analyzer import AnalyzerNotReady, BslAnalyzer, build_configuration
from bsl_mcp.config import Settings
from bsl_mcp.constants import (
    FRAGMENT_LIMITATION,
    ISOLATED_FILE_NOTE,
    SCOPE_NOTE,
    SUPPORTED_EXTENSIONS,
)
from bsl_mcp.paths import (
    PathRejected,
    relative_to_root,
    resolve_project_dir,
    resolve_source_file,
    safe_code_file_name,
)
from bsl_mcp.report import (
    file_status,
    is_blocking,
    parse_report,
    public_diagnostic,
    split_diagnostics,
    status_text,
    summarize,
)

logger = logging.getLogger("bsl_mcp")
MAX_DIAGNOSTICS_PER_FILE = 100


@dataclass
class PreparedFile:
    display: str
    source: Path
    relative: str
    digest: str


class CheckService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.analyzer = BslAnalyzer(settings)
        self._slots = threading.Semaphore(settings.max_concurrent)

    def check_file(self, path: str, fail_on: str | None = None) -> dict[str, object]:
        policy = self._policy(fail_on)
        try:
            resolved = resolve_source_file(path, self.settings.allowed_roots)
        except PathRejected as error:
            return self._not_performed(error.message, policy, "isolated_file", [path])
        return self._check_paths(
            [resolved.path],
            policy,
            context="isolated_file",
            limitations=[ISOLATED_FILE_NOTE],
            config_root=self._config_root_for(resolved.path),
        )

    def check_files(self, paths: list[str], fail_on: str | None = None) -> dict[str, object]:
        policy = self._policy(fail_on)
        if not paths:
            return self._not_performed(
                "Список файлов пуст.",
                policy,
                "isolated_files",
                [],
            )
        accepted: list[Path] = []
        rejected: list[dict[str, object]] = []
        for raw in paths:
            try:
                accepted.append(resolve_source_file(raw, self.settings.allowed_roots).path)
            except PathRejected as error:
                rejected.append({"path": raw, "reason": error.message})
        if not accepted:
            return self._not_performed(
                "Ни один из указанных файлов не удалось передать анализатору.",
                policy,
                "isolated_files",
                [],
                skipped=rejected,
            )
        config_root = self._config_root_for(*accepted)
        result = self._check_paths(
            accepted,
            policy,
            context="isolated_files",
            limitations=[ISOLATED_FILE_NOTE],
            config_root=config_root,
            extra_skipped=rejected,
        )
        return result

    def check_project(self, path: str, fail_on: str | None = None) -> dict[str, object]:
        policy = self._policy(fail_on)
        try:
            root = resolve_project_dir(path, self.settings.allowed_roots)
        except PathRejected as error:
            return self._not_performed(error.message, policy, "project_sources", [path])
        files, skipped, excluded = self._scan_project(root)
        if len(files) > self.settings.max_files:
            return self._not_performed(
                f"В каталоге {root} найдено {len(files)} файлов .bsl/.os, "
                f"лимит BSL_MCP_MAX_FILES равен {self.settings.max_files}. "
                "Укажите более узкий каталог или увеличьте лимит.",
                policy,
                "project_sources",
                [],
                skipped=skipped,
                excluded_directory_count=excluded,
            )
        if not files:
            return self._not_performed(
                f"В каталоге {root} нет доступных файлов .bsl или .os.",
                policy,
                "project_sources",
                [],
                skipped=skipped,
                excluded_directory_count=excluded,
            )
        return self._check_paths(
            files,
            policy,
            context="project_sources",
            limitations=[ISOLATED_FILE_NOTE],
            config_root=self._config_root_for(root),
            extra_skipped=skipped,
            excluded_directory_count=excluded,
            project_root_for_names=root,
        )

    def check_code(
        self,
        code: str,
        file_name: str,
        fail_on: str | None = None,
    ) -> dict[str, object]:
        policy = self._policy(fail_on)
        if not isinstance(code, str):
            return self._not_performed(
                "Параметр code должен быть текстом модуля.",
                policy,
                "isolated_text",
                [],
            )
        try:
            safe_name = safe_code_file_name(file_name)
        except PathRejected as error:
            return self._not_performed(error.message, policy, "isolated_text", [])
        payload = code.lstrip("\ufeff").encode("utf-8")
        if len(payload) > self.settings.max_code_bytes:
            return self._not_performed(
                "Текст кода больше лимита BSL_MCP_MAX_CODE_BYTES "
                f"({self.settings.max_code_bytes} байт).",
                policy,
                "isolated_text",
                [],
            )
        limitations = [FRAGMENT_LIMITATION]
        temp_root = Path(tempfile.mkdtemp(prefix="bsl-mcp-"))
        result: dict[str, object] | None = None
        try:
            source_dir = temp_root / "src"
            output_dir = temp_root / "out"
            source_dir.mkdir()
            output_dir.mkdir()
            destination = source_dir / safe_name
            destination.write_bytes(payload)
            try:
                config_path = self._write_config(temp_root, None)
                output = self._run(source_dir, output_dir, config_path)
                parsed = parse_report(output.report)
            except AnalyzerNotReady as error:
                logger.error("Проверка текста не выполнена: %s", error.message)
                result = self._not_performed(
                    error.message,
                    policy,
                    "isolated_text",
                    [],
                    limitations=limitations,
                )
                return result
            except ValueError as error:
                logger.error("Отчёт по тексту не разобран: %s", error)
                result = self._not_performed(
                    str(error),
                    policy,
                    "isolated_text",
                    [],
                    limitations=limitations,
                )
                return result
            diagnostics = self._diagnostics_for(parsed, {destination.resolve(): safe_name}, safe_name)
            result = self._from_matches(
                [(safe_name, diagnostics)],
                policy,
                context="isolated_text",
                limitations=limitations,
                isolated=True,
                skipped=[],
                source_unchanged=True,
                duration=output.duration_seconds,
                excluded_directory_count=0,
            )
            return result
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)
            if result is not None:
                result["temporary_files_removed"] = not temp_root.exists()

    def _policy(self, fail_on: str | None) -> str:
        if fail_on is None or fail_on == "":
            return self.settings.fail_on
        if fail_on not in {"syntax", "error", "warning", "any"}:
            raise ValueError(f"Неизвестный режим fail_on: {fail_on}")
        return fail_on

    def _check_paths(
        self,
        paths: list[Path],
        policy: str,
        *,
        context: str,
        limitations: list[str],
        config_root: Path | None,
        extra_skipped: list[dict[str, object]] | None = None,
        excluded_directory_count: int = 0,
        project_root_for_names: Path | None = None,
    ) -> dict[str, object]:
        skipped = list(extra_skipped or [])
        unique: list[Path] = []
        seen: set[Path] = set()
        for path in paths:
            resolved = Path(os.path.realpath(path))
            if resolved in seen:
                continue
            seen.add(resolved)
            unique.append(path)
        prepared, prepare_skipped = self._prepare(unique, project_root_for_names)
        skipped.extend(prepare_skipped)
        if not prepared:
            return self._not_performed(
                "Нет файлов, которые можно передать анализатору.",
                policy,
                context,
                [],
                skipped=skipped,
                limitations=limitations,
                excluded_directory_count=excluded_directory_count,
            )
        digests = {item.source: item.digest for item in prepared}
        temp_root = Path(tempfile.mkdtemp(prefix="bsl-mcp-"))
        duration = 0.0
        result: dict[str, object] | None = None
        try:
            source_dir = temp_root / "src"
            output_dir = temp_root / "out"
            source_dir.mkdir()
            output_dir.mkdir()
            mapping: dict[Path, str] = {}
            for item in prepared:
                destination = source_dir / item.relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(item.source, destination)
                mapping[destination.resolve()] = item.display
            try:
                config_path = self._write_config(temp_root, config_root)
                output = self._run(source_dir, output_dir, config_path)
                parsed = parse_report(output.report)
                duration = output.duration_seconds
            except AnalyzerNotReady as error:
                logger.error("Проверка не выполнена: %s", error.message)
                unchanged = self._same_bytes(digests)
                result = self._not_performed(
                    error.message,
                    policy,
                    context,
                    [item.display for item in prepared],
                    skipped=skipped,
                    limitations=limitations,
                    source_unchanged=unchanged,
                    excluded_directory_count=excluded_directory_count,
                )
                return result
            except ValueError as error:
                logger.error("Отчёт анализатора не разобран: %s", error)
                result = self._not_performed(
                    str(error),
                    policy,
                    context,
                    [item.display for item in prepared],
                    skipped=skipped,
                    limitations=limitations,
                    source_unchanged=self._same_bytes(digests),
                    excluded_directory_count=excluded_directory_count,
                )
                return result
            matches = []
            seen_displays: set[str] = set()
            unexpected: list[str] = []
            for mdo, relative, diagnostics in parsed:
                display = None
                if mdo is not None:
                    display = mapping.get(Path(os.path.realpath(mdo)))
                if display is None:
                    display = mapping.get(Path(os.path.realpath(source_dir / relative)))
                if display is None:
                    unexpected.append(relative or (str(mdo) if mdo else ""))
                    continue
                seen_displays.add(display)
                matches.append((display, self._retag(diagnostics, display)))
            for item in prepared:
                if item.display not in seen_displays:
                    skipped.append(
                        {
                            "path": item.display,
                            "reason": "анализатор не вернул результат по этому файлу",
                        }
                    )
            if unexpected:
                limitations = [
                    *limitations,
                    "Анализатор вернул записи, которые не сопоставлены с проверяемыми файлами: "
                    + ", ".join(unexpected),
                ]
            result = self._from_matches(
                matches,
                policy,
                context=context,
                limitations=limitations,
                isolated=False,
                skipped=skipped,
                source_unchanged=self._same_bytes(digests),
                duration=duration,
                excluded_directory_count=excluded_directory_count,
            )
            return result
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)
            if result is not None:
                result["temporary_files_removed"] = not temp_root.exists()

    def _prepare(
        self,
        paths: list[Path],
        project_root: Path | None,
    ) -> tuple[list[PreparedFile], list[dict[str, object]]]:
        prepared: list[PreparedFile] = []
        skipped: list[dict[str, object]] = []
        names = self._relative_names(paths, project_root)
        for path, relative in names:
            display = str(path)
            try:
                info = path.stat()
            except OSError as error:
                skipped.append({"path": display, "reason": f"файл недоступен: {error}"})
                continue
            if info.st_size > self.settings.max_file_bytes:
                skipped.append(
                    {
                        "path": display,
                        "reason": "файл больше допустимого размера BSL_MCP_MAX_FILE_BYTES",
                    }
                )
                continue
            try:
                digest = _sha256(path)
                with path.open("rb") as handle:
                    sample = handle.read(1024)
            except OSError as error:
                skipped.append({"path": display, "reason": f"файл недоступен: {error}"})
                continue
            if b"\x00" in sample:
                skipped.append({"path": display, "reason": "файл не похож на текстовый модуль"})
                continue
            prepared.append(PreparedFile(display, path, relative, digest))
        return prepared, skipped

    def _relative_names(self, paths: list[Path], project_root: Path | None) -> list[tuple[Path, str]]:
        if project_root is not None:
            pairs = []
            for path in paths:
                try:
                    relative = relative_to_root(Path(os.path.realpath(path)), project_root)
                except (PathRejected, ValueError):
                    relative = path.name
                pairs.append((path, relative))
            return _deduplicate_names(pairs)
        if len(paths) == 1:
            return [(paths[0], paths[0].name)]
        try:
            base = Path(os.path.commonpath([str(path.resolve()) for path in paths]))
        except ValueError:
            base = None
        pairs = []
        for index, path in enumerate(paths, start=1):
            if base is not None and base.is_dir():
                try:
                    relative = path.resolve().relative_to(base).as_posix()
                except ValueError:
                    relative = f"{index}_{path.name}"
            else:
                relative = f"{index}_{path.name}"
            if ".." in Path(relative).parts:
                relative = f"{index}_{path.name}"
            pairs.append((path, relative))
        return _deduplicate_names(pairs)

    def _scan_project(self, root: Path) -> tuple[list[Path], list[dict[str, object]], int]:
        files: list[Path] = []
        skipped: list[dict[str, object]] = []
        excluded = 0
        seen: set[Path] = set()
        root_real = Path(os.path.realpath(root))
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            current = Path(dirpath)
            kept: list[str] = []
            for dirname in list(dirnames):
                child = current / dirname
                if dirname.lower() in self.settings.exclude_dir_names:
                    excluded += 1
                    continue
                if child.is_symlink():
                    skipped.append(
                        {
                            "path": str(child),
                            "reason": "каталог-ссылка не обходится",
                            "kind": "directory",
                        }
                    )
                    continue
                kept.append(dirname)
            dirnames[:] = kept
            for filename in filenames:
                path = current / filename
                if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    continue
                try:
                    real = Path(os.path.realpath(path))
                except OSError as error:
                    skipped.append({"path": str(path), "reason": f"файл недоступен: {error}"})
                    continue
                if not _is_inside(real, root_real) or not self._inside_allowed(real):
                    skipped.append(
                        {
                            "path": str(path),
                            "reason": "символическая ссылка или путь выходит за пределы разрешённого каталога",
                        }
                    )
                    continue
                if real in seen:
                    continue
                seen.add(real)
                files.append(path)
        return files, skipped, excluded

    def _inside_allowed(self, path: Path) -> bool:
        for root in self.settings.allowed_roots:
            if _is_inside(path, Path(os.path.realpath(root))):
                return True
        return False

    def _config_root_for(self, *starts: Path) -> Path | None:
        if not starts:
            return None
        try:
            common = Path(os.path.commonpath([str(Path(os.path.realpath(item))) for item in starts]))
        except ValueError:
            return None
        if common.is_file():
            current = common.parent
        else:
            current = common
        allowed = [Path(os.path.realpath(root)) for root in self.settings.allowed_roots]
        while True:
            candidate = current / ".bsl-language-server.json"
            if candidate.is_file():
                return current
            if any(current == root for root in allowed) or current.parent == current:
                return None
            current = current.parent

    def _write_config(self, temp_root: Path, project_root: Path | None) -> Path:
        config = build_configuration(self.settings, project_root)
        path = temp_root / "bsl-language-server.json"
        path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _run(self, source_dir: Path, output_dir: Path, configuration: Path):
        acquired = self._slots.acquire(timeout=self.settings.timeout_seconds)
        if not acquired:
            raise AnalyzerNotReady(
                "Анализатор занят другими проверками дольше BSL_MCP_TIMEOUT. Повторите запрос."
            )
        try:
            return self.analyzer.analyze(source_dir, output_dir, configuration)
        finally:
            self._slots.release()

    def _diagnostics_for(
        self,
        parsed: list[tuple[Path | None, str, list[dict[str, object]]]],
        mapping: dict[Path, str],
        fallback: str,
    ) -> list[dict[str, object]]:
        for mdo, relative, diagnostics in parsed:
            if mdo is not None and Path(os.path.realpath(mdo)) in mapping:
                return self._retag(diagnostics, mapping[Path(os.path.realpath(mdo))])
            candidate = next(iter(mapping))
            if relative == candidate.name or relative.endswith("/" + candidate.name):
                return self._retag(diagnostics, fallback)
        if parsed:
            return self._retag(parsed[0][2], fallback)
        return []

    def _retag(
        self,
        diagnostics: list[dict[str, object]],
        display: str,
    ) -> list[dict[str, object]]:
        retagged = []
        for item in diagnostics:
            copy = dict(item)
            copy["file"] = display
            retagged.append(copy)
        return retagged

    def _from_matches(
        self,
        matches: list[tuple[str, list[dict[str, object]]]],
        policy: str,
        *,
        context: str,
        limitations: list[str],
        isolated: bool,
        skipped: list[dict[str, object]],
        source_unchanged: bool,
        duration: float,
        excluded_directory_count: int,
    ) -> dict[str, object]:
        files: list[dict[str, object]] = []
        syntax_total = 0
        analysis_errors = 0
        warnings = 0
        other_total = 0
        any_syntax = False
        for display, diagnostics in matches:
            syntax, other = split_diagnostics(diagnostics)
            any_syntax = any_syntax or bool(syntax)
            syntax_total += len(syntax)
            other_total += len(other)
            analysis_errors += sum(1 for item in other if item.get("severity") == "Error")
            warnings += sum(1 for item in other if item.get("severity") == "Warning")
            status = file_status(diagnostics, policy)
            entry: dict[str, object] = {
                "file": display,
                "status": status,
                "status_text": status_text(status),
                "syntax_errors": [public_diagnostic(item) for item in syntax[:MAX_DIAGNOSTICS_PER_FILE]],
                "diagnostics": [public_diagnostic(item) for item in other[:MAX_DIAGNOSTICS_PER_FILE]],
            }
            if len(diagnostics) > MAX_DIAGNOSTICS_PER_FILE:
                entry["diagnostics_truncated"] = True
            files.append(entry)
        incomplete = [item for item in skipped if item.get("kind") != "directory"]
        for item in incomplete:
            files.append(
                {
                    "file": str(item.get("path")),
                    "status": "not_performed",
                    "status_text": status_text("not_performed"),
                    "syntax_errors": [],
                    "diagnostics": [],
                    "message": str(item.get("reason")),
                }
            )
        analyzed = [item for item in files if item["status"] != "not_performed"]
        blocking = any(
            is_blocking(diagnostic, policy)
            for _, diagnostics in matches
            for diagnostic in diagnostics
        )
        if not analyzed:
            status = "not_performed"
        elif blocking:
            status = "failed"
        elif isolated or incomplete:
            status = "limited"
        else:
            status = "passed"
        if not analyzed:
            syntax_status = "not_performed"
        elif any_syntax:
            syntax_status = "failed"
        else:
            syntax_status = "passed"
        if not source_unchanged:
            limitations = [
                *limitations,
                "Контрольная сумма хотя бы одного исходного файла изменилась во время проверки.",
            ]
        summary = summarize(status, syntax_total, analysis_errors, warnings, len(analyzed))
        return {
            "status": status,
            "status_text": status_text(status),
            "syntax_status": syntax_status,
            "summary": summary,
            "fail_on": policy,
            "context": context,
            "source_unchanged": source_unchanged,
            "temporary_files_removed": True,
            "files_checked": len(analyzed),
            "syntax_error_count": syntax_total,
            "analysis_error_count": analysis_errors,
            "warning_count": warnings,
            "diagnostic_count": other_total,
            "files": files,
            "skipped": skipped,
            "excluded_directory_count": excluded_directory_count,
            "limitations": limitations,
            "scope_note": SCOPE_NOTE,
            "analyzer": self.analyzer.describe(),
            "duration_seconds": duration,
            "line_base": 1,
        }

    def _not_performed(
        self,
        reason: str,
        policy: str,
        context: str,
        files: list[str],
        *,
        skipped: list[dict[str, object]] | None = None,
        limitations: list[str] | None = None,
        source_unchanged: bool = True,
        excluded_directory_count: int = 0,
    ) -> dict[str, object]:
        skipped_items = list(skipped or [])
        file_entries: list[dict[str, object]] = []
        seen = {str(item.get("path")) for item in skipped_items}
        for path in files:
            if path in seen:
                continue
            file_entries.append(
                {
                    "file": path,
                    "status": "not_performed",
                    "status_text": status_text("not_performed"),
                    "syntax_errors": [],
                    "diagnostics": [],
                    "message": reason,
                }
            )
        for item in skipped_items:
            file_entries.append(
                {
                    "file": str(item.get("path")),
                    "status": "not_performed",
                    "status_text": status_text("not_performed"),
                    "syntax_errors": [],
                    "diagnostics": [],
                    "message": str(item.get("reason")),
                }
            )
        return {
            "status": "not_performed",
            "status_text": status_text("not_performed"),
            "syntax_status": "not_performed",
            "summary": f"Проверка не выполнена. {reason}",
            "fail_on": policy,
            "context": context,
            "source_unchanged": source_unchanged,
            "temporary_files_removed": True,
            "files_checked": 0,
            "syntax_error_count": 0,
            "analysis_error_count": 0,
            "warning_count": 0,
            "diagnostic_count": 0,
            "files": file_entries,
            "skipped": skipped_items,
            "excluded_directory_count": excluded_directory_count,
            "limitations": list(limitations or []),
            "scope_note": SCOPE_NOTE,
            "analyzer": self.analyzer.describe(),
            "duration_seconds": 0,
            "line_base": 1,
        }

    @staticmethod
    def _same_bytes(digests: dict[Path, str]) -> bool:
        for path, digest in digests.items():
            try:
                if _sha256(path) != digest:
                    return False
            except OSError:
                return False
        return True


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _deduplicate_names(pairs: list[tuple[Path, str]]) -> list[tuple[Path, str]]:
    used: set[str] = set()
    result: list[tuple[Path, str]] = []
    for index, (path, relative) in enumerate(pairs, start=1):
        candidate = relative
        if candidate in used:
            candidate = f"{index}_{path.name}"
        used.add(candidate)
        result.append((path, candidate))
    return result
