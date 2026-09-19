import os
import subprocess

from code_agent.sandbox import run_test


def _make_tiny_repo(tmp_path):
    (tmp_path / "mylib.py").write_text("def add(a, b):\n    return a + b\n")
    (tmp_path / "test_mylib.py").write_text(
        "from mylib import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )
    return str(tmp_path)


def test_run_test_passes(tmp_path):
    repo = _make_tiny_repo(tmp_path)
    out = run_test(repo, "pytest test_mylib.py -q")
    assert out["returncode"] == 0
    assert "1 passed" in out["stdout"]


def test_run_test_fails(tmp_path):
    repo = _make_tiny_repo(tmp_path)
    (tmp_path / "mylib.py").write_text("def add(a, b):\n    return a - b\n")
    out = run_test(repo, "pytest test_mylib.py -q")
    assert out["returncode"] == 1
