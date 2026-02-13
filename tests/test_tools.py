#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tests/test_tools.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260210
# Version: 1.1.0

import unittest
import os
import shutil
from infra.tools import list_dir, write_file, _is_path_safe

class TestTools(unittest.TestCase):
    base_dir: str
    test_staging: str
    update_test_file: str

    def setUp(self):
        # 强制归一化 base_dir
        raw_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.base_dir = os.path.normcase(os.path.normpath(raw_base))
        self.test_staging = os.path.normcase(os.path.join(self.base_dir, "staging"))
        
        # 清理
        if os.path.exists(self.test_staging):
            shutil.rmtree(self.test_staging)
        
        # 清理可能残留的 mock 文件 (应对之前的 bug 残留)
        mock_file = os.path.join(self.base_dir, "tests", "mock_new_file.txt")
        if os.path.exists(mock_file):
            os.remove(mock_file)
            
        # 预置文件：必须使用 os.path.join 确保存储路径与工具解析逻辑一致
        self.update_test_file = os.path.normcase(os.path.abspath(os.path.join(self.base_dir, "demo_update.txt")))
        with open(self.update_test_file, 'w', encoding='utf-8') as f:
            f.write("initial content")

    def tearDown(self):
        if os.path.exists(self.update_test_file):
            os.remove(self.update_test_file)
        if os.path.exists(self.test_staging):
            shutil.rmtree(self.test_staging)

    def test_list_dir_external_access(self):
        """验证 list_dir 是否具备完全放权能力，可以访问外部路径"""
        # 在 Windows 上，尝试访问 C 盘根目录（通常有 System Volume Information 等不可读项，但根目录本身应可列出）
        external_path = "C:\\" if os.name == 'nt' else "/"
        res = list_dir(self.base_dir, external_path)
        # 如果由于权限限制（如 C 盘被锁定）失败，我们也捕获它，
        # 但 list_dir 应该在报错前通过 _is_path_safe 的 'R' 级校验
        self.assertTrue(res.get("success") or "Access denied" not in str(res.get("error")))

    def test_is_path_safe_tiered(self):
        """验证 _is_path_safe 的分级权限逻辑"""
        # Read 级别：应返回 UNCERTAIN 以后台触发授权
        self.assertEqual(_is_path_safe(self.base_dir, "C:\\Users", level="R"), "UNCERTAIN")
        
        # Write 级别：应拦截非 workspace 路径
        self.assertEqual(_is_path_safe(self.base_dir, "C:\\Users", level="W"), "DENIED")
        
        # 基准测试：工作区内应允许
        self.assertEqual(_is_path_safe(self.base_dir, self.base_dir, level="R"), "ALLOWED")

    def test_write_file_create_redirection(self):
        """验证 write_file 的 Create 动作是否正确重定向至 Staging"""
        target_path = "tests/mock_new_file.txt"
        content = "Testing staging redirection"
        
        res = write_file(self.base_dir, target_path, content)
        
        self.assertTrue(res["success"])
        self.assertEqual(res["action_type"], "Create")
        # 适配 Windows 反斜杠
        normalized_result = res["result"].replace("\\", "/")
        self.assertIn("staging/new/", normalized_result)
        
        # 物理检查
        expected_physical = os.path.join(self.base_dir, "staging", "new", "tests", "mock_new_file.txt")
        self.assertTrue(os.path.exists(expected_physical))

    def test_write_file_update_backup(self):
        """验证 write_file 的 Update 动作是否在工作区内直写并存底"""
        target_path = "demo_update.txt" # 根目录下预置的文件
        content = "Updated content for test"
        
        res = write_file(self.base_dir, target_path, content)
        
        self.assertTrue(res["success"])
        self.assertEqual(res["action_type"], "Update")
        
        # 检查备份
        backup_dir = os.path.join(self.base_dir, "staging", "backups")
        self.assertTrue(os.listdir(backup_dir)) # 只要目录下有文件即可

    def test_prevent_double_nesting(self):
        """验证 write_file 是否防止了 staging/new/staging/new 的双重嵌套"""
        # 模拟各种可能的嵌套组合
        nested_paths = [
            "staging/new/nested_fix.txt",
            "staging\\new\\nested_win.txt",
            "staging/new/staging/new/deep_nest.txt"
        ]
        
        for p in nested_paths:
            res = write_file(self.base_dir, p, "No more double staging")
            self.assertTrue(res["success"])
            # 提取路径并验证
            # 物理路径应始终为 staging/new/{basename}
            rel_result = res["result"].split("'")[1]
            self.assertFalse("staging/new/staging/new" in rel_result.replace("\\", "/"))

    def test_execute_command_success(self):
        """验证命令执行功能"""
        from infra.tools import execute_command
        # 使用 echo 指令进行测试
        cmd = "echo hello_test"
        res = execute_command(self.base_dir, cmd)
        self.assertTrue(res["success"])
        self.assertIn("hello_test", res["result"])
        self.assertEqual(res["exit_code"], 0)

    def test_execute_command_timeout(self):
        """验证命令执行超时"""
        from infra.tools import execute_command
        # 这是一个在 Windows 下耗时的指令示例（或使用 python 模拟延时）
        cmd = "python -c \"import time; time.sleep(5)\""
        res = execute_command(self.base_dir, cmd, timeout=1)
        self.assertFalse(res["success"])
        self.assertIn("timed out", res["error"])

if __name__ == "__main__":
    unittest.main()
