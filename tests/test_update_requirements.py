from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

import pytest

cupdate = import_module("cupdate.main")

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(packages: list[str]) -> dict[str, dict[str, str]]:
        return {p: {"version": "9.9.9", "url": "", "age": ""} for p in packages}

    monkeypatch.setattr(cupdate, "get_latest_versions", fake)


def run(tmp_path: Path, requirements: str, config: str | None = None) -> str:
    path = tmp_path / "requirements.txt"
    path.write_text(requirements)

    config_path = None
    if config is not None:
        config_path = str(tmp_path / "cupdate.config.txt")
        (tmp_path / "cupdate.config.txt").write_text(config)

    cupdate.update_requirements(str(path), config_path)
    return path.read_text()


def test_keeps_environment_markers(tmp_path: Path) -> None:
    result = run(
        tmp_path,
        'onnxruntime-gpu==1.29.0; platform_machine == "x86_64" or platform_machine == "AMD64"\n'
        'onnxruntime==1.29.0; platform_machine != "x86_64" and platform_machine != "AMD64"\n',
    )
    assert result == (
        'onnxruntime-gpu==9.9.9; platform_machine == "x86_64" or platform_machine == "AMD64"\n'
        'onnxruntime==9.9.9; platform_machine != "x86_64" and platform_machine != "AMD64"\n'
    )


def test_keeps_comments_blank_lines_and_order(tmp_path: Path) -> None:
    result = run(tmp_path, "# pinned for the old runtime\nnumpy==2.4.6\n\naiohttp==3.14.3\n")
    assert result == "# pinned for the old runtime\nnumpy==9.9.9\n\naiohttp==9.9.9\n"


def test_keeps_trailing_comment(tmp_path: Path) -> None:
    assert run(tmp_path, "numpy==2.4.6  # ABI\n") == "numpy==9.9.9  # ABI\n"


def test_leaves_direct_references_alone(tmp_path: Path) -> None:
    source = 'hailort @ https://example.com/hailort-4.21.0.whl ; platform_machine=="aarch64"\n'
    assert run(tmp_path, source) == source


def test_leaves_option_lines_and_ranges_alone(tmp_path: Path) -> None:
    source = "-r base.txt\n--index-url https://example.com/simple\nnumpy>=2.0,<3\n"
    assert run(tmp_path, source) == source


def test_preserves_operator_and_extras(tmp_path: Path) -> None:
    assert run(tmp_path, "aiohttp[speedups]>=3.14.3\n") == "aiohttp[speedups]>=9.9.9\n"


def test_excluded_package_is_untouched(tmp_path: Path) -> None:
    result = run(tmp_path, "onnxruntime-gpu==1.26.0\nnumpy==2.4.6\n", config="onnxruntime-gpu\n")
    assert result == "onnxruntime-gpu==1.26.0\nnumpy==9.9.9\n"


def test_windows_line_endings_survive(tmp_path: Path) -> None:
    path = tmp_path / "requirements.txt"
    path.write_bytes(b"numpy==2.4.6\r\n")
    cupdate.update_requirements(str(path), None)
    assert path.read_bytes() == b"numpy==9.9.9\r\n"


def test_file_untouched_when_nothing_changes(tmp_path: Path) -> None:
    path = tmp_path / "requirements.txt"
    path.write_text("numpy==9.9.9\n")
    before = path.stat().st_mtime_ns
    cupdate.update_requirements(str(path), None)
    assert path.read_text() == "numpy==9.9.9\n"
    assert path.stat().st_mtime_ns == before


def test_read_requirements_reports_markers_free_versions(tmp_path: Path) -> None:
    path = tmp_path / "requirements.txt"
    path.write_text('numpy==2.4.6\nonnxruntime==1.29.0; sys_platform == "darwin"\naiohttp>=3.14.3\n')
    assert cupdate.read_requirements(str(path)) == {
        "numpy": "2.4.6",
        "onnxruntime": "1.29.0",
        "aiohttp": ">=3.14.3",
    }
