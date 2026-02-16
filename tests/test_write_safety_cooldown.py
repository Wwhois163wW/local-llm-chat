#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tests/test_write_safety_cooldown.py

import unittest
import asyncio
import time
import os
from unittest.mock import MagicMock, patch
from core.consumer import handle_generic_action
from core.events import FileWriteRequest

class MockSession:
    def __init__(self):
        self.meta_manager = MagicMock()
        self.resource_manager = MagicMock()
        self.client = MagicMock()
    def Update_Metadata_by_Key(self, key, value, persistent): pass

class TestWriteSafetyCooldown(unittest.IsolatedAsyncioTestCase):
    """验证基于路径与时间的写入冷却拦截逻辑。"""

    async def asyncSetUp(self):
        self.session = MockSession()
        self.cooldown_tracker = {}

    @patch('core.consumer.Execute_Task_by_Name')
    async def test_consecutive_create_same_path_blocked(self, mock_execute):
        """验证：60秒内对同一路径连续 Create 应被拦截。"""
        # 第一次 Create：确保资源管理器返回 None (模拟新建)
        self.session.resource_manager.get_resource.return_value = None
        mock_execute.return_value = {"success": True, "action_type": "Create"}
        
        event = FileWriteRequest(path="test.py", content="print(1)")
        event.act_type = "Create"
        
        # 执行第一次
        res1 = await handle_generic_action(event, self.session, self.cooldown_tracker)
        self.assertIsNone(res1) # 返回 None 表示交给后台执行了，但由于 mock，实际是在 tracker 里记了时间
        
        # 立即执行第二次（同一路径）
        res2 = await handle_generic_action(event, self.session, self.cooldown_tracker)
        self.assertIn("Create blocked", res2)
        self.assertIn("60s", res2)

    @patch('core.consumer.Execute_Task_by_Name')
    async def test_different_paths_not_blocked(self, mock_execute):
        """验证：对不同路径连续 Create 不应拦截。"""
        self.session.resource_manager.get_resource.return_value = None
        mock_execute.return_value = {"success": True, "action_type": "Create"}
        
        # 路径 A
        event_a = FileWriteRequest(path="a.py", content="print('a')")
        # 路径 B
        event_b = FileWriteRequest(path="b.py", content="print('b')")
        
        res_a = await handle_generic_action(event_a, self.session, self.cooldown_tracker)
        res_b = await handle_generic_action(event_b, self.session, self.cooldown_tracker)
        
        self.assertIsNone(res_a)
        self.assertIsNone(res_b)

    @patch('core.consumer.Execute_Task_by_Name')
    async def test_update_is_not_blocked(self, mock_execute):
        """验证：Update 行为不受冷却锁限制。"""
        # 模拟文件已存在
        self.session.resource_manager.get_resource.return_value = {"id": "path_1"}
        mock_execute.return_value = {"success": True, "action_type": "Update"}
        
        event = FileWriteRequest(path="existing.py", content="update")
        event.act_type = "Update"
        
        # 即使连续执行两次 Update 也不应拦截
        res1 = await handle_generic_action(event, self.session, self.cooldown_tracker)
        res2 = await handle_generic_action(event, self.session, self.cooldown_tracker)
        
        self.assertIsNone(res1)
        self.assertIsNone(res2)

    @patch('core.consumer.Execute_Task_by_Name')
    async def test_failure_unlocks_immediately(self, mock_execute):
        """验证：如果创建失败，锁不生效/自动释放。"""
        self.session.resource_manager.get_resource.return_value = None
        # 模拟第一次执行失败
        mock_execute.return_value = {"success": False, "error": "Disk Full"}
        
        event = FileWriteRequest(path="fail.py", content="fail")
        
        await handle_generic_action(event, self.session, self.cooldown_tracker)
        
        # 此时 tracker 中不应有该路径记录（或已过期）
        abs_path = os.path.normcase(os.path.abspath("fail.py"))
        self.assertNotIn(abs_path, self.cooldown_tracker)

if __name__ == '__main__':
    unittest.main()
