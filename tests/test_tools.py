#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tests/test_tools.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260210
# Version: 1.0.0

import unittest
import os
import shutil
from infra.tools import list_dir, write_file, _is_path_safe

class TestTools(unittest.TestCase):
    def setUp(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.test_staging = os.path.join(self.base_dir, ".staging")
        # 清理之前的测试痕迹
        if os.path.exists(self.test_staging):
            shutil.rmtree(self.test_staging)

    def test_list_dir_external_access(self):
        """验证 list_dir 是否具备完全放权能力，可以访问外部路径"""
        # 尝试访问项目根目录的上一级目录（通常具备读取权限且属于外部路径）
        external_path = os.path.dirname(self.base_dir)
        res = list_dir(self.base_dir, external_path)
        if not res["success"]:
            print(f"\n[DEBUG] list_dir failed for {external_path}: {res}")
        self.assertTrue(res["success"], f"Failed to list external dir: {res.get('error')}")
        self.assertIn("items", res)

    def test_is_path_safe_tiered(self):
        """验证 _is_path_safe 的分级权限逻辑"""
        # Read 级别：应允许外部路径（非黑名单）
        self.assertTrue(_is_path_safe(self.base_dir, "C:\\Users", level="R"))
        
        # Write 级别：应拦截非 workspace 路径
        self.assertFalse(_is_path_safe(self.base_dir, "C:\\Users", level="W"))
        
        # 黑名单拦截：无论是 R 还是 W
        self.assertFalse(_is_path_safe(self.base_dir, "C:\\Windows", level="R"))

    def test_write_file_create_redirection(self):
        """验证 write_file 的 Create 动作是否正确重定向至 Staging"""
        target_path = "tests/mock_new_file.txt"
        content = "Testing staging redirection"
        
        res = write_file(self.base_dir, target_path, content)
        
        self.assertTrue(res["success"])
        self.assertEqual(res["action_type"], "Create")
        # 适配 Windows 反斜杠
        normalized_result = res["result"].replace("\\", "/")
        self.assertIn(".staging/new/", normalized_result)
        
        # 物理检查
        expected_physical = os.path.join(self.base_dir, ".staging", "new", "tests", "mock_new_file.txt")
        self.assertTrue(os.path.exists(expected_physical))

    def test_write_file_update_backup(self):
        """验证 write_file 的 Update 动作是否在工作区内直写并存底"""
        target_path = "demo.txt" # 根目录下已存在的文件
        content = "Updated content for test"
        
        res = write_file(self.base_dir, target_path, content)
        
        self.assertTrue(res["success"])
        self.assertEqual(res["action_type"], "Update")
        
        # 检查备份
        backup_dir = os.path.join(self.base_dir, ".staging", "backups")
        self.assertTrue(os.listdir(backup_dir)) # 只要目录下有文件即可

    def test_prevent_double_nesting(self):
        """验证 write_file 是否防止了 .staging/new/.staging/new 的双重嵌套"""
        # 模拟 Agent 已经写了 .staging/new/ 前缀的情况
        target_path = ".staging/new/nested_fix.txt"
        content = "No more double staging"
        
        res = write_file(self.base_dir, target_path, content)
        self.assertTrue(res["success"])
        
        # 正确路径应为 .staging/new/nested_fix.txt，而不是 .staging/new/.staging/new/nested_fix.txt
        rel_path = res["result"].split("'")[1]
        self.assertEqual(os.path.normpath(rel_path), os.path.normpath(".staging/new/nested_fix.txt"))

if __name__ == "__main__":
    unittest.main()
