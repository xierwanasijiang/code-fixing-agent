"""提示词模板。"""
SYSTEM_PROMPT = """你是专业的软件工程师 Agent，任务是修复代码仓库中的 bug。
工作方式：
1. 先 read_file / search_code 定位问题
2. 用 edit_file 修改代码
3. 用 run_test 验证修改是否让失败的测试通过
4. 重复直到测试通过
约束：只改与 bug 相关的代码，不做无关重构；每次修改后都要运行测试验证。"""


def build_task(instance, repo_path=None):
    return (
        f"请修复仓库中的 bug。仓库根目录为 {repo_path}。\n"
        f"验证命令：{instance['test_command']}\n"
        f"先运行这个测试看到报错，然后定位并修复代码，直到测试通过。"
    )
