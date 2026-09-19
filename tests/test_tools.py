from code_agent.tools import TOOL_SCHEMAS, execute_tool


def test_schema_has_five_tools():
    names = {t["function"]["name"] for t in TOOL_SCHEMAS}
    assert names == {"list_files", "read_file", "search_code", "edit_file", "run_test"}


def test_read_file(tmp_path):
    (tmp_path / "a.py").write_text("line1\nline2\nline3\n")
    out = execute_tool("read_file", {"path": "a.py"}, {"repo_path": str(tmp_path)})
    assert "line2" in out


def test_edit_file_roundtrip(tmp_path):
    (tmp_path / "a.py").write_text("old text here\n")
    execute_tool(
        "edit_file",
        {"path": "a.py", "old": "old text", "new": "new text"},
        {"repo_path": str(tmp_path)},
    )
    assert (tmp_path / "a.py").read_text() == "new text here\n"


def test_search_code(tmp_path):
    (tmp_path / "a.py").write_text("def foo():\n    return 42\n\nbar = foo()\n")
    (tmp_path / "__pycache__").mkdir(parents=True, exist_ok=True)
    (tmp_path / "__pycache__" / "b.py").write_text("def foo(): pass\n")
    out = execute_tool("search_code", {"pattern": "foo"}, {"repo_path": str(tmp_path)})
    assert "a.py:1:def foo():" in out
    assert "a.py:4:bar = foo()" in out
    # 排除 __pycache__ 下的文件
    assert "b.py" not in out


def test_search_code_no_match(tmp_path):
    (tmp_path / "a.py").write_text("hello\n")
    out = execute_tool("search_code", {"pattern": "zzz_not_here"}, {"repo_path": str(tmp_path)})
    assert out == "无匹配"


def test_run_test_tool_passes(tmp_path):
    (tmp_path / "mylib.py").write_text("def add(a, b):\n    return a + b\n")
    (tmp_path / "test_mylib.py").write_text(
        "from mylib import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )
    out = execute_tool("run_test", {"test_cmd": "pytest test_mylib.py -q"},
                       {"repo_path": str(tmp_path)})
    assert "returncode=0" in out


def test_run_test_tool_fails(tmp_path):
    (tmp_path / "mylib.py").write_text("def add(a, b):\n    return a - b\n")
    (tmp_path / "test_mylib.py").write_text(
        "from mylib import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )
    out = execute_tool("run_test", {"test_cmd": "pytest test_mylib.py -q"},
                       {"repo_path": str(tmp_path)})
    assert "returncode=1" in out


def test_run_test_rejects_command_injection(tmp_path):
    (tmp_path / "mylib.py").write_text("def add(a, b):\n    return a + b\n")
    out = execute_tool(
        "run_test",
        {"test_cmd": "pytest test_x.py -q && echo hacked"},
        {"repo_path": str(tmp_path)},
    )
    assert "只允许" in out
    # 拒绝的命令不应被执行：不会留下 hacked 文件
    assert not (tmp_path / "hacked").exists()


def test_run_test_rejects_non_pytest(tmp_path):
    out = execute_tool("run_test", {"test_cmd": "echo hacked"},
                       {"repo_path": str(tmp_path)})
    assert "只允许" in out


def test_read_file_rejects_parent_traversal(tmp_path):
    (tmp_path / "a.py").write_text("ok\n")
    secret = tmp_path.parent / "secret.txt"
    secret.write_text("TOP SECRET\n")
    out = execute_tool("read_file", {"path": "../secret.txt"},
                       {"repo_path": str(tmp_path)})
    assert out == "错误：路径越界"
    assert "TOP SECRET" not in out


def test_read_file_rejects_absolute_path(tmp_path):
    (tmp_path / "a.py").write_text("ok\n")
    secret = tmp_path.parent / "abs_secret.txt"
    secret.write_text("TOP SECRET\n")
    out = execute_tool("read_file", {"path": str(secret)},
                       {"repo_path": str(tmp_path)})
    assert out == "错误：路径越界"
    assert "TOP SECRET" not in out


def test_edit_file_rejects_traversal(tmp_path):
    secret = tmp_path.parent / "secret.txt"
    secret.write_text("DON'T TOUCH\n")
    out = execute_tool(
        "edit_file",
        {"path": "../secret.txt", "old": "DON'T", "new": "CHANGED"},
        {"repo_path": str(tmp_path)},
    )
    assert out == "错误：路径越界"
    # 越界路径未被写入
    assert secret.read_text() == "DON'T TOUCH\n"
