#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tests/test_tiered_write_interception.py

import unittest
import asyncio
import time
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
from core.consumer import handle_generic_action
from core.events import FileWriteRequest

class MockSession:
    def __init__(self, base_dir):
        self.meta_manager = MagicMock()
        self.meta_manager.state.base_dir = base_dir
        self.resource_manager = MagicMock()
        self.resource_manager.base_dir = base_dir
        self.client = MagicMock()
    def Update_Metadata_by_Key(self, key, value, persistent): pass

class TestTieredWriteInterception(unittest.IsolatedAsyncioTestCase):
    """验证基于三级核载（New/Loaded/Physical）的写入判定逻辑。"""

    async def asyncSetUp(self):
        self.tmp_dir = os.path.abspath("tmp_test_workspace")
        os.makedirs(self.tmp_dir, exist_ok=True)
        # 准备 staging 目录结构
        self.staging_new = os.path.join(self.tmp_dir, "staging", "new")
        os.makedirs(self.staging_new, exist_ok=True)
        
        self.session = MockSession(self.tmp_dir)
        self.cooldown_tracker = {}

    async def asyncTearDown(self):
        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)

    @patch('core.consumer.Execute_Task_by_Name')
    async def test_update_from_staging_new(self, mock_execute):
        """场景 1：如果 staging/new 已存在，应判定为 Update 并放行。"""
        file_path = "logic.py"
        os.makedirs(self.staging_new, exist_ok=True)
        with open(os.path.join(self.staging_new, file_path), 'w') as f: f.write("orig")
        
        mock_execute.return_value = {"success": True, "action_type": "Update"}
        event = FileWriteRequest(path=file_path, content="new content")
        
        # 连续发起两次，不应拦截
        res1 = await handle_generic_action(event, self.session, self.cooldown_tracker)
        res2 = await handle_generic_action(event, self.session, self.cooldown_tracker)
        
        self.assertIsNone(res1)
        self.assertIsNone(res2)
        self.assertEqual(event.act_type, "Update")

    @patch('core.consumer.Execute_Task_by_Name')
    async def test_update_from_urm_resource(self, mock_execute):
        """场景 2：如果资源管理器已知该文件，判定为 Update 并放行。"""
        file_path = "urm_file.txt"
        self.session.resource_manager.get_resource.return_value = {"id": "rid_1"}
        
        mock_execute.return_value = {"success": True, "action_type": "Update"}
        event = FileWriteRequest(path=file_path, content="content")
        
        res = await handle_generic_action(event, self.session, self.cooldown_tracker)
        self.assertIsNone(res)
        self.assertEqual(event.act_type, "Update")

    @patch('core.consumer.Execute_Task_by_Name')
    async def test_update_from_physical_workspace(self, mock_execute):
        """场景 3：如果工作区源文件存在，判定为 Update 并放行。"""
        file_path = "physical.py"
        with open(os.path.join(self.tmp_dir, file_path), 'w') as f: f.write("phys")
        
        mock_execute.return_value = {"success": True, "action_type": "Update"}
        event = FileWriteRequest(path=file_path, content="content")
        
        res = await handle_generic_action(event, self.session, self.cooldown_tracker)
        self.assertIsNone(res)
        self.assertEqual(event.act_type, "Update")

    @patch('core.consumer.Execute_Task_by_Name')
    async def test_create_blocked_by_cooldown(self, mock_execute):
        """场景 4：全新路径应判定为 Create，且受 60s 冷却拦截。"""
        file_path = "brand_new.py"
        # 确保 URM 和物理路径都不存在
        self.session.resource_manager.get_resource.return_value = None
        
        mock_execute.return_value = {"success": True, "action_type": "Create"}
        event = FileWriteRequest(path=file_path, content="content")
        
        # 第一次执行：成功
        res1 = await handle_generic_action(event, self.session, self.cooldown_tracker)
        self.assertIsNone(res1)
        self.assertEqual(event.act_type, "Create")
        
        # 模拟冷却追踪（手动更新 tracker 以防 mock_execute 不起作用，但在代码中它是根据 success 记的）
        # 在真实代码中，res1 对应的 Execute_Task_by_Name 成功后会记入 tracker
        abs_path = os.path.normcase(os.path.abspath(file_path))
        self.cooldown_tracker[abs_path] = time.time()
        
        # 第二次执行：应拦截
        res2 = await handle_generic_action(event, self.session, self.cooldown_tracker)
        self.assertIn("Create blocked", res2)

if __name__ == '__main__':
    unittest.main()
