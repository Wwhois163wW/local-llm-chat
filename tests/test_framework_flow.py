#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tests/test_framework_flow.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260210
# Version: 1.0.0

import asyncio
import os
import configparser
from core.session import ChatSession
from core.agent import Agent
from tests.mock_llm import Get_Mock_LLM_Client

# @Antigravity, 20260210, [NEW]: 框架全链路异步冒烟测试
async def run_smoke_test():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config = configparser.ConfigParser()
    config.add_section('Agent')
    config.set('Agent', 'model', 'mock-model')
    config.set('Agent', 'max_turns', '3')
    config.add_section('LLM')
    config_path = os.path.join(base_dir, 'config.ini')
    if os.path.exists(config_path):
        config.read(config_path)

    # 1. 初始化 Mock 环境
    mock_client = Get_Mock_LLM_Client()
    history_file = os.path.join(base_dir, 'output', 'test_history.jsonl')
    
    session = ChatSession(
        client=mock_client,
        config=config,
        history_file=history_file
    )
    
    agent = Agent(session, debug_mode=True)
    
    print("\n[Smoke Test] Starting Framework Flow Test with Mock LLM...")
    print("-" * 50)
    
    # 2. 模拟用户输入：触发文件写入流程
    user_input = "Please write a file summary.md to describe the project."
    session.add_conversation_message('user', user_input)
    
    # 3. 驱动核心循环（模仿 consumer.py 的 process_turns）
    from core.consumer import process_turns
    await process_turns(agent, session, max_turns=3)
    
    print("-" * 50)
    print("[Smoke Test] Completed.")
    
    # 4. 验证结果
    # 检查历史记录中是否含有了 Tool 注入的消息
    history = session.chat_history
    tool_injected = False
    for msg in history:
        if msg['role'] == 'user' and '[Observation]' in msg['content']:
            tool_injected = True
            print(f"Verified: Found Tool Observation in history -> {msg['content'][:100]}...")
            break
    
    if tool_injected:
        print("✅ SUCCESS: Framework flow (Input -> Parse -> Action -> Observation -> Next Turn) is working!")
    else:
        print("❌ FAILURE: Tool feedback was not correctly injected into history.")

if __name__ == "__main__":
    asyncio.run(run_smoke_test())
