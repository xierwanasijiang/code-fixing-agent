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
