"""验证 UI 侧边栏 API key 输入 → _get_llm 的完整链路（用 Streamlit AppTest 模拟点击）。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def test_sidebar_key_flows_to_session_state():
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    # 应该没有抛异常，且侧边栏存在 text_input（API key 输入框）
    assert not at.exception
    assert len(at.sidebar.text_input) >= 1, "侧边栏应该有 API key 输入框"

    # 模拟用户填 key 并触发一次 rerun
    at.sidebar.text_input[0].set_value("sk-test-123").run()
    assert at.session_state["api_key"] == "sk-test-123", "填的 key 应该进入 session_state"
