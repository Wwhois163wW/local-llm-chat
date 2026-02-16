#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tests/test_middleware_capture.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260216
# Version: 1.0.0

import unittest
from unittest.mock import MagicMock
import os
import configparser
from core.session import ChatSession

class TestMiddlewareCapture(unittest.TestCase):
    def setUp(self):
        # 1. 模拟配置
        self.config = configparser.ConfigParser()
        self.config.add_section('LLM')
        self.config.set('LLM', 'model', 'test-model')
        self.config.set('LLM', 'max_history_length', '10')
        self.config.set('LLM', 'max_context_tokens', '4096')
        
        # 2. 确定物理根路径（适应从根目录或从 tests/ 目录运行）
        test_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.abspath(os.path.join(test_dir, ".."))
        print(f"\n[Test Setup] CWD: {os.getcwd()} | Project Root: {self.project_root}")
        
        # 3. 模拟客户端和历史文件
        self.mock_client = MagicMock()
        self.history_file = os.path.join(self.project_root, "tests", "test_history.jsonl")
        if os.path.exists(self.history_file):
            os.remove(self.history_file)
            
        self.session = ChatSession(
            client=self.mock_client,
            config=self.config,
            history_file=self.history_file
        )
        # 强制修正 ResourceManager 的 base_dir
        self.session.resource_manager.base_dir = self.project_root

    def test_element_capture_logic(self):
        """测试中间件是否能同时捕获用户输入和助理输出中的要素。"""
        # A. 模拟用户输入包含路径和 URL
        user_msg = "Please check the file core/session.py and look at https://google.com"
        self.session.add_conversation_message("user", user_msg)
        
        meta = self.session.get_metadata()
        active_elements = meta.get("active_elements_info", "")
        print(f"\n[Test] After User Msg, Active Elements:\n{active_elements}")
        
        self.assertIn("path_1", active_elements)
        self.assertIn("url_1", active_elements)
        self.assertIn("session.py", active_elements)

        # B. 模拟助理回复包含新的要素（代码块）
        assistant_msg = "I found the logic. Try this patch:\n```python\nprint('hello world')\n```"
        self.session.add_conversation_message("assistant", assistant_msg)
        
        meta = self.session.get_metadata()
        active_elements = meta.get("active_elements_info", "")
        print(f"\n[Test] After Assistant Msg, Active Elements:\n{active_elements}")
        
        self.assertIn("block_1", active_elements)
        self.assertIn("print('hello world')", active_elements)

    def tearDown(self):
        if os.path.exists(self.history_file):
            os.remove(self.history_file)

if __name__ == "__main__":
    unittest.main()
