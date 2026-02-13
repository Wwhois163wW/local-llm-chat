from core.prompts import AssembledPrompt
from core.session_meta import SessionMetaManager
import os

def audit_prompt_size():
    # 模拟真实 Session 环境
    history_file = "tests/test_history.meta_history.jsonl"
    meta_manager = SessionMetaManager(history_file)
    
    # 构造元数据
    meta = meta_manager.get_snapshot()
    meta["current_mode"] = "ReAct"
    meta["current_task"] = "Analyze the codebase for optimization."
    
    prompt = AssembledPrompt.build(meta)
    
    print(f"--- Rendered Prompt Analysis ---")
    print(f"Character Length: {len(prompt)}")
    print(f"Line Count: {len(prompt.splitlines())}")
    
    # 模拟估算 Token (假设 1 token ~ 4 chars)
    est_tokens = len(prompt) // 4
    print(f"Estimated Tokens: ~{est_tokens}")
    
    print("\n--- Prompt Preview (First 500 chars) ---")
    print(prompt[:500] + "...")
    
    print("\n--- Prompt Preview (Last 500 chars) ---")
    print("..." + prompt[-500:])

if __name__ == "__main__":
    audit_prompt_size()
