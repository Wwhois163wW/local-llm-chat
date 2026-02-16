#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tests/test_streamlined_read.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260216

import unittest
from unittest.mock import MagicMock
import os
import asyncio
import configparser
from core.session import ChatSession
from infra.background_api import _handle_read_resource

class TestStreamlinedRead(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # 1. 模拟配置
        self.config = configparser.ConfigParser()
        self.config.add_section('LLM')
        self.config.set('LLM', 'model', 'test-model')
        self.config.set('LLM', 'max_history_length', '10')
        self.config.set('LLM', 'max_context_tokens', '4096')
        
        # 2. 确定物理根路径
        test_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.abspath(os.path.join(test_dir, ".."))
        
        # 3. 模拟客户端和历史文件
        self.mock_client = MagicMock()
        self.history_file = os.path.join(self.project_root, "tests", "test_streamlined_history.jsonl")
        if os.path.exists(self.history_file):
            os.remove(self.history_file)
            
        self.session = ChatSession(
            client=self.mock_client,
            config=self.config,
            history_file=self.history_file
        )
        self.session.resource_manager.base_dir = self.project_root

    async def test_auto_load_on_read(self):
        """验证 read_resource 在资源未加载时能静默触发自动探测与加载。"""
        target_file = "core/session_meta.py" # 一个绝对存在的文件，但模拟 LLM “直接猜测路径读取”
        
        # 验证初始状态：RM 中尚未注册该文件
        self.assertNotIn(target_file, self.session.resource_manager.content_to_rid)
        
        # 执行读取 (模拟后台 API 处理器被调用)
        params = {"source": target_file, "start": 1, "end": 10}
        result = await _handle_read_resource(params, self.session)
        
        # 验证结果
        print(f"\n[Test] Auto-load result: {result.get('success')}")
        self.assertTrue(result.get("success"), f"Read failed: {result.get('error')}")
        content = result.get("result", "")
        self.assertIn("core/session_meta.py", content)
        
        # 核心验证：文件已在后台静默注册到 URM
        self.assertIn(target_file, self.session.resource_manager.content_to_rid)
        new_rid = self.session.resource_manager.content_to_rid[target_file]
        print(f"[Test] Silent registered RID: {new_rid}")
        self.assertTrue(new_rid.startswith("path_"))

    async def asyncTearDown(self):
        if os.path.exists(self.history_file):
            os.remove(self.history_file)

if __name__ == "__main__":
    unittest.main()
