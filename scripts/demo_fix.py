"""阶段 1 demo：让 agent 端到端修好 benchmark/demo 里的 bug。"""
from code_agent.llm import LLMClient
from code_agent.loop import run_agent


def main():
    llm = LLMClient()
    env = {"repo_path": "benchmark/demo"}
    instance = {"test_command": "pytest test_calc.py -q"}
    out = run_agent(llm, env, instance)
    print("success:", out["success"])
    print("steps:", out["steps"])
    print("answer:", out["answer"])


if __name__ == "__main__":
    main()
