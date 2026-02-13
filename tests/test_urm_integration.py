#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tests/test_urm_integration.py

import unittest
import os
import shutil
import asyncio
import configparser
from unittest.mock import MagicMock
from core.session import ChatSession
from core.events import FileWriteRequest, LoadResourceRequest
from infra.background_api import Execute_Task_by_Name
from core.consumer import handle_generic_action

class TestURMIntegration(unittest.TestCase):
    def setUp(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.staging_dir = os.path.join(self.base_dir, "staging")
        self.history_file = os.path.join(self.base_dir, "tests", "test_history.jsonl")
        
        # Mock LLM Client & Config
        self.mock_client = MagicMock()
        self.config = configparser.ConfigParser()
        self.config.add_section('LLM')
        self.config.set('LLM', 'model', 'test-model')
        self.config.set('LLM', 'max_history_length', '10')
        self.config.set('LLM', 'compression_threshold', '8')
        
        self.session = ChatSession(client=self.mock_client, config=self.config, history_file=self.history_file)
        
        # 清理环境
        if os.path.exists(self.staging_dir):
            shutil.rmtree(self.staging_dir)
        if os.path.exists(self.history_file):
            os.remove(self.history_file)

    def tearDown(self):
        if os.path.exists(self.staging_dir):
            shutil.rmtree(self.staging_dir)
        if os.path.exists(self.history_file):
            os.remove(self.history_file)

    def run_async(self, coro):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_urm_load_and_write_overlay(self):
        """测试 URM 加载后，写操作执行原地覆盖。"""
        sub_path = "tests/integration_test.txt"
        abs_path = os.path.join(self.base_dir, sub_path)
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write("v1")

        # 1. 模拟加载
        load_res = self.run_async(Execute_Task_by_Name(
            "LoadResourceRequest", 
            {"res_type": "file", "source": sub_path}, 
            context={"session": self.session}
        ))
        self.assertTrue(load_res["success"])
        
        # 2. 模拟写入
        event = FileWriteRequest(path=sub_path, content_to_write="v2")
        self.run_async(handle_generic_action(event, self.session))
        
        # 验证物理覆盖
        with open(abs_path, 'r', encoding='utf-8') as f:
            self.assertEqual(f.read(), "v2")
            
        # 验证产生了备份
        backup_dir = os.path.join(self.staging_dir, "backups")
        self.assertTrue(os.path.exists(backup_dir))
        self.assertTrue(len(os.listdir(backup_dir)) >= 1)
        
        # 清理
        if os.path.exists(abs_path): os.remove(abs_path)

    def test_write_isolation_no_load(self):
        """测试资源未加载时，写操作重定向至 staging/new。"""
        sub_path = "tests/unknown_integration.txt"
        abs_path = os.path.join(self.base_dir, sub_path)
        if os.path.exists(abs_path): os.remove(abs_path)
        
        event = FileWriteRequest(path=sub_path, content_to_write="isolated")
        obs = self.run_async(handle_generic_action(event, self.session))
        
        self.assertIn("staging/new/", obs)
        self.assertEqual(self.session.meta_manager.state.last_action_type, "Create")
        
        # 物理检查
        staging_file = os.path.join(self.staging_dir, "new", "tests", "unknown_integration.txt")
        self.assertTrue(os.path.exists(staging_file))
        self.assertFalse(os.path.exists(abs_path))

if __name__ == "__main__":
    unittest.main()
