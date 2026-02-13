#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tests/test_context_trimming.py

import unittest
import configparser
import os
from core.session import ChatSession
from tests.mock_llm import Get_Mock_LLM_Client

class TestContextTrimming(unittest.TestCase):
    def setUp(self):
        self.config = configparser.ConfigParser()
        self.config.add_section('LLM')
        self.config.set('LLM', 'ip', '127.0.0.1')
        self.config.set('LLM', 'port', '1234')
        self.config.set('LLM', 'api_key', 'test')
        self.config.set('LLM', 'model', 'test-model')
        self.config.set('LLM', 'max_history_length', '20')
        # 强制设置较小的上限用于测试
        self.config.set('LLM', 'max_context_tokens', '2000')
        
        self.history_file = 'tests/context_test.jsonl'
        self.mock_client = Get_Mock_LLM_Client()
        self.session = ChatSession(self.mock_client, self.config, self.history_file)

    def tearDown(self):
        if os.path.exists(self.history_file):
            os.remove(self.history_file)
        history_meta = self.history_file.replace('.jsonl', '.meta.json')
        if os.path.exists(history_meta):
            os.remove(history_meta)

    def test_sliding_window_truncation(self):
        """测试历史记录是否在超过 Token 上限时被正确截断。"""
        # 1. 注入一条巨大的消息 (约为 1500 Tokens)
        large_content = "Word " * 1500 
        self.session.add_conversation_message('user', large_content)
        
        # 2. 再注入一些正常消息
        self.session.add_conversation_message('assistant', "I understand context limits.")
        self.session.add_conversation_message('user', "Explain Python decorators.")
        
        # 3. 构建 Prompt
        prompt = self.session.build_prompt()
        total_tokens = self.session.count_tokens(prompt)
        
        print(f"\n[Test] Prompt Messages: {len(prompt)}")
        print(f"[Test] Total Tokens: {total_tokens}")
        for i, msg in enumerate(prompt):
            print(f"  - Msg {i} ({msg['role']}): {len(msg.get('content',''))} chars")

        # 验证：总 Token 必须低于 max_context_tokens (2000)
        self.assertLessEqual(total_tokens, 2000)
        
        # 验证：System Prompt 必须保留在第一位
        self.assertEqual(prompt[0]['role'], 'system')
        
        # 验证：最新的消息必须保留
        self.assertEqual(prompt[-1]['content'], "Explain Python decorators.")
        
        # 验证：那个巨大的消息应该已经被滑窗踢出或截断（在 valid_history 逻辑中是整条踢出）
        # 检查是否包含那条超长消息
        has_large_msg = any(large_content in str(m.get('content')) for m in prompt)
        self.assertFalse(has_large_msg, "Large message should have been truncated to fit window.")

if __name__ == '__main__':
    unittest.main()
