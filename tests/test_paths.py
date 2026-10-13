from pathlib import Path

import pytest

from bsl_mcp.paths import (
    PathRejected,
    resolve_inside_roots,
    resolve_source_file,
    safe_code_file_name,
)


def test_rejects_parent_escape(tmp_path: Path) -> None:
    allowed = tmp_path / "work"
    allowed.mkdir()
    outside = tmp_path / "secret.bsl"
    outside.write_text("А = 1;\n", encoding="utf-8")
    with pytest.raises(PathRejected):
        resolve_inside_roots(str(allowed / ".." / "secret.bsl"), (allowed,))


def test_rejects_symlink_escape(tmp_path: Path) -> None:
    allowed = tmp_path / "work"
    allowed.mkdir()
    outside = tmp_path / "outside.bsl"
    outside.write_text("А = 1;\n", encoding="utf-8")
    link = allowed / "link.bsl"
    link.symlink_to(outside)
    with pytest.raises(PathRejected):
        resolve_source_file(str(link), (allowed,))


def test_allows_file_inside_root(tmp_path: Path) -> None:
    allowed = tmp_path / "work"
    module = allowed / "Module.bsl"
    module.parent.mkdir()
    module.write_text("А = 1;\n", encoding="utf-8")
    resolved = resolve_source_file(str(module), (allowed,))
    assert resolved.path == module.resolve()


def test_code_file_name_rejects_path() -> None:
    with pytest.raises(PathRejected):
        safe_code_file_name(r"..\Module.bsl")
    with pytest.raises(PathRejected):
        safe_code_file_name("notes.txt")
    assert safe_code_file_name("Module.BSL") == "Module.BSL"
