from core.session import ChatSession
from core.prompts import AssembledPrompt
import os
import configparser
import asyncio
from unittest.mock import MagicMock

def test_proactive_mounting():
    # 1. 初始化 Mock 环境
    history_file = "tests/test_prm_history.jsonl"
    if os.path.exists(history_file): 
        try: os.remove(history_file)
        except: pass
    
    # Mock Config
    config = configparser.ConfigParser()
    config['LLM'] = {
        'model': 'test-model',
        'max_history_length': '10',
        'max_context_tokens': '4096'
    }
    
    # Mock Client
    mock_client = MagicMock()
    
    session = ChatSession(mock_client, config, history_file)
    
    # 2. 模拟包含路径的用户输入
    target_path = "README.md" # 使用相对路径测试
    user_input = f"请阅读这个文件: {target_path}"
    
    print(f"--- Step 1: Simulating User Input ---")
    print(f"Input: {user_input}")
    session.add_conversation_message("user", user_input)
    
    # 3. 检查元数据是否已更新
    meta = session.get_metadata()
    print(f"\n--- Step 2: Checking Metadata ---")
    print(f"Full Meta Snapshot: {meta}")
    detected_info = meta.get("detected_resources_info")
    print(f"Detected Info Value: {detected_info}")
    
    assert "res_1" in str(detected_info)
    assert "README.md" in str(detected_info)
    
    # 4. 检查提示词渲染结果
    prompt = AssembledPrompt.build(meta)
    print(f"\n--- Step 3: Checking Rendered Prompt ---")
    assert "PROACTIVELY DETECTED RESOURCES" in prompt
    assert "res_1" in prompt
    print("[PASS] Prompt contains the alias guidance.")
    
    # 5. 验证别名解析逻辑 (模拟工具调用)
    from infra.background_api import probe_and_load_resource
    
    async def verify_resolution():
        print(f"\n--- Step 4: Verifying Alias Resolution ---")
        res = await probe_and_load_resource("res_1", session)
        assert res["success"] is True
        # 验证解析后的物理路径是否对齐
        actual_res = session.resource_manager.get_resource("res_1")
        assert actual_res is not None
        assert "README.md" in actual_res["source"]
        print("[PASS] Alias 'res_1' resolved successfully.")

    asyncio.run(verify_resolution())

if __name__ == "__main__":
    test_proactive_mounting()

if __name__ == "__main__":
    test_proactive_mounting()
