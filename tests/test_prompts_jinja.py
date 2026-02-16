from core.prompts import AssembledPrompt
import json

def test_prompt_rendering():
    # 测试案例 1：完整 ReAct 模式（包含用户画像）
    meta_full = {
        "current_mode": "ReAct",
        "current_task": "Analyze the codebase",
        "user_profile": "A senior software engineer specializing in Python.",
        "context_summary": "User requested refactoring of prompts.",
        "is_new_turn": True
    }
    print("--- Test Case 1: Full ReAct with User Profile ---")
    prompt_1 = AssembledPrompt.build(meta_full)
    print(prompt_1[:500] + "...") # 只打印开头
    assert "USER PROFILE:" in prompt_1
    assert "ReAct PARADIGM:" in prompt_1
    assert "Analyze the codebase" in prompt_1
    print("\n[PASS] Case 1 Success\n")

    # 测试案例 2：缺失用户画像（触发引导词）
    meta_no_profile = {
        "current_mode": "ReAct",
        "current_task": "Simple fix",
        "user_profile": None,
        "is_new_turn": False
    }
    print("--- Test Case 2: ReAct without User Profile ---")
    prompt_2 = AssembledPrompt.build(meta_no_profile)
    assert "USER PROFILE:" not in prompt_2
    assert "ask relevant questions to build their profile" in prompt_2
    assert "Fast Thought" not in prompt_2 # is_new_turn 为 False
    print("\n[PASS] Case 2 Success\n")

    # 测试案例 4：专家角色 - 画像师 (Profiler)
    meta_profiler = {
        "current_mode": "ReAct",
        "current_role": "profiler",
        "current_task": "Build user persona"
    }
    print("--- Test Case 4: Dynamic Tooling - Profiler ---")
    prompt_4 = AssembledPrompt.build(meta_profiler)
    assert "<name>get_metadata</name>" in prompt_4
    assert "<name>update_metadata</name>" in prompt_4
    assert "<name>write_file</name>" not in prompt_4 # 核心：画像师工具箱不含写操作
    assert "<name>execute_command</name>" not in prompt_4 
    print("\n[PASS] Case 4 Success (Restricted Tools for Profiler)\n")

    # 测试案例 5：专家角色 - 编码员 (Coder)
    meta_coder = {
        "current_mode": "ReAct",
        "current_role": "coder",
        "current_task": "Write binary search"
    }
    print("--- Test Case 5: Dynamic Tooling - Coder (Streamlined) ---")
    prompt_5 = AssembledPrompt.build(meta_coder)
    assert "<name>write_file</name>" in prompt_5
    assert "<name>execute_command</name>" in prompt_5
    assert "<name>get_metadata</name>" not in prompt_5 
    assert "<name>load_resource</name>" not in prompt_5 # [NEW]: 确保 load_resource 已对 Coder 隐藏
    print("\n[PASS] Case 5 Success (Streamlined Tools for Coder)\n")

if __name__ == "__main__":
    try:
        test_prompt_rendering()
        print("All dynamic prompt rendering tests passed!")
    except Exception as e:
        print(f"Test failed: {e}")
